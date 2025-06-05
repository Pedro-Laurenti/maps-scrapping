from fastapi import Depends, HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
from typing import Optional, Dict, Any
import asyncpg
import os
from datetime import datetime, timedelta
import secrets
import hashlib
from src.utils import log_exception, with_connection

# Cabeçalho para verificação da API Key
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

async def create_api_key_table():
    """
    Cria a tabela de API Keys no banco de dados se não existir
    """
    try:
        async def create_table(conn):
            # Verifica se a tabela já existe
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = $1)",
                "api_keys"
            )
            
            if not exists:
                # Cria a tabela
                await conn.execute("""
                    CREATE TABLE api_keys (
                        id SERIAL PRIMARY KEY,
                        key_hash TEXT NOT NULL UNIQUE,
                        name TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        expires_at TIMESTAMP,
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        last_used_at TIMESTAMP,
                        use_count INTEGER NOT NULL DEFAULT 0,
                        allowed_ips TEXT[]
                    )
                """)
                print("Tabela api_keys criada com sucesso!")
            else:
                print("Tabela api_keys já existe.")
        
        from src.utils import with_connection
        await with_connection(create_table)
        return True
    except Exception as e:
        log_exception(f"Erro ao criar tabela de API Keys: {str(e)}")
        return False

async def generate_api_key(name: str, expires_days: int = 365, allowed_ips: list = None) -> Dict[str, Any]:
    """
    Gera uma nova API Key e a armazena no banco de dados
    """
    try:
        # Gera um token aleatório seguro
        api_key = secrets.token_urlsafe(32)
        
        # Calcula o hash do token para armazenar no banco
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Define a data de expiração
        expires_at = datetime.now() + timedelta(days=expires_days) if expires_days else None
        
        async def store_key(conn):
            # Insere a chave no banco
            query = """
                INSERT INTO api_keys (key_hash, name, created_at, expires_at, allowed_ips)
                VALUES ($1, $2, NOW(), $3, $4)
                RETURNING id, name, created_at, expires_at
            """
            record = await conn.fetchrow(query, key_hash, name, expires_at, allowed_ips)
            
            # Retorna os detalhes da chave criada
            return {
                "id": record["id"],
                "name": record["name"],
                "api_key": api_key,  # Inclui a chave em texto claro na resposta
                "created_at": record["created_at"],
                "expires_at": record["expires_at"]
            }
        
        return await with_connection(store_key)
    except Exception as e:
        log_exception(f"Erro ao gerar API Key: {str(e)}")
        raise

async def validate_api_key(api_key: str = Security(API_KEY_HEADER), client_ip: str = None) -> bool:
    """
    Valida uma API Key e atualiza métricas de uso
    """
    if not api_key:
        return False
    
    try:
        # Calcula o hash da API key recebida
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        async def validate(conn):
            # Busca a chave no banco de dados
            query = """
                SELECT id, expires_at, is_active, allowed_ips
                FROM api_keys
                WHERE key_hash = $1
            """
            record = await conn.fetchrow(query, key_hash)
            
            # Se a chave não existe, retorna False
            if not record:
                return False
            
            # Verifica se a chave está ativa
            if not record["is_active"]:
                return False
            
            # Verifica se a chave não expirou
            if record["expires_at"] and datetime.now() > record["expires_at"]:
                return False
            
            # Verifica restrição de IP, se configurada
            if record["allowed_ips"] and client_ip and client_ip not in record["allowed_ips"]:
                return False
            
            # Atualiza métricas de uso
            update_query = """
                UPDATE api_keys
                SET last_used_at = NOW(), use_count = use_count + 1
                WHERE id = $1
            """
            await conn.execute(update_query, record["id"])
            
            return True
        
        return await with_connection(validate)
    except Exception as e:
        log_exception(f"Erro ao validar API Key: {str(e)}")
        return False

async def get_api_keys(active_only: bool = False) -> list:
    """
    Lista todas as API Keys cadastradas
    """
    try:
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
    except Exception as e:
        log_exception(f"Erro ao buscar API Keys: {str(e)}")
        return []

async def revoke_api_key(key_id: int) -> bool:
    """
    Revoga (desativa) uma API Key
    """
    try:
        async def revoke(conn):
            query = """
                UPDATE api_keys
                SET is_active = FALSE
                WHERE id = $1
                RETURNING id
            """
            record = await conn.fetchrow(query, key_id)
            return bool(record)
        
        return await with_connection(revoke)
    except Exception as e:
        log_exception(f"Erro ao revogar API Key: {str(e)}")
        return False

# Dependência para uso nos endpoints da API
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
