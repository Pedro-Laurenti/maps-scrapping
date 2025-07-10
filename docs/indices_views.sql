/* =================================================
 * ÍNDICES E VIEWS - BANCO DE DADOS V2
 * =================================================
 * Arquivo complementar para índices, views e outras
 * estruturas que não sejam tabelas
 * ================================================= */

/* =================================================
 * ÍNDICES PARA PERFORMANCE
 * ================================================= */

-- Índices para mensagens_ia (consultas por instância e custos)
CREATE INDEX idx_mensagens_ia_instancia ON mensagens_ia(instancia_id);
CREATE INDEX idx_mensagens_ia_lead ON mensagens_ia(lead_id);
CREATE INDEX idx_mensagens_ia_data ON mensagens_ia(data_criacao);
CREATE INDEX idx_mensagens_ia_status ON mensagens_ia(status);
CREATE INDEX idx_mensagens_ia_tokens ON mensagens_ia(total_tokens);
CREATE INDEX idx_mensagens_ia_custo ON mensagens_ia(estimated_cost);
CREATE INDEX idx_mensagens_ia_instancia_data ON mensagens_ia(instancia_id, data_criacao);
CREATE INDEX idx_mensagens_ia_lead_data ON mensagens_ia(lead_id, data_criacao);

-- Índices para mensagens_lead
CREATE INDEX idx_mensagens_lead_lead ON mensagens_lead(lead_id);
CREATE INDEX idx_mensagens_lead_instancia ON mensagens_lead(instancia_id);
CREATE INDEX idx_mensagens_lead_data ON mensagens_lead(data_criacao);
CREATE INDEX idx_mensagens_lead_status ON mensagens_lead(status);
CREATE INDEX idx_mensagens_lead_instancia_data ON mensagens_lead(instancia_id, data_criacao);

-- Índices para leads
CREATE INDEX idx_leads_telefone ON leads(telefone);
CREATE INDEX idx_leads_busca ON leads(busca_id);
CREATE INDEX idx_leads_empresa ON leads(nome_empresa);
CREATE INDEX idx_leads_tipo_empresa ON leads(tipo_empresa);
CREATE INDEX idx_leads_localizacao ON leads(localizacao);
CREATE INDEX idx_leads_avaliacao ON leads(avaliacao_media);

-- Índices para campanhas
CREATE INDEX idx_campanhas_cliente ON campanhas(cliente_id);
CREATE INDEX idx_campanhas_instancia ON campanhas(instancia_id);
CREATE INDEX idx_campanhas_status ON campanhas(status);
CREATE INDEX idx_campanhas_data ON campanhas(data_criacao);

-- Índices para buscas
CREATE INDEX idx_buscas_campanha ON buscas(campanha_id);
CREATE INDEX idx_buscas_status ON buscas(status);
CREATE INDEX idx_buscas_regiao ON buscas(regiao);
CREATE INDEX idx_buscas_tipo_negocio ON buscas(tipo_negocio);

-- Índices para classificações
CREATE INDEX idx_classificacoes_lead ON classificacoes(lead_id);
CREATE INDEX idx_classificacoes_cliente ON classificacoes(cliente_id);
CREATE INDEX idx_classificacoes_categoria ON classificacoes(categoria);
CREATE INDEX idx_classificacoes_data ON classificacoes(data_criacao);

-- Índices para instâncias
CREATE INDEX idx_instancias_cliente ON instancias(cliente_id);
CREATE INDEX idx_instancias_status ON instancias(status);
CREATE INDEX idx_instancias_numero ON instancias(numero);

-- Índices para API keys
CREATE INDEX idx_api_keys_active ON api_keys(is_active);
CREATE INDEX idx_api_keys_expires ON api_keys(expires_at);

-- Índices para pagamentos
CREATE INDEX idx_pagamentos_cliente ON pagamentos_cliente(cliente_id);
CREATE INDEX idx_pagamentos_data ON pagamentos_cliente(data_pagamento);
CREATE INDEX idx_pagamentos_status ON pagamentos_cliente(status_pagamento);
CREATE INDEX idx_pagamentos_tipo ON pagamentos_cliente(tipo_pagamento);

