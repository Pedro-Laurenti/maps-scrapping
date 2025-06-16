from fastapi import HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
from datetime import datetime
import hashlib
from src.utils import (
    with_connection, handle_exceptions, log_warning
)

# Definição do cabeçalho da API Key
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

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

# As funções de gerenciamento de API keys (get_api_keys e revoke_api_key) foram removidas
# pois são gerenciadas por outra solução

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
