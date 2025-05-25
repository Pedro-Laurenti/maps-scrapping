-- Atualiza a tabela buscas para incluir o campo status
ALTER TABLE buscas ADD COLUMN IF NOT EXISTS status TEXT CHECK (status IN ('waiting', 'processing', 'error', 'concluido')) DEFAULT 'waiting';

-- Cria índice para facilitar consultas por status (melhora performance da fila)
CREATE INDEX IF NOT EXISTS idx_buscas_status ON buscas(status);

-- Atualiza registros existentes para ter um status válido
UPDATE buscas SET status = 'concluido' WHERE status IS NULL;

-- Função para obter a próxima busca na fila
CREATE OR REPLACE FUNCTION get_next_busca_in_queue() 
RETURNS TABLE (
    id INTEGER,
    regiao TEXT,
    tipo_empresa TEXT,
    palavras_chave TEXT[],
    qtd_max INTEGER,
    data_busca TIMESTAMP,
    status TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT b.id, b.regiao, b.tipo_empresa, b.palavras_chave, b.qtd_max, b.data_busca, b.status
    FROM buscas b
    WHERE b.status = 'waiting'
    ORDER BY b.id ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED;
END;
$$ LANGUAGE plpgsql;
