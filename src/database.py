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
    conn = await get_connection()
    try:
        # Converte a string de palavras-chave em um array PostgreSQL
        palavras_array = palavras_chave.split() if palavras_chave else []
        
        # Insere a busca e retorna o ID gerado
        query = """
            INSERT INTO buscas (campanha_id, regiao, tipo_empresa, palavras_chave, qtd_max, data_busca, status)
            VALUES (NULL, $1, $2, $3, $4, NOW(), $5)
            RETURNING id
        """
        busca_id = await conn.fetchval(query, regiao, tipo_empresa, palavras_array, qtd_max, status)
        return busca_id
    finally:
        await conn.close()

async def insert_leads(busca_id: int, leads: List[Dict[str, Any]]) -> List[int]:
    """
    Insere múltiplos leads no banco de dados e retorna os IDs gerados
    """
    conn = await get_connection()
    try:
        # Prepara os valores para inserção em lote
        lead_ids = []
        for lead in leads:
            query = """
                INSERT INTO leads (busca_id, nome_empresa, nome_lead, telefone, 
                                  localizacao, avaliacao_media, reviews, tipo_empresa)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
            """            # Converte rating para float, garantindo que seja um número válido
            rating = lead.get("rating")
            try:
                if rating is not None:
                    # Se for string, substitui vírgula por ponto e converte para float
                    if isinstance(rating, str):
                        rating = float(rating.replace(",", "."))
                    else:
                        rating = float(rating)
                else:
                    rating = 0.0
            except (ValueError, TypeError):
                # Em caso de erro na conversão, usa o valor padrão
                rating = 0.0
                  # Converte reviews_count para inteiro
            reviews_count = lead.get("reviews_count", 0)
            try:
                if reviews_count is not None:
                    # Remove possíveis formatações como "1.234" ou "1,234"
                    if isinstance(reviews_count, str):
                        reviews_count = reviews_count.replace(".", "").replace(",", "")
                    reviews_count = int(reviews_count)
                else:
                    reviews_count = 0
            except (ValueError, TypeError):
                reviews_count = 0
              # Formata o número de telefone (remove espaços, parênteses e adiciona código BR 55)
            phone = lead.get("phone", "")
            if phone:
                # Remove caracteres não numéricos
                phone = ''.join(filter(str.isdigit, phone))
                
                # Se o número já começar com 55, mantém como está
                if not phone.startswith('55'):
                    # Se começar com 0, remove o zero inicial
                    if phone.startswith('0'):
                        phone = phone[1:]
                    
                    # Adiciona o código do Brasil (55)
                    phone = '55' + phone
            
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
    finally:
        await conn.close()

async def get_busca_by_id(busca_id: int) -> Optional[Dict[str, Any]]:
    """
    Recupera uma busca pelo ID
    """
    conn = await get_connection()
    try:
        query = "SELECT * FROM buscas WHERE id = $1"
        row = await conn.fetchrow(query, busca_id)
        if row:
            return dict(row)
        return None
    finally:
        await conn.close()

async def get_leads_by_busca_id(busca_id: int) -> List[Dict[str, Any]]:
    """
    Recupera todos os leads de uma determinada busca
    """
    conn = await get_connection()
    try:
        query = "SELECT * FROM leads WHERE busca_id = $1"
        rows = await conn.fetch(query, busca_id)
        return [dict(row) for row in rows]
    finally:
        await conn.close()

async def update_busca_status(busca_id: int, status: str) -> bool:
    """
    Atualiza o status de uma busca
    """
    conn = await get_connection()
    try:
        query = """
            UPDATE buscas SET status = $1 
            WHERE id = $2
        """
        result = await conn.execute(query, status, busca_id)
        return 'UPDATE' in result
    finally:
        await conn.close()

async def get_next_busca_from_queue() -> Optional[Dict[str, Any]]:
    """
    Retorna a próxima busca na fila de processamento e atualiza seu status para "processing"
    
    Esta função usa um bloqueio de linha (row lock) com FOR UPDATE SKIP LOCKED para garantir
    que somente um worker pegue cada tarefa, mesmo em ambientes com múltiplos workers.
    """
    conn = await get_connection()
    try:
        # Usa transação para garantir que nenhum outro processo pegue a mesma busca
        async with conn.transaction():
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
                
                import logging
                logging.info(f"Iniciando processamento da busca {busca_dict['id']}: {busca_dict['regiao']} - {busca_dict['tipo_empresa']}")
                
                return busca_dict
        
        return None
    finally:
        await conn.close()

async def insert_batch_leads(busca_id: int, leads_batch: List[Dict[str, Any]]) -> List[int]:
    """
    Insere um lote de leads no banco e retorna os IDs gerados
    """
    if not leads_batch:
        return []
    
    return await insert_leads(busca_id, leads_batch)
