from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import uvicorn
from typing import Optional
from src.queue_processor import (
    execute_sync_search
)

app = FastAPI(
    title="Google Maps Scraper API",
    description="API para buscar informações de negócios no Google Maps",
    version="1.0.0"
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
async def scrape(params: ScraperParams):
    """
    Executa uma busca síncrona (bloqueante) e retorna os resultados diretamente.
    Ideal para buscas pequenas e rápidas.
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

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
