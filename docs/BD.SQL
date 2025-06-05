CREATE TABLE campanhas (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    descricao TEXT,
    data_criacao TIMESTAMP DEFAULT now(),
    data_validade TIMESTAMP,
    data_processamento TIMESTAMP,
    status TEXT CHECK (status IN ('ativa', 'concluida', 'cancelada', 'pausada', 'em_processamento')),
);

CREATE TABLE buscas (
    id SERIAL PRIMARY KEY,
    campanha_id INTEGER REFERENCES campanhas(id),
    regiao TEXT,
    tipo_empresa TEXT,
    palavras_chave TEXT[],
    qtd_max INTEGER,
    data_busca TIMESTAMP DEFAULT now()
    status TEXT CHECK (status IN ('waiting', 'processing', 'error', 'concluido')),
);

CREATE TABLE leads (
    id SERIAL PRIMARY KEY,
    busca_id INTEGER REFERENCES buscas(id)
    nome_empresa TEXT,
    nome_lead TEXT,
    telefone TEXT,
    localizacao TEXT,
    avaliacao_media REAL,
    reviews INTEGER,
    tipo_empresa TEXT,
    data_criacao TIMESTAMP DEFAULT now()
);

CREATE TABLE mensagens (
    id SERIAL PRIMARY KEY,
    lead_id INTEGER REFERENCES leads(id),
    conteudo TEXT,
    status TEXT CHECK (status IN ('lido', 'recebido', 'pendente')),
    emissor TEXT CHECK (emissor IN ('ia', 'lead')),
    data_mensagem TIMESTAMP DEFAULT now()
);

CREATE TABLE classificacoes (
    id SERIAL PRIMARY KEY,
    lead_id INTEGER REFERENCES leads(id),
    categoria TEXT,
    data_classificacao TIMESTAMP DEFAULT now()
);