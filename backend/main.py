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

# CORREÇÃO: Usar DATA_DIR corretamente
DATA_DIR_ENV = os.getenv("DATA_DIR", "data")
if not DATA_DIR_ENV.startswith("/"):
    DATA_DIR = PROJECT_ROOT / DATA_DIR_ENV
else:
    DATA_DIR = Path(DATA_DIR_ENV)

INPUTS_DIR = DATA_DIR / "inputs"
OUTPUTS_DIR = DATA_DIR / "outputs"
LOGS_DIR = DATA_DIR / "logs"
CHECKPOINTS_DIR = DATA_DIR / "checkpoints"

# Criar diretórios
for dir_path in [INPUTS_DIR, OUTPUTS_DIR, LOGS_DIR, CHECKPOINTS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

print(f"[BACKEND] DATA_DIR: {DATA_DIR}")
print(f"[BACKEND] INPUTS_DIR: {INPUTS_DIR}")
print(f"[BACKEND] OUTPUTS_DIR: {OUTPUTS_DIR}")

# Carregar config.yaml
try:
    with open(PROJECT_ROOT / "config.yaml") as f:
        CONFIG = yaml.safe_load(f)
except:
    CONFIG = {}
    print("[BACKEND] AVISO: config.yaml não encontrado, usando configurações padrão")

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

# --- Lifespan e Configuração da Aplicação ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.logger = setup_logging(LOGS_DIR, "server", os.getenv("LOG_FORMAT", "legivel"), os.getenv("LOG_LEVEL", "INFO"))
    
    throttle_config = CONFIG.get('throttling', {}).get('limites', {})
    init_throttler(throttle_config or {"openai": 5, "anthropic": 5, "google": 8, "deepseek": 3})
    
    app.state.redis_pubsub = get_redis_connection().pubsub()
    
    app.state.logger.info("server_started", data_dir=str(DATA_DIR), inputs_dir=str(INPUTS_DIR))
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

@app.get("/health")
async def health():
    """Health check endpoint para monitoramento de instâncias."""
    from datetime import datetime
    import os
    
    try:
        # Tentar contar execuções ativas
        execucoes = 0
        try:
            from backend.app.redis_client import redis_conn
            keys = redis_conn.keys("execucao:*")
            execucoes = len(keys) if keys else 0
        except:
            pass
        
        # Contar arquivos
        input_files = len(list(INPUTS_DIR.glob("*.html"))) if INPUTS_DIR.exists() else 0
        output_files = len(list(OUTPUTS_DIR.glob("*.json"))) if OUTPUTS_DIR.exists() else 0
        
        return {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "execucoes_ativas": execucoes,
            "instance_id": os.getenv("INSTANCE_ID", "unknown"),
            "data_dir": str(DATA_DIR),
            "input_files": input_files,
            "output_files": output_files
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.post("/api/upload", response_class=HTMLResponse)
async def upload_e_validar_arquivos(request: Request, files: List[UploadFile] = File(...)):
    """
    Recebe arquivos via HTMX, valida-os e retorna um fragmento de HTML com os resultados.
    """
    logger = get_logger()
    resultados = []
    all_valid = True
    
    logger.info(f"Recebendo {len(files)} arquivo(s) para upload em {INPUTS_DIR}")
    
    for file in files:
        file_path = INPUTS_DIR / file.filename
        try:
            # CORREÇÃO: Garantir que o arquivo seja salvo no diretório correto
            logger.info(f"Salvando arquivo: {file.filename} em {file_path}")
            
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)
            
            logger.info(f"Arquivo salvo com sucesso: {file_path}")
            
            # Validar
            metadados = extrair_metadados(file_path)
            resultados.append(ArquivoValidacao(
                arquivo=file.filename, valido=True, tema=metadados.tema,
                topico=metadados.topico, avisos=metadados.avisos
            ))
        except ValidationError as e:
            all_valid = False
            resultados.append(ArquivoValidacao(arquivo=file.filename, valido=False, erro=e.erro))
            logger.error(f"Erro de validação para {file.filename}: {e.erro}")
        except Exception as e:
            all_valid = False
            resultados.append(ArquivoValidacao(arquivo=file.filename, valido=False, erro=str(e)))
            logger.error(f"Erro ao processar {file.filename}: {str(e)}")
    
    # Listar arquivos no diretório após upload
    if INPUTS_DIR.exists():
        files_in_dir = list(INPUTS_DIR.glob("*.html"))
        logger.info(f"Arquivos no diretório {INPUTS_DIR}: {[f.name for f in files_in_dir]}")
            
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
    logger.info(f"execution_started: {execucao_id}, arquivos: {request.arquivos}, inputs_dir: {INPUTS_DIR}")

    # CORREÇÃO: Validar que os arquivos existem no diretório correto
    arquivos_encontrados = []
    arquivos_faltando = []
    
    for arquivo in request.arquivos:
        arquivo_path = INPUTS_DIR / arquivo
        if arquivo_path.exists():
            arquivos_encontrados.append(arquivo)
            logger.info(f"Arquivo confirmado: {arquivo_path}")
        else:
            arquivos_faltando.append(arquivo)
            logger.error(f"Arquivo não encontrado: {arquivo_path}")
    
    if arquivos_faltando:
        # Listar arquivos disponíveis
        arquivos_disponiveis = [f.name for f in INPUTS_DIR.glob("*.html")] if INPUTS_DIR.exists() else []
        raise HTTPException(
            status_code=400,
            detail=f"Arquivos não encontrados: {arquivos_faltando}. Arquivos disponíveis: {arquivos_disponiveis}"
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
        logger.info(f"Enfileirando tarefa para: {arquivo_nome}")
        processar_arquivo_task.delay(execucao_id, arquivo_nome, request.config.dict())

    return JSONResponse(content={"execucao_id": execucao_id, "status": "iniciado"})


@app.get("/api/execucoes/{execucao_id}/stream")
async def stream_execucao(execucao_id: str):
    """Stream de atualizações via SSE."""
    channel = f"execucao_status:{execucao_id}"
    logger = get_logger()
    
    async def event_generator():
        pubsub = None
        try:
            import redis
            import asyncio
            import time
            
            # Conexão Redis síncrona
            r = redis.StrictRedis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                db=0,
                decode_responses=True
            )
            
            pubsub = r.pubsub(ignore_subscribe_messages=True)
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
            
            last_message_time = time.time()
            keepalive_interval = 15
            
            while True:
                # get_message com timeout (não-bloqueante)
                message = pubsub.get_message(timeout=1.0)
                
                if message and message['type'] == 'message':
                    last_message_time = time.time()
                    
                    yield {
                        "event": "message",
                        "data": message["data"]
                    }
                    
                    logger.debug("sse_message_sent", execucao_id=execucao_id)
                
                # Keepalive
                elif time.time() - last_message_time > keepalive_interval:
                    yield {
                        "event": "ping",
                        "data": json.dumps({"type": "keepalive", "timestamp": time.time()})
                    }
                    last_message_time = time.time()
                
                # Liberar event loop
                await asyncio.sleep(0.1)
                    
        except Exception as e:
            logger.error("sse_stream_error", execucao_id=execucao_id, error=str(e), exc_info=True)
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