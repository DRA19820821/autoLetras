"""Aplicação FastAPI principal - CORRIGIDO."""
import os
import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List
from contextlib import asynccontextmanager

# CRÍTICO: Adicionar diretório backend ao path
# Isso permite que os imports 'app.*' funcionem
BACKEND_DIR = Path(__file__).parent
sys.path.insert(0, str(BACKEND_DIR))

import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.requests import Request
from sse_starlette.sse import EventSourceResponse

from app.api.schemas import *
from app.core.parser import extrair_metadados, gerar_nome_saida, ValidationError
from app.retry.throttler import init_throttler
from app.agents.graph import compilar_workflow
from app.agents.nodes import MusicaState
from app.utils.logger import setup_logging, get_logger, set_arquivo_context, clear_context

# Carregar configurações
load_dotenv()

# IMPORTANTE: Caminho base é o ROOT DO PROJETO (não backend/)
# Porque o servidor será executado do root
PROJECT_ROOT = BACKEND_DIR.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"

print(f"🔍 DEBUG - BACKEND_DIR: {BACKEND_DIR}")
print(f"🔍 DEBUG - PROJECT_ROOT: {PROJECT_ROOT}")
print(f"🔍 DEBUG - CONFIG_PATH: {CONFIG_PATH}")

if not CONFIG_PATH.exists():
    print(f"❌ ERRO: config.yaml não encontrado em {CONFIG_PATH}")
    sys.exit(1)

with open(CONFIG_PATH) as f:
    CONFIG = yaml.safe_load(f)

# Diretórios (relativos ao PROJECT_ROOT)
DATA_DIR = PROJECT_ROOT / Path(os.getenv("DATA_DIR", "data"))
INPUTS_DIR = DATA_DIR / "inputs"
OUTPUTS_DIR = DATA_DIR / "outputs"
LOGS_DIR = DATA_DIR / "logs"
CHECKPOINTS_DIR = DATA_DIR / "checkpoints"

print(f"🔍 DEBUG - DATA_DIR: {DATA_DIR}")
print(f"🔍 DEBUG - INPUTS_DIR: {INPUTS_DIR}")
print(f"🔍 DEBUG - FRONTEND: {PROJECT_ROOT / 'frontend'}")

