import os
import json
from pathlib import Path
from datetime import datetime
from celery import Celery
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configurar caminhos
BACKEND_DIR = Path(__file__).parent
PROJECT_ROOT = BACKEND_DIR.parent
INPUTS_DIR = PROJECT_ROOT / "data" / "inputs"
OUTPUTS_DIR = PROJECT_ROOT / "data" / "outputs"
CHECKPOINTS_DIR = PROJECT_ROOT / "data" / "checkpoints"

# Garantir que os diretórios existam
INPUTS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)

from backend.app.core.parser import extrair_metadados, gerar_nome_saida
from backend.app.agents.graph import criar_workflow
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import aiosqlite
from backend.app.api.schemas import ConfigExecucao
from backend.app.redis_client import redis_conn, publish_status_update
from backend.app.utils.logger import get_logger
from backend.app.retry.throttler import init_throttler

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", 6379)
CELERY_BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
CELERY_RESULT_BACKEND = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

celery_app = Celery(
    "autoletras_worker",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["backend.celery_worker"]
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='America/Sao_Paulo',
    enable_utc=True,
)

logger = get_logger()

try:
    init_throttler({"openai": 5, "anthropic": 5, "google": 8, "deepseek": 3})
except Exception as e:
    logger.warning("throttler_init_failed", erro=str(e))

@celery_app.task(name="processar_arquivo_task")
def processar_arquivo_task(execucao_id: str, arquivo_nome: str, config_dict: dict):
    import asyncio
    config = ConfigExecucao(**config_dict)

    def update_status(etapa: str, progresso: int, detalhes: str = ""):
        try:
            publish_status_update(execucao_id, {
                "type": "file_progress",
                "arquivo": arquivo_nome,
                "etapa_atual": etapa,
                "progresso_percentual": progresso,
                "detalhes": detalhes,
            })
        except Exception as e:
            logger.warning("status_update_failed", erro=str(e))

    try:
        update_status("Iniciando", 5, "Extraindo metadados...")
        html_path = INPUTS_DIR / arquivo_nome
        if not html_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {html_path}")
        metadados = extrair_metadados(html_path)

        # Determinar caminho do arquivo de checkpoints
        checkpointer_path = str(CHECKPOINTS_DIR / f"{execucao_id}_{arquivo_nome}.db")

        # Preparar configuração dos modelos
        config_modelos = {"ciclo_1": config.ciclo_1.dict()}
        if config.num_ciclos >= 2 and config.ciclo_2:
            config_modelos["ciclo_2"] = config.ciclo_2.dict()
        if config.num_ciclos >= 3 and config.ciclo_3:
            config_modelos["ciclo_3"] = config.ciclo_3.dict()

        # Construir estado inicial
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
            "metricas": {"compositor": {}, "custo_total": 0.0},
        }

        thread_id = f"{execucao_id}_{arquivo_nome}"
        config_exec = {"configurable": {"thread_id": thread_id}, "recursion_limit": 100}
        update_status("Processando Workflow", 20, "Iniciando composição...")

        # Função assíncrona que abre a conexão SQLite, compila e executa o grafo
        async def _run_workflow():
            async with aiosqlite.connect(checkpointer_path) as conn:
                saver = AsyncSqliteSaver(conn)
                builder = criar_workflow(config.num_ciclos)
                graph = builder.compile(checkpointer=saver)
                return await graph.ainvoke(initial_state, config_exec)

        # Executar o grafo de forma assíncrona
        resultado = asyncio.run(_run_workflow())

        update_status("Finalizando", 90, "Salvando resultado...")
        output_nome = gerar_nome_saida(html_path, metadados.topico, config.radical, config.id_estilo)
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
                    "ciclos_executados": config.num_ciclos,
                },
                "letra": resultado["letra_atual"],
                "metricas": resultado.get("metricas", {}),
            }, f, ensure_ascii=False, indent=2)
        update_status("Concluído", 100, f"Output: {output_nome}")
        publish_status_update(execucao_id, {
            "type": "file_result",
            "arquivo": arquivo_nome,
            "status": "concluido",
            "output_gerado": output_nome,
        })
        return {"sucesso": True, "output": output_nome}
    except Exception as e:
        logger.error("celery_task_failed", arquivo=arquivo_nome, erro=str(e), exc_info=True)
        publish_status_update(execucao_id, {
            "type": "file_result",
            "arquivo": arquivo_nome,
            "status": "falha",
            "erro": str(e),
        })
        return {"sucesso": False, "erro": str(e)}