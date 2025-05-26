FROM mcr.microsoft.com/playwright/python:latest

WORKDIR /app

# Copiar apenas os arquivos de requisitos primeiro (para melhor uso do cache)
COPY docs/requirements.txt .

# Instalar dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o código-fonte
COPY . .

# Expor a porta que a API utiliza
EXPOSE 8000

# Comando para iniciar a aplicação
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