/* =================================================
 * VIEWS PARA RELATÓRIOS E CONSULTAS
 * ================================================= */

/* =================================================
 * VIEWS PARA RELATÓRIOS E CONSULTAS
 * ================================================= */

-- View para histórico completo de conversas (união das mensagens)
CREATE VIEW vw_conversas_completas AS
SELECT 
    'ia' as emissor,
    mia.id as mensagem_id,
    mia.conteudo,
    mia.status,
    mia.lead_id,
    mia.instancia_id,
    mia.total_tokens,
    mia.estimated_cost,
    mia.data_criacao,
    l.nome_empresa,
    l.telefone,
    i.nome_instancia,
    i.nome_sdr,
    c.nome as cliente_nome
FROM mensagens_ia mia
JOIN leads l ON mia.lead_id = l.id
JOIN instancias i ON mia.instancia_id = i.id
JOIN clientes c ON i.cliente_id = c.id

UNION ALL

SELECT 
    'lead' as emissor,
    ml.id as mensagem_id,
    ml.conteudo,
    ml.status,
    ml.lead_id,
    ml.instancia_id,
    NULL as total_tokens,
    NULL as estimated_cost,
    ml.data_criacao,
    l.nome_empresa,
    l.telefone,
    i.nome_instancia,
    i.nome_sdr,
    c.nome as cliente_nome
FROM mensagens_lead ml
JOIN leads l ON ml.lead_id = l.id
JOIN instancias i ON ml.instancia_id = i.id
JOIN clientes c ON i.cliente_id = c.id
ORDER BY lead_id, instancia_id, data_criacao;

-- View para custos diários por instância
CREATE VIEW vw_custos_diarios_instancia AS
SELECT 
    i.id as instancia_id,
    i.nome_instancia,
    i.nome_sdr,
    i.cliente_id,
    c.nome as cliente_nome,
    DATE(mia.data_criacao) as data,
    COUNT(mia.id) as mensagens_enviadas,
    SUM(mia.total_tokens) as tokens_totais,
    SUM(mia.estimated_cost) as custo_total,
    AVG(mia.estimated_cost) as custo_medio_mensagem,
    AVG(mia.total_tokens) as tokens_medio_mensagem
FROM instancias i
JOIN clientes c ON i.cliente_id = c.id
LEFT JOIN mensagens_ia mia ON i.id = mia.instancia_id
WHERE mia.data_criacao IS NOT NULL
GROUP BY i.id, i.nome_instancia, i.nome_sdr, i.cliente_id, c.nome, DATE(mia.data_criacao)
ORDER BY data DESC, custo_total DESC;

-- View para custos mensais por cliente
CREATE VIEW vw_custos_mensais_cliente AS
SELECT 
    cl.id as cliente_id,
    cl.nome as cliente_nome,
    DATE_TRUNC('month', mia.data_criacao) as mes_referencia,
    COUNT(DISTINCT i.id) as instancias_ativas,
    COUNT(mia.id) as total_mensagens,
    SUM(mia.total_tokens) as total_tokens,
    SUM(mia.estimated_cost) as custo_total,
    AVG(mia.estimated_cost) as custo_medio_mensagem,
    COUNT(DISTINCT mia.lead_id) as leads_contactados
FROM clientes cl
JOIN instancias i ON cl.id = i.cliente_id
LEFT JOIN mensagens_ia mia ON i.id = mia.instancia_id
WHERE mia.data_criacao IS NOT NULL
GROUP BY cl.id, cl.nome, DATE_TRUNC('month', mia.data_criacao)
ORDER BY mes_referencia DESC, custo_total DESC;

-- View para performance de campanhas
CREATE VIEW vw_performance_campanhas AS
SELECT 
    camp.id as campanha_id,
    camp.cliente_id,
    cl.nome as cliente_nome,
    i.nome_instancia,
    COUNT(DISTINCT l.id) as total_leads,
    COUNT(DISTINCT mia.lead_id) as leads_contactados,
    COUNT(DISTINCT ml.lead_id) as leads_que_responderam,
    COUNT(mia.id) as mensagens_enviadas,
    COUNT(ml.id) as respostas_recebidas,
    SUM(mia.estimated_cost) as custo_total,
    ROUND(
        (COUNT(DISTINCT ml.lead_id)::DECIMAL / NULLIF(COUNT(DISTINCT mia.lead_id), 0)) * 100, 2
    ) as taxa_resposta_pct,
    ROUND(
        SUM(mia.estimated_cost) / NULLIF(COUNT(mia.id), 0), 6
    ) as custo_por_mensagem,
    camp.status as campanha_status,
    camp.data_criacao as campanha_criada
