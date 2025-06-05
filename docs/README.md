# 📌 Considerações Técnicas

- **Banco de dados**: PostgreSQL (armazenamento dos dados de leads, mensagens, classificações e histórico).
- **Ferramentas utilizadas**: `n8n` para automações, `EvolutionAPI` para integração com whatsapp.
---

# 🐳 Executando com Docker

O sistema é composto por dois serviços Docker:

1. **API** (`maps-scraper-api`): Serviço que expõe a API REST para interação com o sistema
2. **Worker** (`maps-scraper-worker`): Serviço que processa as buscas na fila de forma assíncrona

## Configuração do Ambiente

1. Clone o repositório:

2. Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:

```
# Configurações do Banco de Dados
DB_HOST=168.231.99.240
DB_PORT=6071
DB_NAME=privado
DB_USER=admin
DB_PASSWORD=789456123

# Configurações de Processamento
BATCH_SIZE=20
MAX_CONCURRENT_TASKS=1
QUEUE_CHECK_INTERVAL=5
QUEUE_UPDATE_INTERVAL=10

# Configurações de Segurança
DEFAULT_API_KEY_NAME="API Default"
DEFAULT_API_KEY_ALLOWED_IPS=""
DEFAULT_API_KEY_EXPIRES_DAYS=365
```

## Executando o Sistema

### Iniciar todos os serviços

Para iniciar tanto a API quanto o worker:

```bash
docker-compose up -d
```

> **Nota importante**: A API e o worker são executados como serviços separados para melhor controle de recursos e escalabilidade. O serviço API (`maps-scraper-api`) apenas processa requisições HTTP, enquanto o serviço worker (`maps-scraper-worker`) é responsável por processar as buscas na fila.

### Ver logs dos serviços

Para ver os logs de todos os serviços:

```bash
docker-compose logs -f
```

Para ver logs de um serviço específico:

```bash
docker-compose logs -f maps-scraper-api
# ou
docker-compose logs -f maps-scraper-worker
```

### Parar os serviços

```bash
docker-compose down
```

## Reconstruindo após alterações no código

Se você fez alterações no código-fonte, é necessário reconstruir as imagens:

```bash
# Pare os containers
docker-compose down

# Reconstrua sem usar cache
docker-compose build --no-cache

# Inicie novamente
docker-compose up -d

# Verifique os logs para confirmar que está funcionando corretamente
docker-compose logs -f
```

Para aplicar apenas as alterações do arquivo .env sem reiniciar completamente:

```bash
docker-compose down
docker-compose up -d
```

# 🔐 Segurança da API

É necessário fornecer uma API Key válida no cabeçalho `X-API-Key` em todas as requisições.

## Obtenção da API Key

Quando a API é iniciada pela primeira vez, uma API Key padrão é criada automaticamente e exibida no log de inicialização. **Guarde esta chave em um local seguro**, pois ela não será exibida novamente.


--- TODO

segurança OK
verificação de existencia (pula) 
verificação de numero (pula)
reviews NULA

