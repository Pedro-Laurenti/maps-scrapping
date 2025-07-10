-- =================================================
-- EXEMPLOS DE USO DA NOVA ESTRUTURA DE MENSAGENS
-- =================================================

-- 1. INSERIR UMA NOVA MENSAGEM DE IA
-- Primeiro insere na tabela principal
INSERT INTO mensagens (instancia_id, lead_id, tipo_emissor, ordem_conversa)
VALUES (1, 123, 'ia', 1);

-- Depois insere os detalhes da IA (usando o ID retornado)
INSERT INTO mensagens_ia (
    mensagem_id, conteudo, modelo_llm, prompt_tokens, 
    completion_tokens, total_tokens, estimated_cost, temperatura
)
VALUES (
    CURRVAL('mensagens_id_seq'), 
    'Olá! Como posso ajudá-lo hoje?',
    'gpt-4o-mini',
    620, 56, 676, 0.0000214, 0.7
);

-- 2. INSERIR UMA RESPOSTA DO LEAD
INSERT INTO mensagens (instancia_id, lead_id, tipo_emissor, ordem_conversa)
VALUES (1, 123, 'lead', 2);

INSERT INTO mensagens_lead (mensagem_id, conteudo, tipo_conteudo)
VALUES (CURRVAL('mensagens_id_seq'), 'Oi, tenho interesse no seu serviço', 'texto');

-- 3. CONSULTAR CONVERSA COMPLETA DE UM LEAD
SELECT 
    ordem_conversa,
    tipo_emissor,
    conteudo,
    data_criacao,
    CASE WHEN tipo_emissor = 'ia' THEN 
        CONCAT('Tokens: ', total_tokens, ' | Custo: $', estimated_cost)
    END as detalhes_ia
FROM vw_conversa_completa 
WHERE lead_id = 123 
ORDER BY ordem_conversa;

-- 4. RELATÓRIO DE CUSTOS POR CLIENTE NO MÊS
SELECT 
    cliente_nome,
    total_mensagens_ia,
    total_tokens,
    custo_total,
    custo_medio_mensagem
FROM vw_relatorio_uso_ia 
WHERE mes_ano = DATE_TRUNC('month', NOW())
ORDER BY custo_total DESC;

-- 5. VERIFICAR LIMITES DE UM CLIENTE
SELECT verificar_limites_uso(1) as status_limites;

-- 6. BUSCAR CONVERSAS MAIS CARAS DO MÊS
SELECT 
    nome_empresa,
    telefone,
    cliente_nome,
    total_mensagens,
    custo_conversa
FROM vw_conversas_ativas 
WHERE custo_conversa > 0
ORDER BY custo_conversa DESC
LIMIT 10;

-- 7. ESTATÍSTICAS DE MODELOS MAIS USADOS
SELECT 
    modelo_llm,
    COUNT(*) as total_usos,
    SUM(total_tokens) as tokens_totais,
    SUM(estimated_cost) as custo_total,
    AVG(tempo_resposta_ms) as tempo_medio_ms
FROM mensagens_ia 
WHERE data_criacao >= NOW() - INTERVAL '30 days'
GROUP BY modelo_llm
ORDER BY total_usos DESC;

-- 8. DEFINIR LIMITES PARA UM CLIENTE
INSERT INTO limites_uso_ia (
    cliente_id, 
    limite_tokens_mes, 
    limite_custo_mes, 
    alerta_percentual, 
    bloqueio_automatico
)
VALUES (1, 1000000, 100.00, 80, TRUE);

-- 9. BUSCAR MENSAGENS COM MAIOR CUSTO
SELECT 
    m.lead_id,
    l.nome_empresa,
    mia.conteudo,
    mia.total_tokens,
    mia.estimated_cost,
    mia.modelo_llm,
    mia.data_criacao
FROM mensagens_ia mia
JOIN mensagens m ON mia.mensagem_id = m.id
JOIN leads l ON m.lead_id = l.id
WHERE mia.estimated_cost > 0.001 -- Mensagens que custaram mais de $0.001
ORDER BY mia.estimated_cost DESC;

-- 10. RELATÓRIO SEMANAL DE PERFORMANCE
SELECT 
    DATE_TRUNC('week', mia.data_criacao) as semana,
    COUNT(*) as total_mensagens,
    SUM(mia.total_tokens) as tokens_utilizados,
    SUM(mia.estimated_cost) as custo_total,
    AVG(mia.tempo_resposta_ms) as tempo_medio_resposta
FROM mensagens_ia mia
WHERE mia.data_criacao >= NOW() - INTERVAL '4 weeks'
GROUP BY DATE_TRUNC('week', mia.data_criacao)
ORDER BY semana DESC;
