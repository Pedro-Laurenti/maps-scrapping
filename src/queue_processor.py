import asyncio
import sys
import time
import traceback
from typing import Dict, Any, List, Optional
import logging
from src.utils import setup_logging, log_exception, with_connection, count_tasks_by_status
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
    
    # Verifica imediatamente se há mais tarefas para processar
    # Isso permite iniciar a próxima tarefa sem esperar o intervalo de verificação
    task = asyncio.create_task(check_for_next_task())
    
    # Log informativo para ajudar no diagnóstico
    logging.info(f"Busca ID {busca_id} completada. Status: {result['status']}. Verificando próxima tarefa na fila.")
    
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
            logging.debug("Nenhuma busca pendente encontrada para processar")
            return None
        
    except Exception as e:
        from src.utils import log_exception
        log_exception(f"Erro crítico ao processar item da fila")
        
        # Tenta identificar a busca para atualizar o status
        if 'next_busca' in locals() and next_busca and 'id' in next_busca:
            busca_id = next_busca['id']
            try:
                await update_busca_status(busca_id, "error")
                logging.info(f"Status da busca {busca_id} atualizado para 'error' devido a exceção")
            except Exception:
                logging.error(f"Não foi possível atualizar o status da busca {busca_id}")
                
        return {"status": "error", "error": str(e)}

async def update_queue_positions():
    """
    Atualiza as posições na fila regularmente
    """
    global _processing_flag, _queue_positions
    
    while _processing_flag:
        try:
            async with _queue_lock:
                async def update_positions(conn):
                    # Busca também tarefas em processamento para mostrar status completo ao usuário
                    query = """
                        SELECT id, status FROM buscas 
                        WHERE status IN ('waiting', 'processing')
                        ORDER BY id ASC
                    """
                    rows = await conn.fetch(query)
                    
                    # Reseta as posições
                    positions = {}
                    
                    # Primeiro adiciona os itens em processamento (com posição 0)
                    processing_ids = []
                    for row in rows:
                        if row['status'] == 'processing':
                            positions[row['id']] = 0  # 0 indica "em processamento"
                            processing_ids.append(row['id'])
                    
                    # Depois adiciona os itens em espera (com posição sequencial)
                    waiting_position = 1
                    for row in rows:
                        if row['status'] == 'waiting':
                            positions[row['id']] = waiting_position
                            waiting_position += 1
                    
                    # Log de diagnóstico para verificar a fila
                    if rows:
                        items_in_queue = len([r for r in rows if r['status'] == 'waiting'])
                        items_processing = len(processing_ids)
                        logging.info(f"Status da fila: {items_processing} processando, {items_in_queue} aguardando")
                    
                    return positions
                
                # Usar a função helper para gerenciar a conexão
                _queue_positions = await with_connection(update_positions)
                    
            # Aguarda um intervalo antes da próxima atualização
            await asyncio.sleep(QUEUE_UPDATE_INTERVAL)
            
        except Exception as e:
            log_exception(f"Erro ao atualizar posições na fila: {str(e)}")
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
            
            # Diagnóstico adicional: verifica números no banco de dados
            processing_count = await count_tasks_by_status("processing")
            waiting_count = await count_tasks_by_status("waiting")
            
            if current_running_count == 0 and processing_count > 0:
                logging.warning(f"Inconsistência detectada: {processing_count} tarefas marcadas como em processamento, mas não há tarefas em execução. Verificando o estado...")
                
                # Verifica se há trabalhos em inconsistência
                if waiting_count > 0:
                    logging.info(f"Iniciando verificação da próxima tarefa devido a inconsistência...")
                    await check_for_next_task()
            
            if current_running_count < MAX_CONCURRENT_TASKS:
                # Usa a mesma função que verifica por próximas tarefas
                # para garantir consistência de comportamento
                await check_for_next_task()
            else:
                logging.info(f"Já existem {current_running_count} tarefas em execução. Aguardando...")
            
            # Aguarda um intervalo antes de verificar novamente
            # Intervalo mais curto se não tivermos nenhuma tarefa em execução e houver tarefas pendentes
            wait_time = QUEUE_CHECK_INTERVAL / 4 if (current_running_count == 0 and waiting_count > 0) else QUEUE_CHECK_INTERVAL
            await asyncio.sleep(wait_time)
            
        except Exception as e:
            logging.error(f"Erro no worker da fila: {str(e)}")
            logging.error(traceback.format_exc())
            await asyncio.sleep(QUEUE_CHECK_INTERVAL)

async def check_for_next_task():
    """
    Verifica e inicia a próxima tarefa na fila.
    Esta função é chamada imediatamente após a conclusão de uma tarefa
    para garantir o processamento contínuo sem esperar o intervalo de verificação.
    """
    try:            # Verifica se há itens em espera no banco de dados
        conn = await get_connection()
        try:
            query = """
                SELECT COUNT(*) FROM buscas 
                WHERE status = 'waiting'
            """
            waiting_count = await conn.fetchval(query)
            
            # Verifica se há tarefas em processamento
            processing_query = """
                SELECT COUNT(*) FROM buscas 
                WHERE status = 'processing'
            """
            processing_count = await conn.fetchval(processing_query)
            
            # Se há tarefas em espera E o número de tarefas em execução
            # é menor que o máximo permitido, inicia uma nova tarefa
            current_running_count = len(_running_tasks)
            if waiting_count > 0 and current_running_count < MAX_CONCURRENT_TASKS:
                logging.info(f"Encontradas {waiting_count} tarefas em espera. Iniciando a próxima imediatamente.")
                
                # Cria uma nova tarefa para processar o próximo item da fila
                task = asyncio.create_task(process_queue_item())
                _running_tasks.add(task)
                # Remove a tarefa do conjunto quando terminar
                task.add_done_callback(_running_tasks.discard)
            else:
                if current_running_count >= MAX_CONCURRENT_TASKS:
                    logging.info(f"Não iniciando nova tarefa: já existem {current_running_count} tarefas em execução (máximo permitido).")
                elif processing_count > 0 and current_running_count == 0:
                    # Esta é uma condição de inconsistência - há tarefas marcadas como em processamento no banco
                    # mas não há tarefas em execução localmente
                    logging.warning(f"Inconsistência detectada: {processing_count} tarefas marcadas como em processamento no banco de dados, mas nenhuma tarefa em execução localmente.")
        finally:
            await conn.close()
    except Exception as e:
        logging.error(f"Erro ao verificar próxima tarefa: {str(e)}")
        logging.error(traceback.format_exc())

def start_queue_processor():
    """
    Inicia o processador de fila em background
    """
    global _processing_flag
    
    if not _processing_flag:
        _processing_flag = True
        
        # Configura o logger usando a função centralizada
        setup_logging()
        
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
