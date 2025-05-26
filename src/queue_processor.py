import asyncio
import sys
import time
from typing import Dict, Any, List, Optional
import logging
import traceback
from src.database import get_next_busca_from_queue, update_busca_status, insert_batch_leads, get_connection
from src.crawler import scrape_google_maps

# Configurações
BATCH_SIZE = 20  # Número máximo de resultados por batch
MAX_CONCURRENT_TASKS = 1  # Número máximo de tarefas concorrentes (mantemos em 1 para garantir ordem FIFO)
QUEUE_CHECK_INTERVAL = 60  # Intervalo em segundos para verificar novas tarefas na fila (1 minuto)
QUEUE_UPDATE_INTERVAL = 60  # Intervalo em segundos para atualizar as posições da fila (1 minuto)

# Controle de tarefas em execução
_running_tasks = set()
_processing_flag = False
_queue_positions = {}  # Armazena as posições da fila

# Lock para sincronização
_queue_lock = asyncio.Lock()

async def process_busca_in_batches(busca_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Processa uma busca em batches para evitar sobrecarga com grandes volumes
    """
    busca_id = busca_data['id']
    region = busca_data['regiao']
    business_type = busca_data['tipo_empresa']
    max_results = busca_data['qtd_max']
    keywords = ' '.join(busca_data['palavras_chave']) if busca_data['palavras_chave'] else ""
    
    # Resultado final para retornar
    result = {
        "status": "processing",
        "total_leads": 0,
        "batches_processed": 0,
        "busca_id": busca_id
    }
    
    try:
        remaining = max_results
        offset = 0
        
        # Calcula o tamanho de cada batch baseado no total
        batch_size = BATCH_SIZE
        if max_results > 100:
            batch_size = 30  # Batches maiores para grandes volumes
        
        while remaining > 0:
            current_batch = min(batch_size, remaining)
            
            # Executa o scraping para o batch atual
            batch_results = await scrape_google_maps(
                region=region,
                business_type=business_type,
                max_results=current_batch,
                keywords=keywords,
                offset=offset
            )
            
            if batch_results:
                # Salva o batch atual no banco
                await insert_batch_leads(busca_id, batch_results)
                
                # Atualiza contadores
                result["total_leads"] += len(batch_results)
                result["batches_processed"] += 1
                
                # Se retornou menos resultados que o solicitado, não há mais para buscar
                if len(batch_results) < current_batch:
                    break
                
                # Atualiza para próximo batch
                remaining -= len(batch_results)
                offset += len(batch_results)
            else:
                # Se não retornou resultados, encerra o processamento
                break
            
            # Pequena pausa entre batches para evitar bloqueio
            await asyncio.sleep(3)
        
        # Atualiza status para concluído
        await update_busca_status(busca_id, "concluido")
        result["status"] = "completed"
        
    except Exception as e:
        # Em caso de erro, atualiza o status da busca
        await update_busca_status(busca_id, "error")
        result["status"] = "error"
        result["error"] = str(e)
    
    # Remove da fila de posições
    if busca_id in _queue_positions:
        del _queue_positions[busca_id]
    
    return result

async def process_queue_item():
    """
    Processa um item da fila de buscas pendentes
    """
    try:
        # Obtém a próxima busca da fila
        next_busca = await get_next_busca_from_queue()
        
        if next_busca:
            busca_id = next_busca['id']
            
            # Log de início do processamento
            logging.info(f"Iniciando processamento da busca ID {busca_id}: {next_busca['regiao']} - {next_busca['tipo_empresa']}")
            
            # Atualiza status no banco novamente para garantir que está como "processing"
            await update_busca_status(busca_id, "processing")
            
            # Processa a busca em batches
            result = await process_busca_in_batches(next_busca)
            
            # Log de finalização
            logging.info(f"Busca ID {busca_id} finalizada com status: {result['status']}")
            
            return result
        else:
            # Se não há buscas para processar, apenas retorna
            return None
        
    except Exception as e:
        logging.error(f"Erro ao processar item da fila: {str(e)}")
        return {"status": "error", "error": str(e)}

async def update_queue_positions():
    """
    Atualiza as posições na fila regularmente
    """
    global _processing_flag, _queue_positions
    
    while _processing_flag:
        try:
            async with _queue_lock:
                # Consulta o banco para obter todas as buscas em espera
                conn = await get_connection()
                try:
                    # Busca também tarefas em processamento para mostrar status completo ao usuário
                    query = """
                        SELECT id, status FROM buscas 
                        WHERE status IN ('waiting', 'processing')
                        ORDER BY id ASC
                    """
                    rows = await conn.fetch(query)
                    
                    # Reseta as posições
                    _queue_positions = {}
                    
                    # Primeiro adiciona os itens em processamento (com posição 0)
                    processing_ids = []
                    for row in rows:
                        if row['status'] == 'processing':
                            _queue_positions[row['id']] = 0  # 0 indica "em processamento"
                            processing_ids.append(row['id'])
                    
                    # Depois adiciona os itens em espera (com posição sequencial)
                    waiting_position = 1
                    for row in rows:
                        if row['status'] == 'waiting':
                            _queue_positions[row['id']] = waiting_position
                            waiting_position += 1
                    
                    # Log de diagnóstico para verificar a fila
                    if rows:
                        items_in_queue = len([r for r in rows if r['status'] == 'waiting'])
                        items_processing = len(processing_ids)
                        logging.info(f"Status da fila: {items_processing} processando, {items_in_queue} aguardando")
                        
                finally:
                    await conn.close()
                    
            # Aguarda um intervalo antes da próxima atualização
            await asyncio.sleep(QUEUE_UPDATE_INTERVAL)
            
        except Exception as e:
            logging.error(f"Erro ao atualizar posições na fila: {str(e)}")
            await asyncio.sleep(QUEUE_UPDATE_INTERVAL)

async def queue_worker():
    """
    Worker para processar a fila continuamente
    """
    global _processing_flag
    
    while _processing_flag:
        try:
            # Verifica se há capacidade para processar mais tarefas
            current_running_count = len(_running_tasks)
            
            if current_running_count < MAX_CONCURRENT_TASKS:
                # Verifica se há tarefas em espera no banco
                conn = await get_connection()
                try:
                    query = """
                        SELECT COUNT(*) FROM buscas 
                        WHERE status = 'waiting'
                    """
                    waiting_count = await conn.fetchval(query)
                    
                    # Se existem tarefas esperando, força a criação de uma nova tarefa
                    if waiting_count > 0:
                        logging.info(f"Existem {waiting_count} tarefas na fila de espera. Iniciando processamento...")
                        async with _queue_lock:  # Usa o lock para evitar condições de corrida
                            # Cria uma nova tarefa para processar um item da fila
                            task = asyncio.create_task(process_queue_item())
                            _running_tasks.add(task)
                            
                            # Remove a tarefa do conjunto quando terminar
                            task.add_done_callback(_running_tasks.discard)
                finally:
                    await conn.close()
            else:
                logging.info(f"Já existem {current_running_count} tarefas em execução. Aguardando...")
            
            # Aguarda um intervalo antes de verificar novamente
            # Intervalo mais curto se não tivermos nenhuma tarefa em execução
            wait_time = QUEUE_CHECK_INTERVAL / 2 if current_running_count == 0 else QUEUE_CHECK_INTERVAL
            await asyncio.sleep(wait_time)
            
        except Exception as e:
            logging.error(f"Erro no worker da fila: {str(e)}")
            logging.error(traceback.format_exc())
            await asyncio.sleep(QUEUE_CHECK_INTERVAL)

def start_queue_processor():
    """
    Inicia o processador de fila em background
    """
    global _processing_flag
    
    if not _processing_flag:
        _processing_flag = True
        
        # Configura o logger para facilitar debug
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
        
        logging.info("Iniciando processador de fila...")
        
        # Usa a policy padrão do sistema para criar o loop
        if sys.platform == 'win32':
            # Configura a policy para Windows
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            
        # Obtém o loop de eventos atual ou cria um novo
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Limpa tasks antigas se existirem
        global _running_tasks
        _running_tasks.clear()
        
        # Inicia o worker em uma tarefa assíncrona
        loop.create_task(queue_worker())
        
        # Inicia o atualizador de posições na fila
        loop.create_task(update_queue_positions())
        
        logging.info(f"Processador de fila iniciado. Permitindo {MAX_CONCURRENT_TASKS} tarefas simultâneas.")

def stop_queue_processor():
    """
    Para o processador de fila
    """
    global _processing_flag
    _processing_flag = False
    logging.info("Processador de fila desligado.")

def get_queue_position(busca_id: int) -> Optional[int]:
    """
    Retorna a posição de uma busca na fila, se disponível
    """
    return _queue_positions.get(busca_id)
