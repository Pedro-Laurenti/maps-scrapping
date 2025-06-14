-- Tabela de clientes (tenants) para suportar multi-tenancy
CREATE TABLE clientes (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    cnpj TEXT UNIQUE,
    data_criacao TIMESTAMP DEFAULT now(),
    status TEXT CHECK (status IN ('ativo', 'inativo', 'suspenso')),
    configuracoes JSONB -- para armazenar configurações específicas do cliente
);

CREATE TABLE campanhas (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER REFERENCES clientes(id) NOT NULL, -- Referência ao cliente
    nome TEXT NOT NULL,
    descricao TEXT,
    data_criacao TIMESTAMP DEFAULT now(),
    data_validade TIMESTAMP,
    data_processamento TIMESTAMP,
    status TEXT CHECK (status IN ('ativa', 'concluida', 'cancelada', 'pausada', 'em_processamento'))
);

CREATE TABLE buscas (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER REFERENCES clientes(id) NOT NULL, -- Referência ao cliente
    campanha_id INTEGER REFERENCES campanhas(id),
    regiao TEXT,
    tipo_empresa TEXT,
    palavras_chave TEXT[],
    qtd_max INTEGER,
    data_busca TIMESTAMP DEFAULT now(),
    status TEXT CHECK (status IN ('waiting', 'processing', 'error', 'concluido'))
);

CREATE TABLE leads (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER REFERENCES clientes(id) NOT NULL, -- Referência ao cliente
    busca_id INTEGER REFERENCES buscas(id),
    nome_empresa TEXT,
    nome_lead TEXT,
    telefone TEXT, -- Removido UNIQUE global para permitir mesmo telefone em tenants diferentes
    localizacao TEXT,
    avaliacao_media REAL,
    reviews INTEGER,
    tipo_empresa TEXT,
    data_criacao TIMESTAMP DEFAULT now(),
    UNIQUE(cliente_id, telefone) -- Garantir que telefone é único para cada cliente
);

CREATE TABLE mensagens (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER REFERENCES clientes(id) NOT NULL, -- Referência ao cliente
    lead_id INTEGER REFERENCES leads(id),
    conteudo TEXT,
    status TEXT CHECK (status IN ('lido', 'recebido', 'pendente')),
    emissor TEXT CHECK (emissor IN ('ia', 'lead')),
    data_mensagem TIMESTAMP DEFAULT now()
);

CREATE TABLE classificacoes (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER REFERENCES clientes(id) NOT NULL, -- Referência ao cliente
    lead_id INTEGER REFERENCES leads(id),
    categoria TEXT,
    data_classificacao TIMESTAMP DEFAULT now()
);

CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER REFERENCES clientes(id) NOT NULL, -- Referência ao cliente
    key_hash TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_used_at TIMESTAMP,
    use_count INTEGER NOT NULL DEFAULT 0,
    allowed_ips TEXT[]
);
