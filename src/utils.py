import json
import sys
import logging
import traceback
import asyncio
import os
import functools
from typing import Dict, Any, Callable, Awaitable, TypeVar, Optional, List
from contextlib import asynccontextmanager
import asyncpg
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env
load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD")
}

# Função para obter uma conexão com o banco de dados
async def get_connection():
    """Estabelece conexão com o banco de dados PostgreSQL"""
    return await asyncpg.connect(**DB_CONFIG)

# Configuração do logging
def setup_logging(level=logging.INFO):
    """
    Configura o sistema de logging com um formato consistente
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger()

# Decorator para tratamento de exceções
def exception_handler(func):
    """
    Decorator que captura e trata exceções em funções assíncronas
    
    @exception_handler
    async def minha_funcao():
        pass
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            log_exception("Erro não esperado na função {}: {}".format(func.__name__, str(e)))
            handle_error(e)
    
    return wrapper

# Decorador para tratamento padronizado de exceções em funções assíncronas
def handle_exceptions(message=None, default_return=None):
    """
    Decorador que envolve a função com tratamento padronizado de exceções.
    
    Exemplo de uso:
    
    @handle_exceptions(message="Erro ao processar dados", default_return=[])
    async def processar_dados():
        # Seu código aqui
        return result
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_message = f"{message or func.__name__}: {str(e)}"
                log_exception(error_message)
                return default_return
        return wrapper
    return decorator

# Funções para tratamento de erros
def log_error(message: str) -> None:
    """
    Registra um erro no stderr (mantido para compatibilidade)
    """
    print(message, file=sys.stderr)

def log_exception(message: str = "Erro não esperado:", exc_info=True) -> None:
    """
    Registra uma exceção no log com traceback completo
    """
    logging.error(message, exc_info=exc_info)

def print_traceback() -> None:
    """
    Imprime o traceback da exceção atual para o stderr
    """
    print(traceback.format_exc(), file=sys.stderr)

def handle_error(error: Exception) -> None:
    """
    Trata um erro de forma padronizada (mantido para compatibilidade)
    """
    error_msg = {
        "error": "Erro durante a execução",
        "message": str(error)
    }
    print(json.dumps(error_msg, ensure_ascii=False))
    # Removido sys.exit(1) para não encerrar o servidor API

def normalize_url_string(text: str) -> str:
    """
    Normaliza uma string para uso em URLs, removendo acentos e substituindo caracteres especiais
    """
    import unicodedata
    import re
    
    # Normaliza a string: remove acentos, mas mantém as letras
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
    
    # Remove caracteres especiais, mantém apenas letras, números, espaços e alguns caracteres básicos
    text = re.sub(r'[^\w\s\-]', '', text)
    
    # Substitui espaços por +
    text = text.replace(' ', '+')
    
    return text

# Helpers para banco de dados
T = TypeVar('T')

@asynccontextmanager
async def db_transaction(conn):
    """
    Context manager para transações de banco de dados
    """
    transaction = conn.transaction()
    try:
        await transaction.start()
        yield
        await transaction.commit()
    except:
        await transaction.rollback()
        raise

async def with_connection(func: Callable[[Any], Awaitable[T]]) -> T:
    """
    Executa uma função com uma conexão de banco de dados
    e fecha a conexão automaticamente ao terminar
    
    Exemplo de uso:
    
    async def get_data(conn, param):
        # use conn aqui
        return await conn.fetch("SELECT * FROM tabela WHERE campo = $1", param)
    
    result = await with_connection(lambda conn: get_data(conn, "valor"))
    """
    conn = await get_connection()
    try:
        return await func(conn)
    finally:
        await conn.close()

# Função para verificar status de tarefas no banco
async def count_tasks_by_status(status: str) -> int:
    """
    Retorna a contagem de tarefas com um determinado status
    """
    async def _count(conn):
        query = "SELECT COUNT(*) FROM buscas WHERE status = $1"
        return await conn.fetchval(query, status)
    
    return await with_connection(_count)

# Funções de utilidade para manipulação/formatação de dados

def format_phone_number(phone: str) -> str:
    """
    Formata um número de telefone para o padrão internacional brasileiro (55)
    Remove caracteres não numéricos e adiciona o prefixo 55 se necessário
    """
    if not phone:
        return ""
        
    # Remove caracteres não numéricos
    phone = ''.join(filter(str.isdigit, phone))
    
    # Se o número já começar com 55, mantém como está
    if not phone.startswith('55'):
        # Se começar com 0, remove o zero inicial
        if phone.startswith('0'):
            phone = phone[1:]
        
        # Adiciona o código do Brasil (55)
        phone = '55' + phone
        
    return phone

def parse_float(value, default=0.0) -> float:
    """
    Converte um valor para float, tratando possíveis formatos diferentes
    como strings com vírgulas no lugar de pontos decimais
    """
    try:
        if value is None:
            return default
            
        if isinstance(value, str):
            # Substitui vírgula por ponto antes da conversão
            return float(value.replace(",", "."))
        
        return float(value)
    except (ValueError, TypeError):
        return default

def parse_int(value, default=0) -> int:
    """
    Converte um valor para inteiro, tratando possíveis formatos diferentes
    como strings com pontos ou vírgulas como separadores de milhar
    """
    try:
        if value is None:
            return default
            
        if isinstance(value, str):
            # Remove pontos e vírgulas que possam ser separadores de milhar
            value = value.replace(".", "").replace(",", "")
        
        return int(value)
    except (ValueError, TypeError):
        return default

# Funções para trabalhar com dados de busca

def get_task_id_from_busca_id(busca_id: int) -> str:
    """
    Retorna o ID da tarefa baseado no ID da busca
    """
    return f"task_{busca_id}"

# Funções para trabalhar com logs em diferentes níveis

def log_debug(message: str) -> None:
    """
    Registra uma mensagem de debug no log
    """
    logging.debug(message)

def log_info(message: str) -> None:
    """
    Registra uma informação no log
    """
    logging.info(message)

def log_warning(message: str) -> None:
    """
    Registra um aviso no log
    """
    logging.warning(message)

# Funções para medição de performance

def timed_execution(func):
    """
    Decorator que mede o tempo de execução de uma função
    
    @timed_execution
    async def minha_funcao():
        pass
    """
    import time
    import functools
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            return await func(*args, **kwargs)
        finally:
            end_time = time.time()
            elapsed = end_time - start_time
            logging.info(f"Função {func.__name__} executada em {elapsed:.2f} segundos")
    
    return wrapper

# Funções para diagnóstico e tratamento de tarefas travadas
async def force_restart_stuck_task(task_id: int) -> bool:
    """
    Força a reinicialização de uma tarefa que parece estar travada
    """
    async def _restart(conn):
        # Primeiro verifica se a tarefa existe e está em processamento
        check_query = """
            SELECT id FROM buscas
            WHERE id = $1 AND status = 'processing'
        """
        exists = await conn.fetchval(check_query, task_id)
        
        if not exists:
            return False
            
        # Redefine o status para waiting
        update_query = """
            UPDATE buscas SET status = 'waiting'
            WHERE id = $1
            RETURNING id
        """
        updated = await conn.fetchval(update_query, task_id)
        
        if updated:
            log_info(f"Tarefa {task_id} foi reiniciada (status alterado para waiting)")
            return True
        return False
        
    return await with_connection(_restart)
