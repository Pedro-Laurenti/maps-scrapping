from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
import uvicorn
from typing import Optional, Dict, Any
from src.queue_processor import (
    execute_sync_search, enqueue_search, get_search_status,
    start_queue_processor
)
from src.security import get_api_key
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # No início da aplicação
    print(f"\n{'='*60}")
    print(f" API pronta para receber requisições")
    print(f" Lembre-se de fornecer uma API Key válida no cabeçalho X-API-Key")
    print(f"{'='*60}\n")
    yield

app = FastAPI(
    title="Google Maps Scraper API",
    description="API para buscar informações de negócios no Google Maps",
    version="1.0.0",
    lifespan=lifespan
)

class ScraperParams(BaseModel):
    region: str
    business_type: str
    max_results: int = 10
    keywords: Optional[str] = ""

class BusinessResult(BaseModel):
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    url: Optional[str] = None

@app.post("/scrape")
async def scrape(params: ScraperParams, api_key: str = Depends(get_api_key)):
    """
    Executa uma busca síncrona (bloqueante) e retorna os resultados diretamente.
    Ideal para buscas pequenas e rápidas.
    
    Requer uma API Key válida no cabeçalho X-API-Key.
    """
    try:
        # Usa a função do queue_processor para executar a busca síncrona
        results = await execute_sync_search(
            region=params.region,
            business_type=params.business_type,
            keywords=params.keywords,
            max_results=params.max_results
        )
        
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/scrape/async")
async def scrape_async(params: ScraperParams, api_key: str = Depends(get_api_key)):
    """
    Adiciona uma busca à fila de processamento para ser executada de forma assíncrona.
    Retorna imediatamente com um ID de busca para verificação posterior.
    Ideal para buscas maiores que não precisam de resposta imediata.
    
    Requer uma API Key válida no cabeçalho X-API-Key.
    """
    try:
        # Adiciona a busca à fila de processamento
        result = await enqueue_search(
            region=params.region,
            business_type=params.business_type,
            keywords=params.keywords,
            max_results=params.max_results
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/scrape/status/{busca_id}")
async def get_scrape_status(busca_id: int, api_key: str = Depends(get_api_key)):
    """
    Verifica o status de uma busca assíncrona pelo ID.
    Retorna detalhes sobre o progresso e conclusão da busca.
    
    Requer uma API Key válida no cabeçalho X-API-Key.
    """
    try:
        status = await get_search_status(busca_id)
        return status
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Classes relacionadas à manipulação de API Keys foram removidas

# Os endpoints para manipulação de API keys foram removidos pois são gerenciados por outra solução
# A validação de API keys nos headers das requisições foi mantida

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
