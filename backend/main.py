import os
import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
from contextlib import asynccontextmanager
import yaml
from dotenv import load_dotenv

# Configuração de Paths
BACKEND_DIR = Path(__file__).parent
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Carregar Configs
load_dotenv(PROJECT_ROOT / ".env")

with open(PROJECT_ROOT / "config.yaml") as f:
    CONFIG = yaml.safe_load(f)

# Importar módulos da aplicação
from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Form, Body
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse

from backend.app.api.schemas import *
from backend.app.core.parser import extrair_metadados, ValidationError
from backend.app.retry.throttler import init_throttler
from backend.app.utils.logger import setup_logging, get_logger
from backend.app.redis_client import redis_conn, get_redis_connection, set_execution_status, get_execution_status
from backend.celery_worker import processar_arquivo_task

# Diretórios
DATA_DIR = PROJECT_ROOT / Path(os.getenv("DATA_DIR", "data"))
INPUTS_DIR = DATA_DIR / "inputs"
LOGS_DIR = DATA_DIR / "logs"
for dir_path in [INPUTS_DIR, LOGS_DIR, DATA_DIR / "outputs", DATA_DIR / "checkpoints"]:
    dir_path.mkdir(parents=True, exist_ok=True)

# --- Lifespan e Configuração da Aplicação ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.logger = setup_logging(LOGS_DIR, "server", os.getenv("LOG_FORMAT", "legivel"), os.getenv("LOG_LEVEL", "INFO"))
    
    throttle_config = CONFIG.get('throttling', {}).get('limites', {})
    init_throttler(throttle_config)
    
    app.state.redis_pubsub = get_redis_connection().pubsub()
    
    app.state.logger.info("server_started")
    yield
    app.state.logger.info("server_shutdown")

app = FastAPI(title="Compositor de Músicas Educativas", lifespan=lifespan)

# Templates e Static
FRONTEND_DIR = PROJECT_ROOT / "frontend"
templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")


# --- Rotas da Interface ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/monitoring/{execucao_id}", response_class=HTMLResponse)
async def monitoring_page(request: Request, execucao_id: str):
    status = get_execution_status(execucao_id)
    if not status:
        raise HTTPException(status_code=404, detail="Execução não encontrada.")
    return templates.TemplateResponse("monitoring.html", {
        "request": request,
        "execucao_id": execucao_id,
        "arquivos": status.get('arquivos', [])
    })


# --- Rotas da API ---

@app.post("/api/upload", response_class=HTMLResponse)
async def upload_e_validar_arquivos(request: Request, files: List[UploadFile] = File(...)):
    """
    Recebe arquivos via HTMX, valida-os e retorna um fragmento de HTML com os resultados.
    """
    resultados = []
    all_valid = True
    for file in files:
        file_path = INPUTS_DIR / file.filename
        try:
            with open(file_path, "wb") as f:
                f.write(await file.read())
            
            metadados = extrair_metadados(file_path)
            resultados.append(ArquivoValidacao(
                arquivo=file.filename, valido=True, tema=metadados.tema,
                topico=metadados.topico, avisos=metadados.avisos
            ))
        except ValidationError as e:
            all_valid = False
            resultados.append(ArquivoValidacao(arquivo=file.filename, valido=False, erro=e.erro))
        except Exception as e:
            all_valid = False
            resultados.append(ArquivoValidacao(arquivo=file.filename, valido=False, erro=str(e)))
            
    return templates.TemplateResponse("partials/file_validation_results.html", {
        "request": request,
        "arquivos": resultados,
        "all_valid": all_valid
    })

