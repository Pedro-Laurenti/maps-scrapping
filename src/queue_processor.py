import asyncio
import sys
import time
from typing import Dict, Any, List, Optional
import logging
from src.database import get_next_busca_from_queue, update_busca_status, insert_batch_leads, get_connection
from src.crawler import scrape_google_maps

# Configurações
BATCH_SIZE = 20  # Número máximo de resultados por batch
MAX_CONCURRENT_TASKS = 2  # Número máximo de tarefas concorrentes
QUEUE_CHECK_INTERVAL = 5  # Intervalo em segundos para verificar novas tarefas na fila
QUEUE_UPDATE_INTERVAL = 30  # Intervalo em segundos para atualizar as posições da fila

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
            
            # Remove da fila de posições
            if busca_id in _queue_positions:
                del _queue_positions[busca_id]
            
            # Processa a busca em batches
            result = await process_busca_in_batches(next_busca)
            
            return result
        
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
                    query = """
                        SELECT id FROM buscas 
                        WHERE status = 'waiting'
                        ORDER BY id ASC
                    """
                    rows = await conn.fetch(query)
                    
                    # Atualiza as posições na fila
                    _queue_positions = {}
                    for i, row in enumerate(rows):
                        _queue_positions[row['id']] = i + 1
                        
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
            if len(_running_tasks) < MAX_CONCURRENT_TASKS:
                # Cria uma nova tarefa para processar um item da fila
                task = asyncio.create_task(process_queue_item())
                _running_tasks.add(task)
                
                # Remove a tarefa do conjunto quando terminar
                task.add_done_callback(_running_tasks.discard)
            
            # Aguarda um intervalo antes de verificar novamente
            await asyncio.sleep(QUEUE_CHECK_INTERVAL)
            
        except Exception as e:
            logging.error(f"Erro no worker da fila: {str(e)}")
            await asyncio.sleep(QUEUE_CHECK_INTERVAL)

def start_queue_processor():
    """
    Inicia o processador de fila em background
    """
    global _processing_flag
    
    if not _processing_flag:
        _processing_flag = True
        
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

        # Inicia o worker em uma tarefa assíncrona
        loop.create_task(queue_worker())
        
        # Inicia o atualizador de posições na fila
        loop.create_task(update_queue_positions())

def stop_queue_processor():
    """
    Para o processador de fila
    """
    global _processing_flag
    _processing_flag = False

def get_queue_position(busca_id: int) -> Optional[int]:
    """
    Retorna a posição de uma busca na fila, se disponível
    """
    return _queue_positions.get(busca_id)
