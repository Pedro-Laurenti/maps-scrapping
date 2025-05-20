@echo off
ECHO Iniciando servidor local...

:: Verificar se o ambiente virtual existe
IF NOT EXIST ".venv\" (
    ECHO Criando ambiente virtual...
    python -m venv .venv
)

:: Ativar o ambiente virtual
CALL .venv\Scripts\activate.bat

:: Instalar o pacote em modo de desenvolvimento (se ainda não estiver instalado)
pip install -e . > nul 2>&1


echo Iniciando Google Maps Scraper API...
cd /d "%~dp0"
python -m api
