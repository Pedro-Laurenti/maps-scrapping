from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import asyncio
import uvicorn
import json
import os
import sys
import subprocess
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from src.database import (
    insert_busca, insert_leads, get_leads_by_busca_id, 
    update_busca_status, get_busca_by_id, get_connection
)
from src.queue_processor import start_queue_processor, stop_queue_processor, process_busca_in_batches, get_queue_position

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializa o processador de fila quando a API inicia
    start_queue_processor()
    yield
    # Para o processador de fila quando a API é encerrada
    stop_queue_processor()

# Definição da aplicação FastAPI
app = FastAPI(
    title="Google Maps Scraper API",
    description="API para buscar informações de negócios no Google Maps",
    version="1.0.0",
    lifespan=lifespan
)

# Modelo para os parâmetros de entrada
class ScraperParams(BaseModel):
    region: str
    business_type: str
    max_results: int = 10
    keywords: Optional[str] = ""

# Modelo para os resultados
class BusinessResult(BaseModel):
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    url: Optional[str] = None

# Armazenamento temporário para resultados de tarefas em andamento
tasks_results: Dict[str, Any] = {}

@app.get("/")
async def root():
    return {"message": "Google Maps Scraper API - Use /docs para ver a documentação"}

async def process_task(task_id: str, params: dict):
    """
    Inicia o processamento de uma tarefa pelo sistema de fila
    """
    try:
        # Obtém o ID da busca do task_id
        busca_id = tasks_results[task_id].get("busca_id")
        
        # Atualiza o status da busca para "waiting" (na fila)
        await update_busca_status(busca_id, "waiting")
        
        # Atualiza o status da task
        tasks_results[task_id]["status"] = "queued"
        
        return True
    except Exception as e:
        tasks_results[task_id] = {
            "status": "error",
            "message": str(e)
        }
        return False

