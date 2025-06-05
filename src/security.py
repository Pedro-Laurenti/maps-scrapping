from fastapi import Depends, HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import secrets
import hashlib
from src.utils import (
    log_exception, with_connection, handle_exceptions, log_info, log_warning
)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

@handle_exceptions(message="Erro ao gerar API Key", default_return=None)
async def generate_api_key(name: str, expires_days: int = 365, allowed_ips: list = None) -> Dict[str, Any]:
    """
    Gera uma nova API Key e a armazena no banco de dados
    """
    api_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    expires_at = datetime.now() + timedelta(days=expires_days) if expires_days else None
    
    async def store_key(conn):
        query = """
            INSERT INTO api_keys (key_hash, name, created_at, expires_at, allowed_ips)
            VALUES ($1, $2, NOW(), $3, $4)
            RETURNING id, name, created_at, expires_at
        """
        record = await conn.fetchrow(query, key_hash, name, expires_at, allowed_ips)
        
        result = {
            "id": record["id"],
            "name": record["name"],
            "api_key": api_key,
            "created_at": record["created_at"],
            "expires_at": record["expires_at"]
        }
        log_info(f"Nova API key gerada para: {name}")
        
        return result
    
    return await with_connection(store_key)

@handle_exceptions(message="Erro ao validar API Key", default_return=False)
async def validate_api_key(api_key: str = Security(API_KEY_HEADER), client_ip: str = None) -> bool:
    """
    Valida uma API Key e atualiza métricas de uso
    """
    if not api_key:
        return False
    
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    async def validate(conn):
        query = """
            SELECT id, expires_at, is_active, allowed_ips
            FROM api_keys
            WHERE key_hash = $1
        """
        record = await conn.fetchrow(query, key_hash)
        
        if not record:
            log_warning(f"Tentativa de uso de API Key inexistente")
            return False
        
        if not record["is_active"]:
            log_warning(f"Tentativa de uso de API Key inativa (ID: {record['id']})")
            return False
        
        if record["expires_at"] and datetime.now() > record["expires_at"]:
            log_warning(f"Tentativa de uso de API Key expirada (ID: {record['id']})")
            return False
        
        if record["allowed_ips"] and client_ip and client_ip not in record["allowed_ips"]:
            log_warning(f"Tentativa de uso de API Key de IP não autorizado: {client_ip} (ID: {record['id']})")
            return False
        
        update_query = """
            UPDATE api_keys
            SET last_used_at = NOW(), use_count = use_count + 1
            WHERE id = $1
        """
        await conn.execute(update_query, record["id"])
        
        return True
    
    return await with_connection(validate)

@handle_exceptions(message="Erro ao buscar API Keys", default_return=[])
async def get_api_keys(active_only: bool = False) -> list:
    """
    Lista todas as API Keys cadastradas
    """
    async def fetch_keys(conn):
        query = """
            SELECT id, name, created_at, expires_at, is_active, last_used_at, use_count
            FROM api_keys
        """
        
        if active_only:
            query += " WHERE is_active = TRUE"
            
        records = await conn.fetch(query)
        return [dict(r) for r in records]
    
    return await with_connection(fetch_keys)

@handle_exceptions(message="Erro ao revogar API Key", default_return=False)
async def revoke_api_key(key_id: int) -> bool:
    """
    Revoga (desativa) uma API Key
    """
    async def revoke(conn):
        query = """
            UPDATE api_keys
            SET is_active = FALSE
            WHERE id = $1
            RETURNING id
        """
        record = await conn.fetchrow(query, key_id)
        
        if record:
            log_info(f"API Key ID {key_id} foi revogada")
            
        return bool(record)
    
    return await with_connection(revoke)

async def get_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """
    Dependência para validar a API Key nos endpoints
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key não fornecida"
        )
    
    is_valid = await validate_api_key(api_key)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API Key inválida ou expirada"
        )
    
    return api_key
