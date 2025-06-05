import asyncio
import os
import time
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

from src.database import (
    insert_busca, insert_leads, get_leads_by_busca_id, 
    update_busca_status, get_busca_by_id, get_connection
)
from src.crawler import scrape_google_maps
from src.utils import log_info, log_exception

load_dotenv()

# Definições de ambiente
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "20"))
MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "3"))
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
