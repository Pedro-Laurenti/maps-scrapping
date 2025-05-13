# Integração do Google Maps Scraper com n8n

Este documento contém instruções para integrar o Google Maps Scraper com o n8n usando Docker e EasyPanel.

## Requisitos

- Docker instalado na VPS onde o n8n está rodando
- Acesso ao n8n para configurar um fluxo de trabalho
- EasyPanel para gerenciamento da VPS

## Instruções para Implantação

### 1. Construir a imagem Docker

```bash
docker build -t gmaps-scraper .
```

### 2. Integração com o n8n

#### Configuração do fluxo no n8n:

1. **Webhook** - Configurar para receber os parâmetros:
   - Região (CEP, cidade, bairro, raio)
   - Tipo de empresa (restaurantes, lanchonetes, padarias, etc.)
   - Quantidade máxima por batch
   - Palavras-chave (opcional: "delivery", "rodízio", "vegano", etc.)

2. **Execute Command** - Configurar para executar o container Docker:
   ```
   docker run -i gmaps-scraper
   ```
   - Passar os parâmetros recebidos do webhook no formato JSON via STDIN
   - Importante: verifique as permissões necessárias para que o n8n execute comandos Docker

3. **Function** - Para tratar o JSON retornado pelo scraper

4. **PostgreSQL** - Para inserir os dados no banco

## Parâmetros de Entrada (JSON)

```json
{
  "region": "Nome da cidade ou bairro",
  "business_type": "Tipo de negócio",
  "max_results": 10,
  "keywords": "Palavras-chave adicionais"
}
```

## Fluxo de Integração com EasyPanel

1. Fazer upload do código para a VPS
2. Construir a imagem Docker no servidor
3. Configurar o n8n para executar o container como parte do fluxo de automação

## Observações de Segurança

- Certifique-se de que o usuário do n8n tenha permissões para executar comandos Docker
- Considere criar um usuário Docker específico com permissões limitadas para essa integração
