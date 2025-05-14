@echo off
ECHO Iniciando teste...

:: Verificar se o ambiente virtual existe
IF NOT EXIST ".venv\" (
    ECHO Criando ambiente virtual...
    python -m venv .venv
)

:: Ativar o ambiente virtual
CALL .venv\Scripts\activate.bat

:: Instalar o pacote em modo de desenvolvimento (se ainda não estiver instalado)
pip install -e . > nul 2>&1

:: Executar o script com os parâmetros de teste
python app.py < params.json > results.json

:: Manter a janela aberta para ver os resultados
PAUSE