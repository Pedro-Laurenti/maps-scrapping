import asyncpg
from typing import List, Dict, Any, Optional

# Configuração do banco de dados
DB_CONFIG = {
    "host": "168.231.99.240",
    "port": 6071,
    "database": "privado",
    "user": "admin",
    "password": "789456123"
}

async def get_connection():
    """Estabelece conexão com o banco de dados PostgreSQL"""
    return await asyncpg.connect(**DB_CONFIG)

async def insert_busca(regiao: str, tipo_empresa: str, palavras_chave: str, 
                      qtd_max: int, status: str = "waiting") -> int:
    """
    Insere uma nova busca no banco de dados e retorna o ID gerado
    """
    from src.utils import with_connection, log_info
    
    async def insert(conn):
        # Converte a string de palavras-chave em um array PostgreSQL
        palavras_array = palavras_chave.split() if palavras_chave else []
        
        # Insere a busca e retorna o ID gerado
        query = """
            INSERT INTO buscas (campanha_id, regiao, tipo_empresa, palavras_chave, qtd_max, data_busca, status)
            VALUES (NULL, $1, $2, $3, $4, NOW(), $5)
            RETURNING id
        """
        busca_id = await conn.fetchval(query, regiao, tipo_empresa, palavras_array, qtd_max, status)
        
        log_info(f"Nova busca inserida: ID {busca_id} - {regiao} - {tipo_empresa} (status: {status})")
        return busca_id
    
    return await with_connection(insert)

async def insert_leads(busca_id: int, leads: List[Dict[str, Any]]) -> List[int]:
    """
    Insere múltiplos leads no banco de dados e retorna os IDs gerados
    """
    from src.utils import with_connection, parse_float, parse_int, format_phone_number
    
    async def insert_lead_batch(conn, leads_data):
        # Prepara os valores para inserção em lote
        lead_ids = []
        for lead in leads_data:
            query = """
                INSERT INTO leads (busca_id, nome_empresa, nome_lead, telefone, 
                                  localizacao, avaliacao_media, reviews, tipo_empresa)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
            """
            # Usa as funções utilitárias para conversão de tipos
            rating = parse_float(lead.get("rating"), 0.0)
            reviews_count = parse_int(lead.get("reviews_count"), 0)
            phone = format_phone_number(lead.get("phone", ""))
            
            lead_id = await conn.fetchval(
                query,
                busca_id,
                lead.get("name", ""),
                "",  # nome_lead (não temos esse dado do scraping)
                phone,  # telefone formatado
                lead.get("address", ""),
                rating,  # avaliação média como float
                reviews_count,  # número de reviews como inteiro
                lead.get("business_type", "")
            )
            lead_ids.append(lead_id)
        
        return lead_ids
    
    # Usa a função with_connection para gerenciar a conexão
    return await with_connection(lambda conn: insert_lead_batch(conn, leads))

async def get_busca_by_id(busca_id: int) -> Optional[Dict[str, Any]]:
    """
    Recupera uma busca pelo ID
    """
    from src.utils import with_connection
    
    async def fetch_busca(conn):
        query = "SELECT * FROM buscas WHERE id = $1"
        row = await conn.fetchrow(query, busca_id)
        if row:
            return dict(row)
        return None
    
    return await with_connection(fetch_busca)

async def get_leads_by_busca_id(busca_id: int) -> List[Dict[str, Any]]:
    """
    Recupera todos os leads de uma determinada busca
    """
    from src.utils import with_connection
    
    async def fetch_leads(conn):
        query = "SELECT * FROM leads WHERE busca_id = $1"
        rows = await conn.fetch(query, busca_id)
        return [dict(row) for row in rows]
    
    return await with_connection(fetch_leads)

async def update_busca_status(busca_id: int, status: str) -> bool:
    """
    Atualiza o status de uma busca
    """
    from src.utils import with_connection, log_info
    
    async def update_status(conn):
        query = """
            UPDATE buscas SET status = $1 
            WHERE id = $2
        """
        result = await conn.execute(query, status, busca_id)
        success = 'UPDATE' in result
        if success:
            log_info(f"Atualizado status da busca {busca_id} para '{status}'")
        return success
    
    return await with_connection(update_status)

async def get_next_busca_from_queue() -> Optional[Dict[str, Any]]:
    """
    Retorna a próxima busca na fila de processamento e atualiza seu status para "processing"
    
    Esta função usa um bloqueio de linha (row lock) com FOR UPDATE SKIP LOCKED para garantir
    que somente um worker pegue cada tarefa, mesmo em ambientes com múltiplos workers.
    """
    from src.utils import with_connection, db_transaction
    import logging
    
    async def get_next_task(conn):
        # Usa transação para garantir que nenhum outro processo pegue a mesma busca
        async with db_transaction(conn):
            # Seleciona a próxima tarefa em espera - não verifica mais se há tarefas em processamento
            # para permitir que as tarefas sejam iniciadas automaticamente
            query = """
                SELECT * FROM buscas 
                WHERE status = 'waiting' 
                ORDER BY id ASC 
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            """
            row = await conn.fetchrow(query)
            if row:
                busca_dict = dict(row)
                
                # Atualiza o status para "processing"
                update_query = """
                    UPDATE buscas SET status = 'processing' 
                    WHERE id = $1
                """
                await conn.execute(update_query, busca_dict['id'])
                
                logging.info(f"Iniciando processamento da busca {busca_dict['id']}: {busca_dict['regiao']} - {busca_dict['tipo_empresa']}")
                
                return busca_dict
        
        return None
    
    return await with_connection(get_next_task)

async def insert_batch_leads(busca_id: int, leads_batch: List[Dict[str, Any]]) -> List[int]:
    """
    Insere um lote de leads no banco e retorna os IDs gerados
    """
    from src.utils import log_info
    
    if not leads_batch:
        return []
    
    lead_ids = await insert_leads(busca_id, leads_batch)
    log_info(f"Inseridos {len(lead_ids)} leads para busca ID {busca_id}")
    
    return lead_ids
