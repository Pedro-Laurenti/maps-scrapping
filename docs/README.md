# Google Maps Scraper

Esse é um scraper simples para o Google Maps que extrai informações de estabelecimentos com base em uma região e tipo de negócio.

## Estrutura do Projeto

O projeto foi organizado em múltiplos módulos para facilitar a manutenção:

- `scraper.py` - Arquivo principal que coordena a execução
- `crawler.py` - Funções para navegação e scraping no Google Maps
- `extractor.py` - Funções para extrair dados dos estabelecimentos
- `utils.py` - Funções utilitárias para entrada/saída e tratamento de erros

## Requisitos

- Python 3.8+
- Playwright

## Instalação

1. Clone o repositório
2. Crie um ambiente virtual:

```bash
python -m venv .venv
```

3. Ative o ambiente virtual:

No Windows:
```bash
.venv\Scripts\activate
```

No Linux/Mac:
```bash
source .venv/bin/activate
```

4. Instale as dependências:

```bash
pip install -r requirements.txt
```

5. Instale os navegadores do Playwright:

```bash
playwright install chromium
```

## Uso

Execute o script fornecendo os parâmetros em formato JSON via entrada padrão:

```bash
python scraper.py < params.json > results.json
```

Ou use o script de teste fornecido:

```bash
test_scraper.bat
```

### Formato de Entrada

```json
{
  "region": "Local a ser pesquisado",
  "business_type": "Tipo de estabelecimento",
  "max_results": 10,
  "keywords": "Palavras-chave adicionais"
}
```

### Formato de Saída

```json
[
  {
    "name": "Nome do Estabelecimento"
  },
  ...
]
```

## Funcionalidades Atuais

- Extração de nomes de estabelecimentos do Google Maps

## Funcionalidades Futuras

- Extração de endereços
- Extração de números de telefone
- Extração de websites
- Extração de avaliações e número de comentários
