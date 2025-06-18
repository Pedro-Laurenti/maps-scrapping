/* =================================================
 * GESTÃO DE CLIENTES E USUÁRIOS
 * =================================================
 * Tabelas relacionadas ao gerenciamento de clientes,
 * closers e instâncias de comunicação
 * ================================================= */

CREATE TABLE clientes (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    email TEXT,
    telefone TEXT,
    prompt_mensagem_qualificacao TEXT,
    prompt_geracao_mensagem TEXT,
    data_criacao TIMESTAMP DEFAULT now()
);

CREATE TABLE closers (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    email TEXT,
    telefone TEXT,
    status TEXT CHECK (status IN ('active', 'inactive')) DEFAULT 'active',
    cliente_id INTEGER REFERENCES clientes(id),
    data_criacao TIMESTAMP DEFAULT now()
);

CREATE TABLE instancias (
    id SERIAL PRIMARY KEY,
    nome_instancia TEXT NOT NULL,
    nome_sdr TEXT NOT NULL,
    numero TEXT NOT NULL UNIQUE,
    status TEXT CHECK (status IN ('active', 'inactive', 'blocked')),
    cliente_id INTEGER REFERENCES clientes(id),
    data_criacao TIMESTAMP DEFAULT now()
);

/* =================================================
 * SISTEMA DE LEADS E MENSAGENS
 * =================================================
 * Tabelas relacionadas às campanhas, leads, mensagens
 * e classificações de contatos
 * ================================================= */

CREATE TABLE campanhas (
    id SERIAL PRIMARY KEY,
    max_daily_sends INTEGER,
    status TEXT CHECK (status IN ('active', 'completed', 'cancelled', 'paused', 'processing')),
    cliente_id INTEGER REFERENCES clientes(id),
    instancia_id INTEGER REFERENCES instancias(id),
    data_criacao TIMESTAMP DEFAULT now()
);

CREATE TABLE leads (
    id SERIAL PRIMARY KEY,
    nome_empresa TEXT,
    tipo_empresa TEXT,
    telefone TEXT UNIQUE,
    localizacao TEXT,
    avaliacao_media REAL,
    reviews INTEGER,
    nome_lead TEXT,
    busca_id INTEGER REFERENCES buscas(id),
    data_criacao TIMESTAMP DEFAULT now()
);

CREATE TABLE leads_clientes (
    id SERIAL PRIMARY KEY,
    lead_id INTEGER REFERENCES leads(id),
    cliente_id INTEGER REFERENCES clientes(id),
    data_criacao TIMESTAMP DEFAULT now()
);

CREATE TABLE mensagens (
    id SERIAL PRIMARY KEY,
    conteudo TEXT,
    status TEXT CHECK (status IN ('lido', 'recebido', 'pendente')),
    emissor TEXT CHECK (emissor IN ('ia', 'lead')),
    instancia_id INTEGER REFERENCES instancias(id),
    lead_id INTEGER REFERENCES leads(id),
    data_criacao TIMESTAMP DEFAULT now()
);

CREATE TABLE mensagens_debounce (
    telefone VARCHAR(20) NOT NULL,
    mensagens TEXT[] NULL,
    ultima_atualizacao TIMESTAMP DEFAULT now() NULL,
    CONSTRAINT mensagens_debounce_pkey PRIMARY KEY (telefone)
);

CREATE TABLE classificacoes (
    id SERIAL PRIMARY KEY,
    categoria TEXT CHECK (categoria IN ('frio', 'respondeu', 'irritado', 'apresentacao')),
    lead_id INTEGER REFERENCES leads(id),
    cliente_id INTEGER REFERENCES clientes(id),
    data_criacao TIMESTAMP DEFAULT now()
);

CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    key_hash TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    allowed_ips TEXT[]
);

/* =================================================
 * FILAS DE PROCESSAMENTO
 * =================================================
 * Tabelas relacionadas às filas de busca e transcrições
 * ================================================= */

CREATE TABLE buscas (
    id SERIAL PRIMARY KEY,
    regiao TEXT,
    tipo_negocio TEXT,
    palavras_chave TEXT[],
    qtd_leads INTEGER,
    status TEXT CHECK (status IN ('waiting', 'processing', 'error', 'done')),
    campanha_id INTEGER REFERENCES campanhas(id),
    data_criacao TIMESTAMP DEFAULT now()
);

CREATE TABLE transcricoes (
    id SERIAL PRIMARY KEY,
    caminho_arquivo TEXT NOT NULL,
    duracao INTEGER,
    idioma TEXT DEFAULT 'pt',
    data_envio TIMESTAMP DEFAULT now(),
    data_processamento TIMESTAMP,
    status TEXT CHECK (status IN ('waiting', 'processing', 'error', 'done')),
    texto TEXT
);

/* =================================================
 * SISTEMA FINANCEIRO
 * =================================================
 * Tabelas relacionadas ao controle de preços, 
 * cobrança e pagamentos
 * ================================================= */

CREATE TABLE historico_preco_mensagem (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER REFERENCES clientes(id) NOT NULL,
    preco_por_100_mensagens DECIMAL(10, 2) NOT NULL,
    valor_total DECIMAL(10, 2) NOT NULL,
    quantidade_parcelas INTEGER DEFAULT 1,
    dia_mes_cobranca DECIMAL(10, 2) NOT NULL,
    status_pagamento TEXT CHECK (status_pagamento IN ('pendente', 'em_andamento', 'concluido', 'cancelado')) DEFAULT 'pendente',
    ativo BOOLEAN DEFAULT TRUE,
    data_inicio TIMESTAMP DEFAULT now(),
    data_fim TIMESTAMP,
    data_criacao TIMESTAMP DEFAULT now()
);

CREATE TABLE historico_preco_fixo (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER REFERENCES clientes(id) NOT NULL,
    preco_fixo_servico DECIMAL(10, 2) NOT NULL,
    valor_total DECIMAL(10, 2) NOT NULL,
    quantidade_parcelas INTEGER DEFAULT 1,
    dia_mes_cobranca DECIMAL(10, 2) NOT NULL,
    status_pagamento TEXT CHECK (status_pagamento IN ('pendente', 'em_andamento', 'concluido', 'cancelado')) DEFAULT 'pendente',
    ativo BOOLEAN DEFAULT TRUE,
    data_inicio TIMESTAMP DEFAULT now(),
    data_fim TIMESTAMP,
    data_criacao TIMESTAMP DEFAULT now()
);

CREATE TABLE pagamentos_cliente (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER REFERENCES clientes(id) NOT NULL,
    tipo_pagamento TEXT CHECK (tipo_pagamento IN ('mensagem', 'fixo', 'adicional', 'multa', 'desconto')) NOT NULL,
    historico_preco_mensagem_id INTEGER REFERENCES historico_preco_mensagem(id),
    historico_preco_fixo_id INTEGER REFERENCES historico_preco_fixo(id),
    valor_pago DECIMAL(10, 2) NOT NULL,
    data_pagamento TIMESTAMP NOT NULL,
    metodo_pagamento TEXT CHECK (metodo_pagamento IN ('pix', 'boleto', 'cartao', 'transferencia', 'dinheiro', 'outros')) NOT NULL,
    comprovante_url TEXT,
    status_pagamento TEXT CHECK (status_pagamento IN ('aprovado', 'pendente_aprovacao', 'recusado', 'estornado')) DEFAULT 'pendente_aprovacao',
    data_criacao TIMESTAMP DEFAULT now()
);