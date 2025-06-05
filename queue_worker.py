#!/usr/bin/env python3
# filepath: /home/pedro/DEVP/maps-scrapping/queue_worker.py
import asyncio
from dotenv import load_dotenv
import os
import signal
import sys
from src.queue_processor import start_queue_processor
from src.utils import log_info, log_exception

# Carrega variáveis do arquivo .env
load_dotenv()

# Configura o número de workers a partir de variável de ambiente ou usa valor padrão
NUM_WORKERS = int(os.getenv("MAX_CONCURRENT_TASKS", "1"))

# Flag para controlar a execução do loop principal
running = True

def handle_signal(signum, frame):
    """
    Manipulador de sinais para parar o programa graciosamente quando receber SIGINT ou SIGTERM
    """
    global running
    log_info(f"Recebido sinal {signum}, encerrando workers...")
    running = False

async def main():
    """
    Função principal que inicia os workers e mantém o processo em execução
    """
    try:
        log_info(f"Iniciando processador de fila com {NUM_WORKERS} workers")
        
        # Registra manipuladores de sinal para parada graciosa
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
        
        # Inicia os workers
        workers = await start_queue_processor(NUM_WORKERS)
        
        # Mantém o programa em execução até receber sinal para parar
        while running:
            await asyncio.sleep(1)
            
        log_info("Encerrando processador de fila...")
        
        # Cancela todos os workers
        for worker in workers:
            worker.cancel()
            
        # Espera todos os workers terminarem
        await asyncio.gather(*workers, return_exceptions=True)
        
        log_info("Processador de fila encerrado com sucesso")
        
    except Exception as e:
        log_exception(f"Erro no processador de fila: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    # Inicia o loop de eventos do asyncio
    asyncio.run(main())
