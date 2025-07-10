/* =================================================
 * EXEMPLOS DE CONSULTAS ÚTEIS
 * =================================================
 * Exemplos práticos de como usar as views e consultas
 * para extrair insights do sistema
 * ================================================= */

-- =================================================
-- 1. MONITORAMENTO DE CUSTOS
-- =================================================

-- Custo total por cliente no mês atual
SELECT 
    cliente_nome,
    custo_total,
    total_mensagens,
    custo_medio_mensagem,
    leads_contactados
FROM vw_custos_mensais_cliente 
WHERE mes_referencia = DATE_TRUNC('month', CURRENT_DATE)
ORDER BY custo_total DESC;

-- Top 5 instâncias que mais gastaram ontem
SELECT 
    nome_instancia,
    nome_sdr,
    cliente_nome,
    custo_total,
    mensagens_enviadas,
    tokens_totais
FROM vw_custos_diarios_instancia 
WHERE data = CURRENT_DATE - INTERVAL '1 day'
ORDER BY custo_total DESC 
LIMIT 5;

-- Análise de custo por token ao longo do tempo
SELECT 
    DATE(data_criacao) as data,
    COUNT(*) as mensagens,
    SUM(total_tokens) as tokens_totais,
    SUM(estimated_cost) as custo_total,
    ROUND(SUM(estimated_cost) / SUM(total_tokens) * 1000, 6) as custo_por_1k_tokens
FROM mensagens_ia 
WHERE data_criacao >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(data_criacao)
ORDER BY data DESC;

-- =================================================
-- 2. ANÁLISE DE PERFORMANCE DE CAMPANHAS
-- =================================================

-- Campanhas com melhor ROI (taxa de resposta vs custo)
SELECT 
    campanha_id,
    cliente_nome,
    nome_instancia,
    total_leads,
    leads_contactados,
    leads_que_responderam,
    taxa_resposta_pct,
    custo_total,
    ROUND(custo_total / NULLIF(leads_que_responderam, 0), 2) as custo_por_resposta
FROM vw_performance_campanhas
WHERE campanha_status = 'active'
ORDER BY taxa_resposta_pct DESC, custo_por_resposta ASC;

-- Campanhas que precisam de atenção (baixa performance)
SELECT 
    campanha_id,
    cliente_nome,
    total_leads,
    leads_contactados,
    leads_que_responderam,
    taxa_resposta_pct,
    custo_total
FROM vw_performance_campanhas
WHERE taxa_resposta_pct < 5 -- Menos de 5% de resposta
   OR (leads_contactados > 50 AND leads_que_responderam = 0) -- Muitos contatos, zero respostas
ORDER BY custo_total DESC;

-- =================================================
-- 3. ANÁLISE DE LEADS E ENGAJAMENTO
-- =================================================

-- Leads mais promissores (alto engajamento + boa avaliação)
SELECT 
    nome_empresa,
    telefone,
    tipo_empresa,
    localizacao,
    avaliacao_media,
    total_respostas,
    nivel_engajamento,
    ultima_resposta,
    clientes_interesse
FROM vw_leads_engajados
WHERE avaliacao_media >= 4.0 
  AND nivel_engajamento IN ('Alto engajamento', 'Médio engajamento')
ORDER BY total_respostas DESC, avaliacao_media DESC;

-- Leads frios que podem precisar de nova abordagem
SELECT 
    l.nome_empresa,
    l.telefone,
    l.tipo_empresa,
    COUNT(mia.id) as mensagens_enviadas,
    COUNT(ml.id) as respostas_recebidas,
    MAX(mia.data_criacao) as ultima_mensagem_enviada,
    EXTRACT(days FROM NOW() - MAX(mia.data_criacao)) as dias_sem_contato
FROM leads l
JOIN mensagens_ia mia ON l.id = mia.lead_id
LEFT JOIN mensagens_lead ml ON l.id = ml.lead_id
WHERE ml.id IS NULL -- Sem respostas
  AND mia.data_criacao < NOW() - INTERVAL '7 days' -- Última mensagem há mais de 7 dias
