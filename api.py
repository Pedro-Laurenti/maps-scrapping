from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import asyncio
import uvicorn
import json
import os
import sys
import subprocess
from typing import Optional, Dict, Any
from src.database import insert_busca, insert_leads, get_leads_by_busca_id

# Definição da aplicação FastAPI
app = FastAPI(
    title="Google Maps Scraper API",
    description="API para buscar informações de negócios no Google Maps",
    version="1.0.0"
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

def run_scraper_process(task_id: str, params: dict):
    """Executa o scraper em um processo separado"""
    # Salva os parâmetros em um arquivo temporário
    params_file = f"temp_params_{task_id}.json"
    with open(params_file, "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False)
    
    try:
        # Executa o script app.py em um processo separado
        # Não use text=True ou encoding para evitar problemas de codificação
        result = subprocess.run(
            [sys.executable, "app.py", params_file],
            capture_output=True
        )
        
        # Tenta processar a saída com tratamento de codificação
        try:
            # Tenta várias codificações comuns
            encodings = ['utf-8', 'latin1', 'cp1252']
            stdout_text = None
            
            for encoding in encodings:
                try:
                    stdout_text = result.stdout.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if stdout_text is None:
                # Se nenhuma codificação funcionar, use 'latin1' que aceita qualquer byte
                stdout_text = result.stdout.decode('latin1')
                
            # Limpa a saída para remover caracteres que podem causar problemas
            stdout_text = stdout_text.strip()
              # Tenta analisar como JSON
            if stdout_text:
                output_data = json.loads(stdout_text)
                
                # Obtém o ID da busca para salvar os leads
                busca_id = tasks_results[task_id].get("busca_id")
                
                # Salva os leads no banco de dados
                asyncio.run(insert_leads(busca_id, output_data))
                
                tasks_results[task_id] = {
                    "status": "completed",
                    "results": output_data,
                    "busca_id": busca_id,
                    "leads_count": len(output_data)
                }
            else:
                tasks_results[task_id] = {
                    "status": "error",
                    "message": "O processo retornou uma saída vazia"
                }
        except json.JSONDecodeError as je:
            # Registre detalhes para depuração
            error_msg = f"Erro ao processar JSON: {je}. "
            if stdout_text:
                # Mostra apenas os primeiros 200 caracteres da saída para evitar poluir o log
                preview = stdout_text[:200] + ('...' if len(stdout_text) > 200 else '')
                error_msg += f"Preview da saída: {preview}"
            
            tasks_results[task_id] = {
                "status": "error",
                "message": error_msg
            }
    except Exception as e:
        tasks_results[task_id] = {
            "status": "error",
            "message": str(e)
        }
    finally:
        # Remove o arquivo temporário
        if os.path.exists(params_file):
            os.unlink(params_file)

@app.post("/scrape")
async def scrape(params: ScraperParams, background_tasks: BackgroundTasks):
    try:
        import time
        # Insere a busca no banco e usa o ID como identificador da tarefa
        busca_id = await insert_busca(
            regiao=params.region,
            tipo_empresa=params.business_type,
            palavras_chave=params.keywords,
            qtd_max=params.max_results
        )
        
        # Usa o ID da busca como parte do task_id
        task_id = f"task_{busca_id}"
        
        # Inicializa o status da tarefa
        tasks_results[task_id] = {
            "status": "in_progress",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "params": params.dict(),
            "busca_id": busca_id
        }
        
        # Executa o scraper em segundo plano
        background_tasks.add_task(
            run_scraper_process, 
            task_id, 
            params.dict()
        )
        
        return {
            "message": "Requisição aceita para processamento",
            "task_id": task_id,
            "busca_id": busca_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/task/{task_id}")
async def get_task_status(task_id: str):
    if task_id not in tasks_results:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    
    task_data = tasks_results[task_id].copy()
    
    # Adiciona informações adicionais para depuração
    if task_data["status"] == "error" and "stderr" not in task_data and "message" in task_data:
        # Conserva a mensagem original de erro
        task_data["error_details"] = task_data["message"]
    
    # Adiciona informações do banco de dados se a tarefa estiver concluída
    if task_data.get("status") == "completed" and "busca_id" in task_data:
        busca_id = task_data["busca_id"]
        try:
            # Verifica se temos leads no banco para essa busca
            leads = await get_leads_by_busca_id(busca_id)
            task_data["db_leads_count"] = len(leads)
        except Exception as e:
            task_data["db_error"] = str(e)
    
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

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
