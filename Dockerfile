FROM mcr.microsoft.com/playwright/python:v1.52.0-focal

WORKDIR /app

# Copiar apenas os arquivos necessários
COPY __init__.py crawler.py extractor.py utils.py /app/
COPY docs/requirements.txt /app/

# Instalar dependências
RUN pip install --no-cache-dir -r requirements.txt

# Instalar browsers necessários
RUN python -m playwright install chromium

# Configurar o script como ponto de entrada
ENTRYPOINT ["python", "__init__.py"]
