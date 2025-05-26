import json
import sys
import logging
import traceback
import asyncio
from typing import Dict, Any, Callable, Awaitable, TypeVar, Optional, List
from contextlib import asynccontextmanager

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

# Funções utilitárias para dados
def read_input_params() -> Dict[str, Any]:
    """
    Função legada mantida para compatibilidade com o script original.
    Na API, usamos o modelo Pydantic diretamente.
    """
    try:
        with open("params.json", "r", encoding="utf-8") as f:
            input_data = json.load(f)
        
        region = input_data.get("region", "")
        business_type = input_data.get("business_type", "")
        max_results = int(input_data.get("max_results", 10))
        keywords = input_data.get("keywords", "")
        
        if not region or not business_type:
            error_msg = {
                "error": "Parâmetros insuficientes",
                "message": "É necessário fornecer ao menos região e tipo de negócio"
            }
            print(json.dumps(error_msg))
            sys.exit(1)
            
        return {
            "region": region,
            "business_type": business_type,
            "max_results": max_results,
            "keywords": keywords
        }
    except (json.JSONDecodeError, FileNotFoundError):
        error_msg = {
            "error": "Formato inválido ou arquivo não encontrado",
            "message": "Os parâmetros devem ser fornecidos em formato JSON no arquivo params.json"
        }
        print(json.dumps(error_msg))
        sys.exit(1)

def output_results(results: list) -> None:
    """
    Imprime os resultados como JSON.
    Garante que a saída é UTF-8 válido e que os caracteres especiais são mantidos.
    """
    # Serializa para JSON com encoding UTF-8 e garantindo que caracteres não-ASCII são mantidos
    output = json.dumps(results, ensure_ascii=False)
    
    # Para maior compatibilidade, explicitamente codifica como UTF-8 e imprime os bytes
    # Isso ajuda a evitar problemas de codificação no pipe do subprocess
    if hasattr(sys.stdout, 'buffer'):
        # Se stdout suporta buffer (normal no Python 3)
        sys.stdout.buffer.write(output.encode('utf-8'))
        sys.stdout.buffer.write(b'\n')
        sys.stdout.buffer.flush()
    else:
        # Fallback para o comportamento padrão
        print(output)

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
    from src.database import get_connection
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

async def check_running_tasks() -> Dict[str, Any]:
    """
    Verifica as tarefas em execução e retorna informações detalhadas
    """
    async def _check(conn):
        # Buscar tarefas em processamento
        query = """
            SELECT id, regiao, tipo_empresa, status, data_busca,
                   EXTRACT(EPOCH FROM (NOW() - data_busca)) as seconds_running
            FROM buscas 
            WHERE status = 'processing'
        """
        rows = await conn.fetch(query)
        
        result = {
            "processing_count": len(rows),
            "tasks": []
        }
        
        # Adiciona informações para cada tarefa em processamento
        for row in rows:
            task_info = dict(row)
            # Adiciona um campo para indicar se a tarefa parece estar travada
            # (consideramos mais de 15 minutos como potencialmente travada)
            task_info["appears_stuck"] = task_info["seconds_running"] > 900  # 15 minutos
            result["tasks"].append(task_info)
            
        return result
    
    return await with_connection(_check)

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

async def debug_queue_state() -> Dict[str, Any]:
    """
    Retorna informações detalhadas sobre o estado atual da fila
    para diagnóstico de problemas
    """
    async def _debug(conn):
        # Contagem por status
        count_query = """
            SELECT status, COUNT(*) as count
            FROM buscas
            GROUP BY status
            ORDER BY status
        """
        count_rows = await conn.fetch(count_query)
        
        # Tarefas em processamento com detalhes
        processing_query = """
            SELECT id, regiao, tipo_empresa, data_busca,
                   EXTRACT(EPOCH FROM (NOW() - data_busca)) as seconds_running
            FROM buscas
            WHERE status = 'processing'
            ORDER BY data_busca ASC
        """
        processing_rows = await conn.fetch(processing_query)
        
        # Próximas tarefas na fila
        waiting_query = """
            SELECT id, regiao, tipo_empresa, data_busca
            FROM buscas
            WHERE status = 'waiting'
            ORDER BY id ASC
            LIMIT 10
        """
        waiting_rows = await conn.fetch(waiting_query)
        
        return {
            "counts": {row["status"]: row["count"] for row in count_rows},
            "processing": [dict(row) for row in processing_rows],
            "waiting": [dict(row) for row in waiting_rows]
        }
        
    return await with_connection(_debug)

async def manual_process_next_task() -> Optional[int]:
    """
    Processa manualmente a próxima tarefa na fila,
    ignorando restrições de concorrência.
    Útil para desbloquear a fila em situações de erro.
    """
    async def _process(conn):
        # Tenta pegar a próxima tarefa em espera
        query = """
            SELECT id 
            FROM buscas
            WHERE status = 'waiting'
            ORDER BY id ASC
            LIMIT 1
        """
        task_id = await conn.fetchval(query)
        
        if task_id:
            # Define o status como processando
            update_query = """
                UPDATE buscas SET status = 'processing'
                WHERE id = $1
            """
            await conn.execute(update_query, task_id)
            log_info(f"Manualmente iniciando processamento da tarefa {task_id}")
            
        return task_id
    
    return await with_connection(_process)