FROM campanhas camp
JOIN clientes cl ON camp.cliente_id = cl.id
JOIN instancias i ON camp.instancia_id = i.id
LEFT JOIN buscas b ON camp.id = b.campanha_id
LEFT JOIN leads l ON b.id = l.busca_id
LEFT JOIN mensagens_ia mia ON l.id = mia.lead_id AND camp.instancia_id = mia.instancia_id
LEFT JOIN mensagens_lead ml ON l.id = ml.lead_id AND camp.instancia_id = ml.instancia_id
GROUP BY camp.id, camp.cliente_id, cl.nome, i.nome_instancia, camp.status, camp.data_criacao
ORDER BY camp.data_criacao DESC;

-- View para leads mais engajados
CREATE VIEW vw_leads_engajados AS
SELECT 
    l.id as lead_id,
    l.nome_empresa,
    l.telefone,
    l.tipo_empresa,
    l.localizacao,
    l.avaliacao_media,
    COUNT(ml.id) as total_respostas,
    COUNT(mia.id) as mensagens_recebidas,
    MAX(ml.data_criacao) as ultima_resposta,
    MAX(mia.data_criacao) as ultima_mensagem_enviada,
    CASE 
        WHEN COUNT(ml.id) = 0 THEN 'Sem resposta'
        WHEN COUNT(ml.id) = 1 THEN 'Baixo engajamento'
        WHEN COUNT(ml.id) BETWEEN 2 AND 5 THEN 'Médio engajamento'
        ELSE 'Alto engajamento'
    END as nivel_engajamento,
    STRING_AGG(DISTINCT cl.nome, ', ') as clientes_interesse
FROM leads l
LEFT JOIN mensagens_ia mia ON l.id = mia.lead_id
LEFT JOIN mensagens_lead ml ON l.id = ml.lead_id
LEFT JOIN instancias i ON mia.instancia_id = i.id OR ml.instancia_id = i.id
LEFT JOIN clientes cl ON i.cliente_id = cl.id
GROUP BY l.id, l.nome_empresa, l.telefone, l.tipo_empresa, l.localizacao, l.avaliacao_media
HAVING COUNT(mia.id) > 0 OR COUNT(ml.id) > 0
ORDER BY total_respostas DESC, ultima_resposta DESC;

-- View para ranking de tipos de empresa por conversão
CREATE VIEW vw_ranking_tipos_empresa AS
SELECT 
    l.tipo_empresa,
    COUNT(DISTINCT l.id) as total_leads,
    COUNT(DISTINCT ml.lead_id) as leads_que_responderam,
    COUNT(ml.id) as total_respostas,
    ROUND(
        (COUNT(DISTINCT ml.lead_id)::DECIMAL / NULLIF(COUNT(DISTINCT l.id), 0)) * 100, 2
    ) as taxa_resposta_pct,
    AVG(l.avaliacao_media) as avaliacao_media,
    COUNT(DISTINCT l.localizacao) as regioes_diferentes
FROM leads l
LEFT JOIN mensagens_ia mia ON l.id = mia.lead_id
LEFT JOIN mensagens_lead ml ON l.id = ml.lead_id
WHERE l.tipo_empresa IS NOT NULL
GROUP BY l.tipo_empresa
HAVING COUNT(DISTINCT l.id) >= 5  -- Só tipos com pelo menos 5 leads
ORDER BY taxa_resposta_pct DESC, total_leads DESC;

