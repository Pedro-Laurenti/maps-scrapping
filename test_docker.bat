@echo off
ECHO Construindo a imagem Docker...
docker build -t gmaps-scraper .

ECHO Executando o container com os parâmetros de teste...
docker run -i gmaps-scraper < params.json

ECHO Teste concluído.
PAUSE