@app.post("/api/execucoes/")
async def criar_execucao(request: IniciarExecucaoRequest):
    """
    Inicia uma nova execução, enfileirando as tarefas no Celery.
    """
    execucao_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger = get_logger()
    logger.info("execution_started", execucao_id=execucao_id, num_files=len(request.arquivos))

    # Validar que os arquivos existem
    for arquivo in request.arquivos:
        arquivo_path = INPUTS_DIR / arquivo
        if not arquivo_path.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Arquivo '{arquivo}' não encontrado. Por favor, faça o upload novamente."
            )

    # Salvar estado inicial no Redis
    arquivos_status = [
        StatusArquivo(arquivo=arq, status="aguardando", progresso_percentual=0).dict()
        for arq in request.arquivos
    ]
    status_inicial = ExecucaoStatus(
        execucao_id=execucao_id, status="inicializando", timestamp_inicio=datetime.now(),
        arquivos=arquivos_status, total_arquivos=len(request.arquivos),
        arquivos_concluidos=0, arquivos_em_processo=len(request.arquivos), arquivos_falhados=0
    )
    set_execution_status(execucao_id, status_inicial.dict())

    # Enfileirar tarefas no Celery
    for arquivo_nome in request.arquivos:
        processar_arquivo_task.delay(execucao_id, arquivo_nome, request.config.dict())

    return JSONResponse(content={"execucao_id": execucao_id, "status": "iniciado"})

@app.get("/api/execucoes/{execucao_id}/stream")
async def stream_execucao(execucao_id: str):
    """
    Stream de atualizações de status via SSE usando Redis Pub/Sub.
    CORRIGIDO: Melhor tratamento de erros e keepalive.
    """
    channel = f"execucao_status:{execucao_id}"
    logger = get_logger()
    
    async def event_generator():
        pubsub = None
        try:
            # Criar nova conexão Redis para este stream
            pubsub = get_redis_connection().pubsub()
            pubsub.subscribe(channel)
            
            logger.info("sse_connection_opened", execucao_id=execucao_id, channel=channel)
            
            # Enviar status inicial
            current_status = get_execution_status(execucao_id)
            if current_status:
                yield {
                    "event": "message",
                    "data": json.dumps({
                        "type": "full_status",
                        "payload": current_status
                    })
                }
                logger.debug("sse_sent_initial_status", execucao_id=execucao_id)
            else:
                logger.warning("sse_no_initial_status", execucao_id=execucao_id)
            
            # Timeout e contador de mensagens vazias
            import time
            last_message_time = time.time()
            keepalive_interval = 15  # segundos
            
            # Escutar mensagens
            for message in pubsub.listen():
                if message["type"] == "message":
                    last_message_time = time.time()
                    
                    # Enviar mensagem ao cliente
                    yield {
                        "event": "message",
                        "data": message["data"]
                    }
                    
                    logger.debug(
                        "sse_message_sent",
                        execucao_id=execucao_id,
                        data_preview=message["data"][:100]
                    )
                
                # Keepalive - enviar comentário a cada 15s
                elif time.time() - last_message_time > keepalive_interval:
                    yield {
                        "event": "ping",
                        "data": json.dumps({"type": "keepalive", "timestamp": time.time()})
                    }
                    last_message_time = time.time()
                    logger.debug("sse_keepalive_sent", execucao_id=execucao_id)
                    
        except Exception as e:
            logger.error(
                "sse_stream_error",
                execucao_id=execucao_id,
                error=str(e),
                exc_info=True
            )
            yield {
                "event": "error",
                "data": json.dumps({"type": "error", "message": str(e)})
            }
        finally:
            if pubsub:
                try:
                    pubsub.unsubscribe(channel)
                    pubsub.close()
                    logger.info("sse_connection_closed", execucao_id=execucao_id)
                except Exception as e:
                    logger.error("sse_cleanup_error", error=str(e))
    
    return EventSourceResponse(event_generator())

@app.get("/api/execucoes/{execucao_id}")
async def get_execucao_status_api(execucao_id: str):
    """Retorna o status atual de uma execução a partir do Redis."""
    status = get_execution_status(execucao_id)
    if not status:
        raise HTTPException(status_code=404, detail="Execução não encontrada.")
    return status