-- View para análise de horários de resposta dos leads
CREATE VIEW vw_analise_horarios_resposta AS
SELECT 
    EXTRACT(hour FROM ml.data_criacao) as hora_resposta,
    EXTRACT(dow FROM ml.data_criacao) as dia_semana, -- 0=Domingo, 6=Sábado
    COUNT(*) as total_respostas,
    COUNT(DISTINCT ml.lead_id) as leads_unicos,
    CASE EXTRACT(dow FROM ml.data_criacao)
        WHEN 0 THEN 'Domingo'
        WHEN 1 THEN 'Segunda'
        WHEN 2 THEN 'Terça'
        WHEN 3 THEN 'Quarta'
        WHEN 4 THEN 'Quinta'
        WHEN 5 THEN 'Sexta'
        WHEN 6 THEN 'Sábado'
    END as nome_dia_semana
FROM mensagens_lead ml
GROUP BY EXTRACT(hour FROM ml.data_criacao), EXTRACT(dow FROM ml.data_criacao)
ORDER BY dia_semana, hora_resposta;

-- View para alertas de instâncias inativas
CREATE VIEW vw_alertas_instancias AS
SELECT 
    i.id as instancia_id,
    i.nome_instancia,
    i.nome_sdr,
    i.numero,
    i.status,
    c.nome as cliente_nome,
    COALESCE(MAX(mia.data_criacao), i.data_criacao) as ultima_atividade,
    COUNT(mia.id) as mensagens_ultimos_7_dias,
    CASE 
        WHEN i.status = 'inactive' THEN 'Instância desativada'
        WHEN i.status = 'blocked' THEN 'Instância bloqueada'
        WHEN COALESCE(MAX(mia.data_criacao), i.data_criacao) < NOW() - INTERVAL '7 days' 
            THEN 'Sem atividade há mais de 7 dias'
        WHEN COUNT(CASE WHEN mia.data_criacao >= NOW() - INTERVAL '24 hours' THEN 1 END) = 0
            THEN 'Sem mensagens nas últimas 24h'
        ELSE 'Normal'
    END as alerta
FROM instancias i
JOIN clientes c ON i.cliente_id = c.id
LEFT JOIN mensagens_ia mia ON i.id = mia.instancia_id 
    AND mia.data_criacao >= NOW() - INTERVAL '7 days'
GROUP BY i.id, i.nome_instancia, i.nome_sdr, i.numero, i.status, c.nome
HAVING CASE 
    WHEN i.status = 'inactive' THEN true
    WHEN i.status = 'blocked' THEN true
    WHEN COALESCE(MAX(mia.data_criacao), i.data_criacao) < NOW() - INTERVAL '7 days' THEN true
    WHEN COUNT(CASE WHEN mia.data_criacao >= NOW() - INTERVAL '24 hours' THEN 1 END) = 0 THEN true
    ELSE false
END
ORDER BY ultima_atividade ASC;

-- View para classificações dos leads
CREATE VIEW vw_classificacoes_leads AS
SELECT 
    l.id as lead_id,
    l.nome_empresa,
    l.telefone,
    l.tipo_empresa,
    STRING_AGG(cl.categoria, ', ' ORDER BY cl.data_criacao DESC) as classificacoes,
    STRING_AGG(DISTINCT c.nome, ', ') as clientes_classificaram,
    MAX(cl.data_criacao) as ultima_classificacao,
    COUNT(DISTINCT cl.categoria) as tipos_classificacao
FROM leads l
LEFT JOIN classificacoes cl ON l.id = cl.lead_id
LEFT JOIN clientes c ON cl.cliente_id = c.id
GROUP BY l.id, l.nome_empresa, l.telefone, l.tipo_empresa
HAVING COUNT(cl.id) > 0
ORDER BY ultima_classificacao DESC;

-- View para estatísticas de leads por campanha
CREATE VIEW vw_stats_leads_campanha AS
SELECT 
    camp.id as campanha_id,
    camp.cliente_id,
    COUNT(DISTINCT l.id) as total_leads,
    COUNT(DISTINCT mia.lead_id) as leads_com_mensagem_enviada,
    COUNT(DISTINCT ml.lead_id) as leads_que_responderam,
    COUNT(ml.id) as total_respostas_leads,
    COUNT(mia.id) as total_mensagens_enviadas,
    SUM(mia.estimated_cost) as custo_total_campanha
