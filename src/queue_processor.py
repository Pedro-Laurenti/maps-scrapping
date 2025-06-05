import asyncio
import os
import time
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

from src.database import (
    insert_busca, insert_leads, get_leads_by_busca_id, 
    update_busca_status, get_busca_by_id, get_connection,
    get_next_busca_from_queue, insert_batch_leads
)
from src.crawler import scrape_google_maps
from src.utils import log_info, log_exception

load_dotenv()

# Definições de ambiente
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "20"))
MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "1"))
QUEUE_CHECK_INTERVAL = int(os.getenv("QUEUE_CHECK_INTERVAL", "5"))
QUEUE_UPDATE_INTERVAL = int(os.getenv("QUEUE_UPDATE_INTERVAL", "10"))

# Dicionário para armazenar o estado das tarefas
tasks_results = {}

async def execute_sync_search(region: str, business_type: str, keywords: str, max_results: int) -> Dict[str, Any]:
    """
    Executa uma busca síncrona (bloqueante) e retorna os resultados diretamente.
    Ideal para buscas pequenas e rápidas.
    """
    try:
        # Limita o número máximo de resultados para buscas síncronas
        max_results = min(max_results, 50)
        
        # Executa o scraping diretamente
        results = await scrape_google_maps(
            region=region,
            business_type=business_type,
            max_results=max_results,
            keywords=keywords
        )
        
        return {
            "message": f"Busca concluída com sucesso. {len(results)} resultados encontrados.",
            "params": {
                "region": region,
                "business_type": business_type,
                "keywords": keywords,
                "max_results": max_results
            },
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        log_exception(f"Erro na busca síncrona: {str(e)}")
        raise

async def enqueue_search(region: str, business_type: str, keywords: str, max_results: int) -> Dict[str, Any]:
    """
    Adiciona uma nova busca à fila de processamento e retorna imediatamente.
    Ideal para buscas maiores que serão processadas em background.
    """
    try:
        # Insere a busca no banco de dados com status "waiting"
        busca_id = await insert_busca(
            regiao=region,
            tipo_empresa=business_type,
            palavras_chave=keywords,
            qtd_max=max_results,
            status="waiting"
        )
        
        return {
            "message": f"Busca adicionada à fila de processamento com ID {busca_id}",
            "busca_id": busca_id,
            "params": {
                "region": region,
                "business_type": business_type,
                "keywords": keywords,
                "max_results": max_results
            },
            "status": "waiting"
        }
    except Exception as e:
        log_exception(f"Erro ao adicionar busca à fila: {str(e)}")
        raise

async def get_search_status(busca_id: int) -> Dict[str, Any]:
    """
    Verifica o status atual de uma busca por ID.
    """
    try:
        # Obtém os detalhes da busca
        busca = await get_busca_by_id(busca_id)
        if not busca:
            raise ValueError(f"Busca com ID {busca_id} não encontrada")
            
        # Obtém os leads já processados
        leads = await get_leads_by_busca_id(busca_id)
        
        return {
            "busca_id": busca_id,
            "status": busca["status"],
            "params": {
                "region": busca["regiao"],
                "business_type": busca["tipo_empresa"],
                "keywords": " ".join(busca["palavras_chave"]) if busca["palavras_chave"] else "",
                "max_results": busca["qtd_max"]
            },
            "processed_count": len(leads),
            "completed": busca["status"] == "concluido"
        }
    except Exception as e:
        log_exception(f"Erro ao verificar status da busca {busca_id}: {str(e)}")
        raise

async def process_search_task(busca_id: int) -> None:
    """
    Processa uma tarefa de busca específica.
    """
    try:
        # Obtém os detalhes da busca
        busca = await get_busca_by_id(busca_id)
        if not busca:
            log_exception(f"Busca com ID {busca_id} não encontrada")
            return
            
        # Atualiza o status para "processing" caso ainda não esteja
        if busca["status"] != "processing":
            await update_busca_status(busca_id, "processing")
            
        log_info(f"Iniciando processamento da busca {busca_id}: {busca['regiao']} - {busca['tipo_empresa']}")
        
        # Executa o scraping
        keywords = " ".join(busca["palavras_chave"]) if busca["palavras_chave"] else ""
        
        results = await scrape_google_maps(
            region=busca["regiao"],
            business_type=busca["tipo_empresa"],
            max_results=busca["qtd_max"],
            keywords=keywords
        )
        
        # Salva os resultados em lotes
        for i in range(0, len(results), BATCH_SIZE):
            batch = results[i:i + BATCH_SIZE]
            await insert_batch_leads(busca_id, batch)
            
        # Atualiza o status para "concluido" (de acordo com a constraint do banco)
        await update_busca_status(busca_id, "concluido")
        
        log_info(f"Busca {busca_id} concluída com sucesso. {len(results)} resultados encontrados.")
        
    except Exception as e:
        log_exception(f"Erro ao processar busca {busca_id}: {str(e)}")
        await update_busca_status(busca_id, "error")

async def queue_worker():
    """
    Worker que monitora a fila de buscas e executa as tarefas pendentes.
    """
    while True:
        try:
            # Busca a próxima tarefa disponível
            busca = await get_next_busca_from_queue()
            
            if busca:
                # Processa a busca em background
                asyncio.create_task(process_search_task(busca["id"]))
                
            # Espera um intervalo antes de verificar novamente
            await asyncio.sleep(QUEUE_CHECK_INTERVAL)
                
        except Exception as e:
            log_exception(f"Erro no worker de fila: {str(e)}")
            # Espera um pouco antes de tentar novamente para não sobrecarregar em caso de erro persistente
            await asyncio.sleep(QUEUE_CHECK_INTERVAL * 2)

async def start_queue_processor(num_workers: int = MAX_CONCURRENT_TASKS):
    """
    Inicia o sistema de processamento em fila com múltiplos workers.
    """
    workers = []
    log_info(f"Iniciando {num_workers} workers para processamento em fila")
    
    for i in range(num_workers):
        worker = asyncio.create_task(queue_worker())
        workers.append(worker)
        
    return workers
