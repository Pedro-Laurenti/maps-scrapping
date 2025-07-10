-- =================================================
-- SCRIPT DE MIGRAÇÃO DA ESTRUTURA ANTIGA PARA NOVA
-- =================================================

-- ATENÇÃO: Execute este script com cuidado em produção
-- Faça backup da base de dados antes de executar

-- 1. Criar backup da tabela original
CREATE TABLE mensagens_backup AS SELECT * FROM mensagens;

-- 2. Migrar dados da estrutura antiga para a nova

-- Primeiro, criar as novas mensagens principais
WITH mensagens_ordenadas AS (
    SELECT 
        *,
        ROW_NUMBER() OVER (PARTITION BY lead_id, instancia_id ORDER BY data_criacao) as ordem
    FROM mensagens_backup
)
INSERT INTO mensagens (id, instancia_id, lead_id, tipo_emissor, status, ordem_conversa, data_criacao)
SELECT 
    id,
    instancia_id,
    lead_id,
    emissor as tipo_emissor,
    status,
    ordem,
    data_criacao
FROM mensagens_ordenadas;

-- Resetar a sequência para evitar conflitos
SELECT setval('mensagens_id_seq', (SELECT MAX(id) FROM mensagens) + 1);

-- 3. Migrar mensagens de IA (assumindo valores padrão para campos novos)
INSERT INTO mensagens_ia (mensagem_id, conteudo, modelo_llm, prompt_tokens, completion_tokens, total_tokens, estimated_cost)
SELECT 
    m.id,
    mb.conteudo,
    'legacy-model', -- Modelo padrão para dados migrados
    0, -- Tokens não disponíveis nos dados antigos
    0,
    0,
    0.0
FROM mensagens m
JOIN mensagens_backup mb ON m.id = mb.id
WHERE m.tipo_emissor = 'ia';

-- 4. Migrar mensagens de leads
INSERT INTO mensagens_lead (mensagem_id, conteudo, tipo_conteudo)
SELECT 
    m.id,
    mb.conteudo,
    'texto'
FROM mensagens m
JOIN mensagens_backup mb ON m.id = mb.id
WHERE m.tipo_emissor = 'lead';

-- 5. Verificar integridade da migração
SELECT 
    'Total mensagens originais' as tipo,
    COUNT(*) as quantidade
FROM mensagens_backup
UNION ALL
SELECT 
    'Total mensagens migradas',
    COUNT(*)
FROM mensagens
UNION ALL
SELECT 
    'Mensagens IA migradas',
    COUNT(*)
FROM mensagens_ia
UNION ALL
SELECT 
    'Mensagens Lead migradas',
    COUNT(*)
FROM mensagens_lead;

-- 6. Teste de integridade - deve retornar 0 se tudo estiver correto
SELECT COUNT(*) as mensagens_sem_detalhes
FROM mensagens m
LEFT JOIN mensagens_ia mia ON m.id = mia.mensagem_id
LEFT JOIN mensagens_lead ml ON m.id = ml.mensagem_id
WHERE mia.id IS NULL AND ml.id IS NULL;

-- 7. Comparação de dados antes e depois
SELECT 
    'Antes da migração' as momento,
    emissor,
    COUNT(*) as total
FROM mensagens_backup
GROUP BY emissor
UNION ALL
SELECT 
    'Depois da migração',
    tipo_emissor,
    COUNT(*)
FROM mensagens
GROUP BY tipo_emissor
ORDER BY momento, emissor;

-- 8. Após confirmar que a migração está correta, você pode:
-- DROP TABLE mensagens_backup; -- CUIDADO: só execute após confirmar que está tudo OK

-- 9. Inserir dados iniciais para controle de custos
INSERT INTO custos_ia_resumo (cliente_id, mes_ano, total_tokens_utilizados, total_custo_estimado, total_mensagens)
SELECT 
    i.cliente_id,
    DATE_TRUNC('month', m.data_criacao)::DATE,
    0, -- Tokens zerados pois não temos histórico
    0, -- Custo zerado pois não temos histórico
    COUNT(*)
FROM mensagens m
JOIN instancias i ON m.instancia_id = i.id
WHERE m.tipo_emissor = 'ia'
GROUP BY i.cliente_id, DATE_TRUNC('month', m.data_criacao)
ON CONFLICT (cliente_id, mes_ano) DO NOTHING;

COMMIT;