FROM campanhas camp
LEFT JOIN buscas b ON camp.id = b.campanha_id
LEFT JOIN leads l ON b.id = l.busca_id
LEFT JOIN mensagens_ia mia ON l.id = mia.lead_id AND camp.instancia_id = mia.instancia_id
LEFT JOIN mensagens_lead ml ON l.id = ml.lead_id AND camp.instancia_id = ml.instancia_id
GROUP BY camp.id, camp.cliente_id;

-- View para análise de funil de conversão
CREATE VIEW vw_funil_conversao AS
SELECT 
    camp.id as campanha_id,
    camp.cliente_id,
    cl.nome as cliente_nome,
    i.nome_instancia,
    COUNT(DISTINCT l.id) as total_leads_campanha,
    COUNT(DISTINCT mia.lead_id) as leads_contactados,
    COUNT(DISTINCT ml.lead_id) as leads_responderam,
    COUNT(DISTINCT CASE WHEN classif.categoria = 'apresentacao' THEN l.id END) as leads_apresentacao,
    COUNT(DISTINCT CASE WHEN classif.categoria IN ('irritado', 'sem-whatsapp') THEN l.id END) as leads_negativos,
    ROUND((COUNT(DISTINCT mia.lead_id)::DECIMAL / NULLIF(COUNT(DISTINCT l.id), 0)) * 100, 2) as taxa_contato_pct,
    ROUND((COUNT(DISTINCT ml.lead_id)::DECIMAL / NULLIF(COUNT(DISTINCT mia.lead_id), 0)) * 100, 2) as taxa_resposta_pct,
    ROUND((COUNT(DISTINCT CASE WHEN classif.categoria = 'apresentacao' THEN l.id END)::DECIMAL / NULLIF(COUNT(DISTINCT ml.lead_id), 0)) * 100, 2) as taxa_apresentacao_pct
FROM campanhas camp
JOIN clientes cl ON camp.cliente_id = cl.id
JOIN instancias i ON camp.instancia_id = i.id
LEFT JOIN buscas b ON camp.id = b.campanha_id
LEFT JOIN leads l ON b.id = l.busca_id
LEFT JOIN mensagens_ia mia ON l.id = mia.lead_id AND camp.instancia_id = mia.instancia_id
LEFT JOIN mensagens_lead ml ON l.id = ml.lead_id AND camp.instancia_id = ml.instancia_id
LEFT JOIN classificacoes classif ON l.id = classif.lead_id
GROUP BY camp.id, camp.cliente_id, cl.nome, i.nome_instancia;

-- View para análise de retenção e follow-up
CREATE VIEW vw_analise_follow_up AS
SELECT 
    l.id as lead_id,
    l.nome_empresa,
    l.telefone,
    COUNT(mia.id) as total_mensagens_enviadas,
    COUNT(ml.id) as total_respostas,
    MIN(mia.data_criacao) as primeiro_contato,
    MAX(mia.data_criacao) as ultimo_envio,
    MAX(ml.data_criacao) as ultima_resposta,
    EXTRACT(days FROM NOW() - MAX(COALESCE(ml.data_criacao, mia.data_criacao))) as dias_sem_interacao,
    CASE 
        WHEN COUNT(ml.id) > 0 AND MAX(ml.data_criacao) > MAX(mia.data_criacao) THEN 'Aguardando follow-up'
        WHEN COUNT(ml.id) > 0 AND MAX(mia.data_criacao) > MAX(ml.data_criacao) THEN 'Aguardando resposta'
        WHEN COUNT(ml.id) = 0 AND COUNT(mia.id) >= 3 THEN 'Lead frio'
        WHEN COUNT(ml.id) = 0 AND COUNT(mia.id) < 3 THEN 'Em prospecção'
        ELSE 'Status indefinido'
    END as status_follow_up,
    STRING_AGG(DISTINCT i.nome_instancia, ', ') as instancias_contato
FROM leads l
LEFT JOIN mensagens_ia mia ON l.id = mia.lead_id
LEFT JOIN mensagens_lead ml ON l.id = ml.lead_id
LEFT JOIN instancias i ON mia.instancia_id = i.id OR ml.instancia_id = i.id
GROUP BY l.id, l.nome_empresa, l.telefone
HAVING COUNT(mia.id) > 0 OR COUNT(ml.id) > 0
ORDER BY dias_sem_interacao DESC;