GROUP BY l.id, l.nome_empresa, l.telefone, l.tipo_empresa
HAVING COUNT(mia.id) BETWEEN 1 AND 3 -- Entre 1 e 3 tentativas
ORDER BY dias_sem_contato DESC;

-- =================================================
-- 4. OTIMIZAÇÃO DE HORÁRIOS
-- =================================================

-- Melhores horários para envio (baseado em respostas)
SELECT 
    hora_resposta,
    nome_dia_semana,
    total_respostas,
    leads_unicos,
    ROUND(total_respostas::DECIMAL / leads_unicos, 2) as media_respostas_por_lead
FROM vw_analise_horarios_resposta
WHERE total_respostas >= 5 -- Pelo menos 5 respostas para ser significativo
ORDER BY total_respostas DESC;

-- Distribuição de respostas por dia da semana
SELECT 
    nome_dia_semana,
    SUM(total_respostas) as respostas_total,
    COUNT(DISTINCT hora_resposta) as horas_ativas,
    AVG(total_respostas) as media_respostas_por_hora
FROM vw_analise_horarios_resposta
GROUP BY dia_semana, nome_dia_semana
ORDER BY dia_semana;

-- =================================================
-- 5. SEGMENTAÇÃO E TARGETING
-- =================================================

-- Tipos de empresa com melhor conversão
SELECT 
    tipo_empresa,
    total_leads,
    leads_que_responderam,
    taxa_resposta_pct,
    avaliacao_media,
    regioes_diferentes
FROM vw_ranking_tipos_empresa
WHERE taxa_resposta_pct > 10 -- Mais de 10% de resposta
ORDER BY taxa_resposta_pct DESC;

-- Análise por região (cidades com melhor engajamento)
SELECT 
    l.localizacao,
    COUNT(DISTINCT l.id) as total_leads,
    COUNT(DISTINCT ml.lead_id) as leads_responderam,
    ROUND((COUNT(DISTINCT ml.lead_id)::DECIMAL / COUNT(DISTINCT l.id)) * 100, 2) as taxa_resposta,
    AVG(l.avaliacao_media) as avaliacao_media,
    COUNT(DISTINCT l.tipo_empresa) as tipos_empresa_diferentes
FROM leads l
LEFT JOIN mensagens_lead ml ON l.id = ml.lead_id
WHERE l.localizacao IS NOT NULL
GROUP BY l.localizacao
HAVING COUNT(DISTINCT l.id) >= 10 -- Pelo menos 10 leads na região
ORDER BY taxa_resposta DESC, total_leads DESC;

-- =================================================
-- 6. ALERTAS E MONITORAMENTO
-- =================================================

-- Instâncias que precisam de atenção
SELECT 
    nome_instancia,
    nome_sdr,
    cliente_nome,
    status,
    alerta,
    ultima_atividade,
    mensagens_ultimos_7_dias
FROM vw_alertas_instancias
ORDER BY 
    CASE alerta
        WHEN 'Instância bloqueada' THEN 1
        WHEN 'Instância desativada' THEN 2
        WHEN 'Sem atividade há mais de 7 dias' THEN 3
        WHEN 'Sem mensagens nas últimas 24h' THEN 4
        ELSE 5
    END,
    ultima_atividade ASC;

-- Leads com classificações negativas que precisam de atenção
SELECT 
    nome_empresa,
    telefone,
    classificacoes,
    clientes_classificaram,
    ultima_classificacao
FROM vw_classificacoes_leads
WHERE classificacoes ILIKE '%irritado%' 
   OR classificacoes ILIKE '%sem-whatsapp%'
ORDER BY ultima_classificacao DESC;

-- =================================================
-- 7. RELATÓRIOS EXECUTIVOS
-- =================================================

-- Resumo geral do sistema (últimos 30 dias)
SELECT 
    'Métricas Gerais' as categoria,
    COUNT(DISTINCT c.id) as total_clientes,
    COUNT(DISTINCT i.id) as total_instancias,
    COUNT(DISTINCT l.id) as total_leads,
    COUNT(DISTINCT camp.id) as campanhas_ativas