@app.post("/scrape")
async def scrape(params: ScraperParams, background_tasks: BackgroundTasks):
    try:
        import time
        # Valida os parâmetros para lidar com grandes volumes
        max_results = params.max_results
        
        # Limita o máximo de resultados se for muito grande
        if max_results > 500:
            max_results = 500
        
        # Insere a busca no banco e usa o ID como identificador da tarefa
        busca_id = await insert_busca(
            regiao=params.region,
            tipo_empresa=params.business_type,
            palavras_chave=params.keywords,
            qtd_max=max_results,
            status="waiting"  # Status inicial: aguardando processamento
        )
        
        # Usa o ID da busca como parte do task_id
        task_id = f"task_{busca_id}"
        
        # Inicializa o status da tarefa
        tasks_results[task_id] = {
            "status": "queued",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "params": {
                "region": params.region,
                "business_type": params.business_type,
                "keywords": params.keywords,
                "max_results": max_results
            },
            "busca_id": busca_id,
            "queue_position": "pending"  # Será atualizado pelo processador de fila
        }
        
        return {
            "message": "Requisição adicionada à fila de processamento",
            "task_id": task_id,
            "busca_id": busca_id,
            "max_results": max_results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/task/{task_id}")
async def get_task_status(task_id: str):
    if task_id not in tasks_results:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    
    task_data = tasks_results[task_id].copy()
    
    # Verificar status atual no banco de dados se tiver busca_id
    if "busca_id" in task_data:
        busca_id = task_data["busca_id"]
        try:
            # Obtém informações atualizadas do banco
            busca_info = await get_busca_by_id(busca_id)
            if busca_info:
                # Atualiza o status baseado no banco de dados
                db_status = busca_info.get("status", "")
                if db_status == "concluido":
                    task_data["status"] = "completed"
                elif db_status == "error":
                    task_data["status"] = "error"
                elif db_status == "processing":
                    task_data["status"] = "in_progress"
                elif db_status == "waiting":
                    task_data["status"] = "queued"
                
                # Atualiza no dicionário local também
                tasks_results[task_id]["status"] = task_data["status"]
                
                # Adiciona informações do banco de dados
                task_data["db_status"] = db_status
            
            # Verifica se temos leads no banco para essa busca
            leads = await get_leads_by_busca_id(busca_id)
            task_data["db_leads_count"] = len(leads)
        except Exception as e:
            task_data["db_error"] = str(e)
      # Adiciona a posição na fila (queue_position) às informações da tarefa
    if "busca_id" in task_data:
        busca_id = task_data["busca_id"]
        queue_position = get_queue_position(busca_id)
        if queue_position is not None:
            # Se position for 0, significa que está em processamento
            if queue_position == 0:
                task_data["status"] = "in_progress"
                task_data["queue_position"] = "processing"
            else:
                task_data["queue_position"] = queue_position
    
    return task_data

# Endpoint para listar todas as tarefas
@app.get("/tasks")
async def list_tasks():
    tasks_list = []
    
    for task_id, task_data in tasks_results.items():
        task_info = {
            "task_id": task_id,
            "status": task_data["status"],
            "created_at": task_data.get("created_at", "desconhecido")
        }
        
        # Adiciona ID da busca se disponível
        if "busca_id" in task_data:
            task_info["busca_id"] = task_data["busca_id"]
            
            # Adiciona contagem de leads para tarefas concluídas
            if task_data["status"] == "completed":
                task_info["leads_count"] = task_data.get("leads_count", 0)
                
        tasks_list.append(task_info)
    
    return {
        "total_tasks": len(tasks_list),
        "tasks": tasks_list
    }

@app.get("/queue/start")
async def start_queue():
    """Inicia o processador de fila"""
    try:
        start_queue_processor()
        return {"status": "success", "message": "Processador de fila iniciado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/queue/stop")
async def stop_queue():
    """Para o processador de fila"""
    try:
        stop_queue_processor()
        return {"status": "success", "message": "Processador de fila parado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/queue/status")
async def queue_status():
    """Retorna o status atual da fila de processamento"""
    try:
        from src.utils import with_connection
        
        async def get_queue_stats(conn):
            stats = {}
            
            # Contagem de buscas por status
            status_query = """
                SELECT status, COUNT(*) as count
                FROM buscas
                GROUP BY status
            """
            status_rows = await conn.fetch(status_query)
            status_counts = {row['status']: row['count'] for row in status_rows}
            
            # Total de buscas na fila (waiting)
            stats["queue_size"] = status_counts.get("waiting", 0)
            
            # Total de buscas em processamento
            stats["processing"] = status_counts.get("processing", 0)
            
            # Total de buscas concluídas
            stats["completed"] = status_counts.get("concluido", 0)
            
            # Total de erros
            stats["errors"] = status_counts.get("error", 0)
            
            # Próximas buscas na fila (top 5)
            queue_query = """
                SELECT id, regiao, tipo_empresa, palavras_chave, qtd_max, data_busca
                FROM buscas
                WHERE status = 'waiting'
                ORDER BY id ASC
                LIMIT 5
            """
            queue_rows = await conn.fetch(queue_query)
            next_in_queue = []
            for i, row in enumerate(queue_rows):
                next_in_queue.append({
                    "position": i + 1,
                    "busca_id": row['id'],
                    "region": row['regiao'],
                    "business_type": row['tipo_empresa'],
                    "max_results": row['qtd_max'],
                    "queued_at": row['data_busca'].isoformat() if row['data_busca'] else None
                })
            
            stats["next_in_queue"] = next_in_queue
            
            # Buscas em processamento
            processing_query = """
                SELECT id, regiao, tipo_empresa, palavras_chave, qtd_max, data_busca
                FROM buscas
                WHERE status = 'processing'
                ORDER BY id ASC
            """
            processing_rows = await conn.fetch(processing_query)
            currently_processing = []
            for row in processing_rows:
                currently_processing.append({
                    "busca_id": row['id'],
                    "region": row['regiao'],
                    "business_type": row['tipo_empresa'],
                    "max_results": row['qtd_max'],
                    "started_at": row['data_busca'].isoformat() if row['data_busca'] else None
                })
            
            stats["currently_processing"] = currently_processing
            
            return stats
        
        return await with_connection(get_queue_stats)
    except Exception as e:
        from src.utils import log_exception
        log_exception("Erro ao obter status da fila")
        raise HTTPException(status_code=500, detail=str(e))

async def process_single_busca(busca: Dict[str, Any], task_id: str):
    """
    Processa uma única busca diretamente (não usa a fila)
    """
    try:
        # Processa a busca em batches
        result = await process_busca_in_batches(busca)
        
        # Atualiza o status da tarefa
        if task_id in tasks_results:
            if result["status"] == "completed":
                tasks_results[task_id]["status"] = "completed"
                tasks_results[task_id]["leads_count"] = result["total_leads"]
                tasks_results[task_id]["message"] = f"Finalizado com sucesso. {result['total_leads']} leads encontrados."
            else:
                tasks_results[task_id]["status"] = "error"
                tasks_results[task_id]["error"] = result.get("error", "Erro desconhecido")
    except Exception as e:
        from src.utils import log_exception
        
        # Em caso de erro, atualiza o status
        if task_id in tasks_results:
            tasks_results[task_id]["status"] = "error"
            tasks_results[task_id]["error"] = str(e)
        
        # Atualiza o status no banco de dados
        if busca and "id" in busca:
            await update_busca_status(busca["id"], "error")
            
        # Log do erro usando a função centralizada
        log_exception(f"Erro ao processar busca {busca['id'] if busca and 'id' in busca else 'desconhecido'}")

@app.post("/task/{busca_id}/process")
async def process_task_now(busca_id: int, background_tasks: BackgroundTasks):
    """Processa uma tarefa específica imediatamente (fora da fila)"""
    try:
        # Obtém a busca do banco de dados
        busca = await get_busca_by_id(busca_id)
        if not busca:
            raise HTTPException(status_code=404, detail="Busca não encontrada")
        
        # Verifica status atual - não podemos processar algo que já está em processamento
        if busca.get("status") == "processing":
            return {
                "message": "A busca já está em processamento",
                "busca_id": busca_id,
                "status": "processing"
            }
        
        # Cria o task_id correspondente
        task_id = f"task_{busca_id}"
        
        # Atualiza o status para processando
        await update_busca_status(busca_id, "processing")
        
        # Atualiza o status no dicionário de tarefas se existir
        if task_id in tasks_results:
            tasks_results[task_id]["status"] = "in_progress"
        
        # Processa a busca em background
        background_tasks.add_task(
            process_single_busca, 
            busca, 
            task_id
        )
        
        return {
            "message": "Processamento iniciado",
            "busca_id": busca_id,
            "task_id": task_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/queue/reset-stuck-tasks")
async def reset_stuck_tasks():
    """
    Limpa tarefas que ficaram presas em status de processamento por muito tempo
    """
    try:
        from src.utils import with_connection
        
        async def reset_tasks(conn):
            # Encontra buscas que estão presas no status "processing"
            query = """
                UPDATE buscas 
                SET status = 'waiting' 
                WHERE status = 'processing'
                RETURNING id
            """
            rows = await conn.fetch(query)
            
            # Conta quantas tarefas foram resetadas
            reset_count = len(rows)
            
            # Registra os IDs que foram resetados
            reset_ids = [row['id'] for row in rows]
            
            return {
                "status": "success", 
                "reset_count": reset_count,
                "reset_ids": reset_ids,
                "message": f"{reset_count} tarefas presas foram resetadas para status 'waiting'"
            }
        
        return await with_connection(reset_tasks)
    except Exception as e:
        from src.utils import log_exception
        log_exception("Erro ao resetar tarefas presas")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/queue/cancel-task/{busca_id}")
async def cancel_task(busca_id: int):
    """
    Cancela uma tarefa específica, independente do seu status atual
    """
    try:
        # Verifica se a busca existe
        busca = await get_busca_by_id(busca_id)
        if not busca:
            raise HTTPException(status_code=404, detail="Busca não encontrada")
        
        # Atualiza para status de erro (ou poderia ser um status específico de "cancelado")
        await update_busca_status(busca_id, "error")
        
        # Atualiza o status no dicionário de tarefas se existir
        task_id = f"task_{busca_id}"
        if task_id in tasks_results:
            tasks_results[task_id]["status"] = "canceled"
            tasks_results[task_id]["message"] = "Tarefa cancelada pelo usuário"
        
        return {
            "status": "success",
            "message": f"Busca ID {busca_id} foi cancelada com sucesso",
            "busca_id": busca_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/queue/process-waiting")
async def process_waiting_tasks():
    """
    Força o processamento imediato da próxima tarefa em espera
    """
    try:
        from src.utils import with_connection, count_tasks_by_status, log_exception
        
        # Verifica se há tarefas em espera
        waiting_count = await count_tasks_by_status('waiting')
        
        if waiting_count == 0:
            return {
                "status": "info",
                "message": "Não há tarefas em espera para processar"
            }
        
        async def process_next_task(conn):
            # Obtém a próxima tarefa na fila
            next_query = """
                SELECT id FROM buscas 
                WHERE status = 'waiting'
                ORDER BY id ASC
                LIMIT 1
            """
            next_id = await conn.fetchval(next_query)
            
            if next_id:
                # Atualiza o status para processing diretamente pelo conn
                update_query = "UPDATE buscas SET status = 'processing' WHERE id = $1"
                await conn.execute(update_query, next_id)
                
                return next_id
            return None
        
        next_id = await with_connection(process_next_task)
        
        if next_id:
            # Obtém a busca completa
            busca = await get_busca_by_id(next_id)
            
            # Inicia o processamento em background
            task_id = f"task_{next_id}"
            from fastapi import BackgroundTasks
            background_tasks = BackgroundTasks()
            background_tasks.add_task(process_single_busca, busca, task_id)
            
            # Força a execução imediata (isso é uma técnica para iniciar a task em background)
            import asyncio
            asyncio.create_task(background_tasks())
            
            return {
                "status": "success",
                "message": f"Iniciado processamento da tarefa ID {next_id}",
                "task_id": task_id
            }
        
        return {
            "status": "error",
            "message": "Falha ao identificar a próxima tarefa na fila"
        }
    except Exception as e:
        from src.utils import log_exception
        log_exception("Erro ao processar próxima tarefa em espera")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/queue/force-process-next")
async def force_process_next():
    """
    Endpoint para forçar o processamento do próximo item da fila,
    útil para desbloquear a fila em situações de erro ou quando uma tarefa não inicia automaticamente.
    """
    try:
        from src.utils import manual_process_next_task
        from src.queue_processor import check_for_next_task
        
        # Força a verificação da próxima tarefa
        await check_for_next_task()
        
        return {"status": "success", "message": "Próxima tarefa da fila iniciada"}
    except Exception as e:
        from src.utils import log_exception
        log_exception("Erro ao forçar processamento da próxima tarefa")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/queue/diagnostics")
async def queue_diagnostics():
    """
    Retorna informações detalhadas de diagnóstico sobre o estado da fila
    e tarefas em processamento.
    """
    try:
        from src.utils import debug_queue_state, check_running_tasks
        
        # Obtém informações detalhadas da fila
        queue_info = await debug_queue_state()
        running_tasks_info = await check_running_tasks()
        
        from src.queue_processor import _running_tasks
        
        return {
            "queue_info": queue_info,
            "running_tasks": running_tasks_info,
            "task_count": len(_running_tasks)
        }
    except Exception as e:
        from src.utils import log_exception
        log_exception("Erro ao obter diagnósticos da fila")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
