import os
import json
from pathlib import Path
from datetime import datetime
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

BACKEND_DIR = Path(__file__).parent
PROJECT_ROOT = BACKEND_DIR.parent
INPUTS_DIR = PROJECT_ROOT / "data" / "inputs"
OUTPUTS_DIR = PROJECT_ROOT / "data" / "outputs"
CHECKPOINTS_DIR = PROJECT_ROOT / "data" / "checkpoints"

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

        checkpointer_path = str(CHECKPOINTS_DIR / f"{execucao_id}_{arquivo_nome}.db")

        config_modelos = {"ciclo_1": config.ciclo_1.dict()}
        if config.num_ciclos >= 2 and config.ciclo_2:
            config_modelos["ciclo_2"] = config.ciclo_2.dict()
        if config.num_ciclos >= 3 and config.ciclo_3:
            config_modelos["ciclo_3"] = config.ciclo_3.dict()

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
            "llms_usados": {},  # NOVO: Rastreamento de LLMs
            "metricas": {"compositor": {}, "custo_total": 0.0},
        }

        thread_id = f"{execucao_id}_{arquivo_nome}"
        config_exec = {"configurable": {"thread_id": thread_id}, "recursion_limit": 100}
        update_status("Processando Workflow", 20, "Iniciando composição...")

        # NOVO: Callback para monitorar ciclos e salvar outputs intermediários
        ciclos_salvos = []
        estado_acumulado = initial_state.copy()  # Manter estado completo
        
        async def _run_workflow():
            nonlocal estado_acumulado
            
            async with aiosqlite.connect(checkpointer_path) as conn:
                saver = AsyncSqliteSaver(conn)
                builder = criar_workflow(config.num_ciclos)
                graph = builder.compile(checkpointer=saver)
                
                # Executar e monitorar
                last_ciclo = 1
                async for state in graph.astream(initial_state, config_exec):
                    # Atualizar estado acumulado com os deltas
                    if isinstance(state, dict):
                        for key, value in state.items():
                            if isinstance(value, dict):
                                # Merge do estado
                                estado_acumulado.update(value)
                                
                                # Detectar mudança de ciclo
                                if 'ciclo_atual' in value:
                                    current_ciclo = value['ciclo_atual']
                                    
                                    # Se mudou de ciclo, salvar o ciclo anterior
                                    if current_ciclo > last_ciclo and last_ciclo not in ciclos_salvos:
                                        # Salvar output do ciclo que acabou de terminar
                                        await salvar_output_ciclo(
                                            html_path, metadados, config, 
                                            estado_acumulado,  # Usar estado acumulado
                                            last_ciclo,  # Ciclo que terminou
                                            execucao_id
                                        )
                                        ciclos_salvos.append(last_ciclo)
                                        
                                        # Update progress
                                        progresso = 20 + (last_ciclo * 60 // config.num_ciclos)
                                        update_status(
                                            f"Ciclo {last_ciclo} concluído",
                                            progresso,
                                            f"Output salvo: ciclo {last_ciclo}"
                                        )
                                    
                                    last_ciclo = current_ciclo
                
                # Retornar estado final acumulado
                return estado_acumulado
        
        async def salvar_output_ciclo(html_path, metadados, config, state, ciclo, exec_id):
            """Salva output de um ciclo específico."""
            output_nome = gerar_nome_saida(
                html_path, metadados.topico, config.radical, config.id_estilo
            )
            # Adicionar sufixo do ciclo
            output_nome = output_nome.replace('.json', f'_c{ciclo}.json')
            output_path = OUTPUTS_DIR / output_nome
            
            # Extrair LLMs usados neste ciclo
            llms_ciclo = state.get('llms_usados', {}).get(f'ciclo_{ciclo}', [])
            letra_atual = state.get('letra_atual', '')
            
            # Logging de debug
            logger.info(
                "salvando_ciclo",
                ciclo=ciclo,
                arquivo=output_nome,
                tem_letra=bool(letra_atual),
                tamanho_letra=len(letra_atual),
                num_llms=len(llms_ciclo)
            )
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump({
                    "metadata": {
                        "arquivo_origem": html_path.name,
                        "tema": metadados.tema,
                        "topico": metadados.topico,
                        "estilo": config.estilo,
                        "identificador_estilo": config.id_estilo,
                        "radical": config.radical,
                        "timestamp_geracao": datetime.now().isoformat(),
                        "ciclo": ciclo,
                        "ciclos_totais": config.num_ciclos,
                        "tentativas_juridico": state.get("tentativas_juridico", 0),
                        "tentativas_linguistico": state.get("tentativas_linguistico", 0),
                    },
                    "letra": letra_atual,
                    "llms_usados": llms_ciclo,
                    "metricas": state.get("metricas", {}),
                }, f, ensure_ascii=False, indent=2)
            
            logger.info(f"output_ciclo_salvo", ciclo=ciclo, arquivo=output_nome)

        resultado = asyncio.run(_run_workflow())

        # Salvar output final do último ciclo (se ainda não foi salvo)
        ultimo_ciclo = config.num_ciclos
        if ultimo_ciclo not in ciclos_salvos:
            output_nome = gerar_nome_saida(html_path, metadados.topico, config.radical, config.id_estilo)
            output_nome_final = output_nome.replace('.json', f'_c{ultimo_ciclo}.json')
            output_path = OUTPUTS_DIR / output_nome_final
            
            # Extrair LLMs usados no último ciclo
            llms_ciclo = resultado.get('llms_usados', {}).get(f'ciclo_{ultimo_ciclo}', [])
            
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
                        "ciclo": ultimo_ciclo,
                        "ciclos_totais": config.num_ciclos,
                        "tentativas_juridico": resultado.get("tentativas_juridico", 0),
                        "tentativas_linguistico": resultado.get("tentativas_linguistico", 0),
                    },
                    "letra": resultado["letra_atual"],
                    "llms_usados": llms_ciclo,
                    "metricas": resultado.get("metricas", {}),
                }, f, ensure_ascii=False, indent=2)

        update_status("Concluído", 100, f"Outputs gerados: {len(ciclos_salvos) + 1} ciclos")
        
        # Lista de todos os outputs gerados
        outputs_gerados = [
            output_nome.replace('.json', f'_c{i}.json') 
            for i in range(1, config.num_ciclos + 1)
        ]
        
        publish_status_update(execucao_id, {
            "type": "file_result",
            "arquivo": arquivo_nome,
            "status": "concluido",
            "output_gerado": ", ".join(outputs_gerados),
        })
        return {"sucesso": True, "outputs": outputs_gerados}
        
    except Exception as e:
        logger.error("celery_task_failed", arquivo=arquivo_nome, erro=str(e), exc_info=True)
        publish_status_update(execucao_id, {
            "type": "file_result",
            "arquivo": arquivo_nome,
            "status": "falha",
            "erro": str(e),
        })
        return {"sucesso": False, "erro": str(e)}