FROM clientes c
LEFT JOIN instancias i ON c.id = i.cliente_id
LEFT JOIN campanhas camp ON i.id = camp.instancia_id AND camp.status = 'active'
LEFT JOIN buscas b ON camp.id = b.campanha_id
LEFT JOIN leads l ON b.id = l.busca_id

UNION ALL

SELECT 
    'Mensagens (30 dias)' as categoria,
    COUNT(mia.id) as mensagens_enviadas,
    COUNT(DISTINCT mia.lead_id) as leads_contactados,
    COUNT(ml.id) as respostas_recebidas,
    COUNT(DISTINCT ml.lead_id) as leads_responderam
FROM mensagens_ia mia
FULL OUTER JOIN mensagens_lead ml ON mia.lead_id = ml.lead_id
WHERE mia.data_criacao >= NOW() - INTERVAL '30 days'
   OR ml.data_criacao >= NOW() - INTERVAL '30 days'

UNION ALL

SELECT 
    'Custos (30 dias)' as categoria,
    ROUND(SUM(mia.estimated_cost), 2) as custo_total,
    ROUND(AVG(mia.estimated_cost), 6) as custo_medio_mensagem,
    SUM(mia.total_tokens) as tokens_totais,
    ROUND(AVG(mia.total_tokens), 0) as tokens_medio_mensagem
FROM mensagens_ia mia
WHERE mia.data_criacao >= NOW() - INTERVAL '30 days';

-- Performance por cliente (ranking)
SELECT 
    ROW_NUMBER() OVER (ORDER BY 
        COALESCE(leads_que_responderam, 0) DESC, 
        COALESCE(custo_total, 0) ASC
    ) as ranking,
    cliente_nome,
    COALESCE(leads_contactados, 0) as leads_contactados,
    COALESCE(leads_que_responderam, 0) as leads_responderam,
    COALESCE(taxa_resposta_pct, 0) as taxa_resposta,
    COALESCE(custo_total, 0) as custo_total,
    COALESCE(instancias_ativas, 0) as instancias_ativas
FROM vw_custos_mensais_cliente
WHERE mes_referencia = DATE_TRUNC('month', CURRENT_DATE)
ORDER BY ranking;

-- =================================================
-- 8. CONSULTAS DE TROUBLESHOOTING
-- =================================================

-- Mensagens com erro que precisam ser reenviadas
SELECT 
    mia.id,
    mia.conteudo,
    l.nome_empresa,
    l.telefone,
    i.nome_instancia,
    mia.data_criacao,
    mia.estimated_cost
FROM mensagens_ia mia
JOIN leads l ON mia.lead_id = l.id
JOIN instancias i ON mia.instancia_id = i.id
WHERE mia.status = 'erro'
  AND mia.data_criacao >= NOW() - INTERVAL '24 hours'
ORDER BY mia.data_criacao DESC;

-- Leads duplicados (mesmo telefone)
SELECT 
    telefone,
    STRING_AGG(nome_empresa, ' | ') as empresas,
    COUNT(*) as duplicatas
FROM leads 
WHERE telefone IS NOT NULL
GROUP BY telefone 
HAVING COUNT(*) > 1
ORDER BY COUNT(*) DESC;

-- Instâncias sem atividade recente mas ativas
SELECT 
    i.nome_instancia,
    i.nome_sdr,
    c.nome as cliente,
    i.status,
    COALESCE(MAX(mia.data_criacao), i.data_criacao) as ultima_atividade,
    EXTRACT(days FROM NOW() - COALESCE(MAX(mia.data_criacao), i.data_criacao)) as dias_inativo
FROM instancias i
JOIN clientes c ON i.cliente_id = c.id
LEFT JOIN mensagens_ia mia ON i.id = mia.instancia_id
WHERE i.status = 'active'
GROUP BY i.id, i.nome_instancia, i.nome_sdr, c.nome, i.status, i.data_criacao
HAVING COALESCE(MAX(mia.data_criacao), i.data_criacao) < NOW() - INTERVAL '3 days'
ORDER BY dias_inativo DESC;