-- View para dashboard executivo
CREATE VIEW vw_dashboard_executivo AS
SELECT 
    'hoje' as periodo,
    COUNT(DISTINCT mia.id) as mensagens_enviadas,
    COUNT(DISTINCT ml.id) as respostas_recebidas,
    COUNT(DISTINCT mia.lead_id) as leads_contactados,
    COUNT(DISTINCT ml.lead_id) as leads_responderam,
    SUM(mia.estimated_cost) as custo_total,
    SUM(mia.total_tokens) as tokens_consumidos,
    COUNT(DISTINCT mia.instancia_id) as instancias_ativas
FROM mensagens_ia mia
FULL OUTER JOIN mensagens_lead ml ON DATE(mia.data_criacao) = DATE(ml.data_criacao)
WHERE DATE(mia.data_criacao) = CURRENT_DATE 
   OR DATE(ml.data_criacao) = CURRENT_DATE

UNION ALL

SELECT 
    'semana' as periodo,
    COUNT(DISTINCT mia.id) as mensagens_enviadas,
    COUNT(DISTINCT ml.id) as respostas_recebidas,
    COUNT(DISTINCT mia.lead_id) as leads_contactados,
    COUNT(DISTINCT ml.lead_id) as leads_responderam,
    SUM(mia.estimated_cost) as custo_total,
    SUM(mia.total_tokens) as tokens_consumidos,
    COUNT(DISTINCT mia.instancia_id) as instancias_ativas
FROM mensagens_ia mia
FULL OUTER JOIN mensagens_lead ml ON DATE_TRUNC('week', mia.data_criacao) = DATE_TRUNC('week', ml.data_criacao)
WHERE mia.data_criacao >= DATE_TRUNC('week', CURRENT_DATE)
   OR ml.data_criacao >= DATE_TRUNC('week', CURRENT_DATE)

UNION ALL

SELECT 
    'mes' as periodo,
    COUNT(DISTINCT mia.id) as mensagens_enviadas,
    COUNT(DISTINCT ml.id) as respostas_recebidas,
    COUNT(DISTINCT mia.lead_id) as leads_contactados,
    COUNT(DISTINCT ml.lead_id) as leads_responderam,
    SUM(mia.estimated_cost) as custo_total,
    SUM(mia.total_tokens) as tokens_consumidos,
    COUNT(DISTINCT mia.instancia_id) as instancias_ativas
FROM mensagens_ia mia
FULL OUTER JOIN mensagens_lead ml ON DATE_TRUNC('month', mia.data_criacao) = DATE_TRUNC('month', ml.data_criacao)
WHERE mia.data_criacao >= DATE_TRUNC('month', CURRENT_DATE)
   OR ml.data_criacao >= DATE_TRUNC('month', CURRENT_DATE);

-- View para análise de qualidade das mensagens
CREATE VIEW vw_qualidade_mensagens AS
SELECT 
    i.id as instancia_id,
    i.nome_instancia,
    i.nome_sdr,
    c.nome as cliente_nome,
    COUNT(mia.id) as total_mensagens,
    AVG(LENGTH(mia.conteudo)) as tamanho_medio_mensagem,
    AVG(mia.total_tokens) as tokens_medio,
    AVG(mia.estimated_cost) as custo_medio,
    COUNT(DISTINCT mia.lead_id) as leads_unicos_contactados,
    COUNT(ml.id) as respostas_obtidas,
    ROUND((COUNT(ml.id)::DECIMAL / NULLIF(COUNT(mia.id), 0)) * 100, 2) as taxa_resposta_pct,
    ROUND(AVG(mia.estimated_cost) / AVG(mia.total_tokens) * 1000, 6) as custo_por_1k_tokens
FROM instancias i
JOIN clientes c ON i.cliente_id = c.id
LEFT JOIN mensagens_ia mia ON i.id = mia.instancia_id
LEFT JOIN mensagens_lead ml ON mia.lead_id = ml.lead_id AND mia.instancia_id = ml.instancia_id
WHERE mia.data_criacao >= NOW() - INTERVAL '30 days'
GROUP BY i.id, i.nome_instancia, i.nome_sdr, c.nome
HAVING COUNT(mia.id) > 0
ORDER BY taxa_resposta_pct DESC, custo_medio ASC;
