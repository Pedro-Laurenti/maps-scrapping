from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Security, status
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
import uvicorn
import asyncio
import secrets
from typing import Optional, List, Dict, Any
from src.queue_processor import (
    execute_sync_search, enqueue_search, get_search_status,
    start_queue_processor
)
from src.security import (
    get_api_key, create_api_key_table, generate_api_key, 
    revoke_api_key, get_api_keys
)

app = FastAPI(
    title="Google Maps Scraper API",
    description="API para buscar informações de negócios no Google Maps",
    version="1.0.0"
)

# Inicializa a tabela de API keys ao iniciar o aplicativo
@app.on_event("startup")
async def startup():
    # Cria a tabela de API Keys se não existir
    await create_api_key_table()
    
    # Verifica se existe alguma API Key ativa
    keys = await get_api_keys(active_only=True)
    
    # Se não existir nenhuma API Key ativa, cria uma padrão
    if not keys:
        import os
        from dotenv import load_dotenv
        
        # Recarrega as variáveis de ambiente para garantir que temos os valores mais recentes
        load_dotenv()
        
        # Obtém configurações do arquivo .env
        default_name = os.getenv("DEFAULT_API_KEY_NAME", "API Default")
        default_expires = int(os.getenv("DEFAULT_API_KEY_EXPIRES_DAYS", "365"))
        default_ips_str = os.getenv("DEFAULT_API_KEY_ALLOWED_IPS", "")
        
        # Converte string de IPs para lista (se não estiver vazia)
        default_ips = [ip.strip() for ip in default_ips_str.split(",")] if default_ips_str else None
        
        # Cria a API Key padrão
        key_info = await generate_api_key(
            name=default_name,
            expires_days=default_expires,
            allowed_ips=default_ips
        )
        
        print(f"\n{'='*60}")
        print(f" API KEY GERADA: {key_info['api_key']}")
        print(f" GUARDE ESTA CHAVE EM LOCAL SEGURO!")
        print(f" Nome: {key_info['name']}")
        print(f" Criada em: {key_info['created_at']}")
        print(f" Expira em: {key_info['expires_at']}")
        print(f"{'='*60}\n")

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

class APIKeyRequest(BaseModel):
    name: str
    expires_days: Optional[int] = 365  # Validade em dias, padrão de 1 ano
    allowed_ips: Optional[List[str]] = None  # Lista de IPs permitidos (opcional)

class RevokeRequest(BaseModel):
    key_id: int

# Endpoints para gerenciar API Keys (com proteção especial)
@app.post("/admin/api-keys", status_code=status.HTTP_201_CREATED)
async def create_key(request: APIKeyRequest):
    """
    Cria uma nova API Key.
    
    Este endpoint deve ser protegido por senha ou estar em uma rede segura.
    Em um ambiente de produção, seria melhor adicionar autenticação adicional aqui.
    """
    try:
        result = await generate_api_key(
            name=request.name,
            expires_days=request.expires_days,
            allowed_ips=request.allowed_ips
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/api-keys")
async def list_keys(active_only: bool = False):
    """
    Lista todas as API Keys.
    
    Este endpoint deve ser protegido por senha ou estar em uma rede segura.
    Em um ambiente de produção, seria melhor adicionar autenticação adicional aqui.
    """
    try:
        keys = await get_api_keys(active_only)
        return {"keys": keys, "count": len(keys)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/api-keys/revoke")
async def revoke_key(request: RevokeRequest):
    """
    Revoga (desativa) uma API Key.
    
    Este endpoint deve ser protegido por senha ou estar em uma rede segura.
    Em um ambiente de produção, seria melhor adicionar autenticação adicional aqui.
    """
    try:
        success = await revoke_api_key(request.key_id)
        if not success:
            raise HTTPException(status_code=404, detail="API Key não encontrada")
        return {"message": "API Key revogada com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