# Criar diretórios
for dir_path in [INPUTS_DIR, OUTPUTS_DIR, LOGS_DIR, CHECKPOINTS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)
    print(f"✓ Diretório: {dir_path}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle da aplicação."""
    # Startup
    logger = setup_logging(
        LOGS_DIR / f"server_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "server",
        formato=os.getenv("LOG_FORMAT", "legivel"),
        nivel=os.getenv("LOG_LEVEL", "INFO")
    )
    
    # Inicializar throttler
    throttle_config = {
        "openai": int(os.getenv("THROTTLE_OPENAI", CONFIG['throttling']['limites']['openai'])),
        "anthropic": int(os.getenv("THROTTLE_ANTHROPIC", CONFIG['throttling']['limites']['anthropic'])),
        "google": int(os.getenv("THROTTLE_GOOGLE", CONFIG['throttling']['limites']['google'])),
        "deepseek": int(os.getenv("THROTTLE_DEEPSEEK", CONFIG['throttling']['limites']['deepseek'])),
    }
    init_throttler(throttle_config)
    
    # Validar API keys
    provedores = await validar_provedores()
    app.state.provedores_disponiveis = provedores
    
    logger.info("server_started", provedores=provedores)
    
    yield
    
    # Shutdown
    logger.info("server_shutdown")


app = FastAPI(title="Compositor de Músicas Educativas", lifespan=lifespan)

# Templates e static (relativos ao PROJECT_ROOT)
FRONTEND_DIR = PROJECT_ROOT / "frontend"

if not FRONTEND_DIR.exists():
    print(f"❌ ERRO: Diretório frontend não encontrado em {FRONTEND_DIR}")
    sys.exit(1)

print(f"✓ Frontend dir: {FRONTEND_DIR}")

templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")

# Estado global de execuções
execucoes: Dict[str, ExecucaoStatus] = {}
execucoes_tasks: Dict[str, asyncio.Task] = {}


async def validar_provedores() -> Dict[str, ProvedorStatus]:
    """Valida disponibilidade dos provedores."""
    from app.core.llm_client import LLMClient
    
    client = LLMClient()
    resultados = {}
    
    provedores_modelos = {
        "openai": "gpt-4-turbo",
        "anthropic": "claude-sonnet-4",
        "google": "gemini-pro",
        "deepseek": "deepseek-chat"
    }
    
    for provider, modelo in provedores_modelos.items():
        api_key = os.getenv(f"{provider.upper()}_API_KEY")
        
        if not api_key:
            resultados[provider] = ProvedorStatus(
                provedor=provider,
                disponivel=False,
                mensagem="API key não configurada"
            )
            continue
        
        try:
            # Teste mínimo
            await client.chamar(
                modelo,
                "teste",
                max_tokens=5,
                timeout_override=10
            )
            resultados[provider] = ProvedorStatus(
                provedor=provider,
                disponivel=True,
                mensagem="OK"
            )
        except Exception as e:
            resultados[provider] = ProvedorStatus(
                provedor=provider,
                disponivel=False,
                mensagem=str(e)[:100]
            )
    
    return resultados


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Página principal."""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "provedores": app.state.provedores_disponiveis
        }
    )


@app.post("/api/upload")
async def upload_arquivos(files: List[UploadFile] = File(...)):
    """Upload de arquivos HTML."""
    resultados = []
    
    print(f"📥 Recebidos {len(files)} arquivos para upload")
    
    for file in files:
        print(f"  - Processando: {file.filename}")
        
        # Salvar arquivo
        file_path = INPUTS_DIR / file.filename
        
        try:
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            
            print(f"    ✓ Salvo em: {file_path}")
            
            # Validar
            metadados = extrair_metadados(file_path)
            resultados.append(ArquivoValidacao(
                arquivo=file.filename,
                valido=True,
                tema=metadados.tema,
                topico=metadados.topico,
                avisos=metadados.avisos
            ))
            print(f"    ✓ Validado: {metadados.tema} - {metadados.topico}")
            
        except ValidationError as e:
            print(f"    ✗ Erro de validação: {e.erro}")
            resultados.append(ArquivoValidacao(
                arquivo=file.filename,
                valido=False,
                erro=e.erro
            ))
        except Exception as e:
            print(f"    ✗ Erro inesperado: {e}")
            resultados.append(ArquivoValidacao(
                arquivo=file.filename,
                valido=False,
                erro=str(e)
            ))
    
    return {"arquivos": resultados}


@app.post("/api/execucoes/")
async def criar_execucao(
    request: IniciarExecucaoRequest,
    background_tasks: BackgroundTasks
):
    """Inicia nova execução."""
    execucao_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print(f"\n🚀 Iniciando execução {execucao_id}")
    print(f"   Arquivos: {len(request.arquivos)}")
    print(f"   Ciclos: {request.config.num_ciclos}")
    print(f"   Estilo: {request.config.estilo}")
    
    # Criar status inicial
    arquivos_status = [
        StatusArquivo(arquivo=arq, status="aguardando")
        for arq in request.arquivos
    ]
    
    status = ExecucaoStatus(
        execucao_id=execucao_id,
        status="inicializando",
        timestamp_inicio=datetime.now(),
        arquivos=arquivos_status,
        total_arquivos=len(request.arquivos),
        arquivos_concluidos=0,
        arquivos_em_processo=0,
        arquivos_falhados=0
    )
    
    execucoes[execucao_id] = status
    
    # Iniciar processamento em background
    task = asyncio.create_task(
        processar_lote(execucao_id, request.arquivos, request.config)
    )
    execucoes_tasks[execucao_id] = task
    
    print(f"   ✓ Execução {execucao_id} iniciada")
    
    return {"execucao_id": execucao_id, "status": "iniciado"}


async def processar_lote(
    execucao_id: str,
    arquivos: List[str],
    config: ConfigExecucao
):
    """Processa lote de arquivos."""
    logger = get_logger()
    status = execucoes[execucao_id]
    
    # Setup logging para execução
    log_dir = LOGS_DIR / execucao_id
    setup_logging(log_dir, execucao_id)
    
    status.status = "processando"
    
    # Compilar workflow
    workflow = compilar_workflow(
        num_ciclos=config.num_ciclos,
        checkpointer_path=str(CHECKPOINTS_DIR / f"{execucao_id}.db")
    )
    
    # Processar até 10 arquivos em paralelo
    tasks = []
    for arquivo in arquivos[:10]:  # Máximo 10
        task = processar_arquivo(
            execucao_id,
            arquivo,
            config,
            workflow
        )
        tasks.append(task)
    
    # Aguardar conclusão
    resultados = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Atualizar status final
    status.status = "concluido"
    status.timestamp_fim = datetime.now()
    status.duracao_segundos = int(
        (status.timestamp_fim - status.timestamp_inicio).total_seconds()
    )
    
    logger.info("lote_concluido", execucao_id=execucao_id)


async def processar_arquivo(
    execucao_id: str,
    arquivo_nome: str,
    config: ConfigExecucao,
    workflow
) -> Dict:
    """Processa um arquivo individual."""
    logger = get_logger()
    status = execucoes[execucao_id]
    
    # Encontrar status do arquivo
    arq_status = next(a for a in status.arquivos if a.arquivo == arquivo_nome)
    arq_status.status = "processando"
    status.arquivos_em_processo += 1
    
    set_arquivo_context(arquivo_nome)
    
    try:
        # Extrair metadados
        html_path = INPUTS_DIR / arquivo_nome
        metadados = extrair_metadados(html_path)
        
        # Preparar configuração de modelos
        config_modelos = {
            "ciclo_1": config.ciclo_1.dict(),
        }
        if config.num_ciclos >= 2 and config.ciclo_2:
            config_modelos["ciclo_2"] = config.ciclo_2.dict()
        if config.num_ciclos >= 3 and config.ciclo_3:
            config_modelos["ciclo_3"] = config.ciclo_3.dict()
        
        # Estado inicial
        initial_state = {
            "arquivo": arquivo_nome,
            "tema": metadados.tema,
            "topico": metadados.topico,
            "conteudo": metadados.conteudo,
            "estilo": config.estilo,
            "ciclo_atual": 1,
            "etapa_atual": "compositor",
            "letra_atual": "",
            "letra_anterior": None,
            "problemas_juridicos": [],
            "problemas_linguisticos": [],
            "tentativas_juridico": 0,
            "tentativas_linguistico": 0,
            "status_juridico": "pendente",
            "status_linguistico": "pendente",
            "config": config_modelos,
            "metricas": {"compositor": {}, "custo_total": 0.0}
        }
        
        # Executar workflow
        thread_id = f"{execucao_id}_{arquivo_nome}"
        config_exec = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 100  # Aumentar limite para evitar erro prematuro
        }
        
        logger.info("workflow_starting", arquivo=arquivo_nome, thread_id=thread_id)
        
        try:
            # Invocar workflow de forma assíncrona
            resultado = await workflow.ainvoke(initial_state, config_exec)
            logger.info("workflow_completed", arquivo=arquivo_nome)
        except Exception as e:
            logger.error("workflow_execution_error", arquivo=arquivo_nome, erro=str(e))
            raise
        
        # Salvar output
        output_nome = gerar_nome_saida(
            html_path,
            metadados.topico,
            config.radical,
            config.id_estilo
        )
        
        output_path = OUTPUTS_DIR / output_nome
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "metadata": {
                    "arquivo_origem": arquivo_nome,
                    "tema": metadados.tema,
                    "topico": metadados.topico,
                    "estilo": config.estilo,
                    "identificador_estilo": config.id_estilo,
                    "radical": config.radical,
                    "timestamp_geracao": datetime.now().isoformat(),
                    "ciclos_executados": config.num_ciclos
                },
                "letra": resultado["letra_atual"],
                "metricas": resultado.get("metricas", {})
            }, f, ensure_ascii=False, indent=2)
        
        # Atualizar status
        arq_status.status = "concluido"
        arq_status.output_gerado = output_nome
        arq_status.progresso_percentual = 100
        status.arquivos_concluidos += 1
        status.arquivos_em_processo -= 1
        
        logger.info("arquivo_concluido", arquivo=arquivo_nome, output=output_nome)
        
        return {"sucesso": True, "output": output_nome}
        
    except Exception as e:
        logger.error("arquivo_falhou", arquivo=arquivo_nome, erro=str(e))
        arq_status.status = "falha"
        arq_status.erro = str(e)
        status.arquivos_falhados += 1
        status.arquivos_em_processo -= 1
        return {"sucesso": False, "erro": str(e)}
    
    finally:
        clear_context()


@app.get("/api/execucoes/{execucao_id}")
async def get_execucao(execucao_id: str):
    """Retorna status de uma execução."""
    if execucao_id not in execucoes:
        raise HTTPException(404, "Execução não encontrada")
    
    return execucoes[execucao_id]


@app.get("/api/execucoes/{execucao_id}/stream")
async def stream_execucao(execucao_id: str):
    """Stream SSE com updates da execução."""
    if execucao_id not in execucoes:
        raise HTTPException(404, "Execução não encontrada")
    
    async def event_generator():
        while True:
            status = execucoes[execucao_id]
            
            yield {
                "event": "status",
                "data": status.json()
            }
            
            if status.status in ["concluido", "cancelado", "erro"]:
                break
            
            await asyncio.sleep(2)  # Update a cada 2s
    
    return EventSourceResponse(event_generator())


@app.get("/api/provedores")
async def get_provedores():
    """Retorna status dos provedores."""
    return app.state.provedores_disponiveis


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "execucoes_ativas": len([e for e in execucoes.values() if e.status == "processando"])
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=True
    )