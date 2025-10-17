import os
import json
from pathlib import Path
from datetime import datetime
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

BACKEND_DIR = Path(__file__).parent
PROJECT_ROOT = BACKEND_DIR.parent

# CORREÇÃO: Usar DATA_DIR da variável de ambiente diretamente (sem duplicação)
DATA_DIR = os.getenv("DATA_DIR", "data")
if not DATA_DIR.startswith("/"):
    # Se for caminho relativo, resolver a partir do PROJECT_ROOT
    INSTANCE_DATA_DIR = PROJECT_ROOT / DATA_DIR
else:
    # Se for caminho absoluto, usar diretamente
    INSTANCE_DATA_DIR = Path(DATA_DIR)

INPUTS_DIR = INSTANCE_DATA_DIR / "inputs"
OUTPUTS_DIR = INSTANCE_DATA_DIR / "outputs"
CHECKPOINTS_DIR = INSTANCE_DATA_DIR / "checkpoints"
LOGS_DIR = INSTANCE_DATA_DIR / "logs"

# Criar diretórios se não existirem
for dir_path in [INPUTS_DIR, OUTPUTS_DIR, CHECKPOINTS_DIR, LOGS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

print(f"[CELERY] DATA_DIR: {DATA_DIR}")
print(f"[CELERY] INSTANCE_DATA_DIR: {INSTANCE_DATA_DIR}")
print(f"[CELERY] INPUTS_DIR: {INPUTS_DIR}")
print(f"[CELERY] OUTPUTS_DIR: {OUTPUTS_DIR}")

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
        """Atualiza status com logging detalhado."""
        logger.info(
            "attempting_status_update",
            execucao_id=execucao_id,
            arquivo=arquivo_nome,
            etapa=etapa,
            progresso=progresso,
            inputs_dir=str(INPUTS_DIR),
            outputs_dir=str(OUTPUTS_DIR)
        )
        
        try:
            message = {
                "type": "file_progress",
                "arquivo": arquivo_nome,
                "etapa_atual": etapa,
                "progresso_percentual": progresso,
                "detalhes": detalhes,
                "timestamp": datetime.now().isoformat()
            }
            
            # Testar conexão Redis antes de publicar
            redis_conn.ping()
            
            # Publicar mensagem
            publish_status_update(execucao_id, message)
            
            logger.info(
                "status_update_published",
                execucao_id=execucao_id,
                arquivo=arquivo_nome,
                progresso=progresso
            )
            
        except Exception as e:
            logger.error(
                "status_update_failed",
                execucao_id=execucao_id,
                arquivo=arquivo_nome,
                erro=str(e),
                exc_info=True
            )

    try:
        update_status("Iniciando", 5, "Extraindo metadados...")
        
        # CORREÇÃO: Verificar se o arquivo existe no diretório correto
        html_path = INPUTS_DIR / arquivo_nome
        logger.info(f"Procurando arquivo em: {html_path}")
        
        if not html_path.exists():
            # Tentar caminho alternativo (caso o arquivo tenha sido colocado em outro lugar)
            alt_path = PROJECT_ROOT / "data" / "inputs" / arquivo_nome
            if alt_path.exists():
                logger.info(f"Arquivo encontrado em caminho alternativo: {alt_path}")
                html_path = alt_path
            else:
                logger.error(f"Arquivo não encontrado em nenhum dos caminhos:")
                logger.error(f"  - {html_path}")
                logger.error(f"  - {alt_path}")
                raise FileNotFoundError(f"Arquivo não encontrado: {arquivo_nome}")
        
        logger.info(f"Processando arquivo: {html_path}")
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
            "llms_usados": {},
            "metricas": {"compositor": {}, "custo_total": 0.0},
        }

        thread_id = f"{execucao_id}_{arquivo_nome}"
        config_exec = {"configurable": {"thread_id": thread_id}, "recursion_limit": 100}
        update_status("Processando Workflow", 20, "Iniciando composição...")

        # Callback para monitorar ciclos e salvar outputs intermediários
        ciclos_salvos = []
        estado_acumulado = initial_state.copy()
        
        async def _run_workflow():
            nonlocal estado_acumulado
            
            async with aiosqlite.connect(checkpointer_path) as conn:
                saver = AsyncSqliteSaver(conn)
                builder = criar_workflow(config.num_ciclos)
                graph = builder.compile(checkpointer=saver)
                
                last_ciclo = 1
                step_count = 0
                
                async for state in graph.astream(initial_state, config_exec):
                    step_count += 1
                    
                    if step_count % 3 == 0:
                        progresso = min(20 + (step_count * 2), 95)
                        update_status(
                            f"Processando step {step_count}",
                            progresso,
                            f"Ciclo {last_ciclo} em andamento"
                        )
                    
                    if isinstance(state, dict):
                        for key, value in state.items():
                            if isinstance(value, dict):
                                estado_acumulado.update(value)
                                
                                if 'ciclo_atual' in value:
                                    current_ciclo = value['ciclo_atual']
                                    
                                    if current_ciclo > last_ciclo and last_ciclo not in ciclos_salvos:
                                        await salvar_output_ciclo(
                                            html_path, metadados, config, 
                                            estado_acumulado,
                                            last_ciclo,
                                            execucao_id
                                        )
                                        ciclos_salvos.append(last_ciclo)
                                        
                                        progresso = 20 + (last_ciclo * 60 // config.num_ciclos)
                                        update_status(
                                            f"Ciclo {last_ciclo} concluído",
                                            progresso,
                                            f"Output salvo: ciclo {last_ciclo}"
                                        )
                                    
                                    last_ciclo = current_ciclo
                
                return estado_acumulado
        
        async def salvar_output_ciclo(html_path, metadados, config, state, ciclo, exec_id):
            """Salva output de um ciclo específico."""
            output_nome = gerar_nome_saida(
                html_path, metadados.topico, config.radical, config.id_estilo
            )
            output_nome = output_nome.replace('.json', f'_c{ciclo}.json')
            output_path = OUTPUTS_DIR / output_nome
            
            llms_ciclo = state.get('llms_usados', {}).get(f'ciclo_{ciclo}', [])
            letra_atual = state.get('letra_atual', '')
            
            logger.info(
                "salvando_ciclo",
                ciclo=ciclo,
                arquivo=output_nome,
                output_path=str(output_path),
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
            
            logger.info("output_ciclo_salvo", ciclo=ciclo, arquivo=output_nome)

        resultado = asyncio.run(_run_workflow())

        # Salvar output final do último ciclo
        ultimo_ciclo = config.num_ciclos
        if ultimo_ciclo not in ciclos_salvos:
            output_nome = gerar_nome_saida(html_path, metadados.topico, config.radical, config.id_estilo)
            output_nome_final = output_nome.replace('.json', f'_c{ultimo_ciclo}.json')
            output_path = OUTPUTS_DIR / output_nome_final
            
            llms_ciclo = resultado.get('llms_usados', {}).get(f'ciclo_{ultimo_ciclo}', [])
            
            logger.info(f"Salvando output final em: {output_path}")
            
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
        
        outputs_gerados = [
            output_nome.replace('.json', f'_c{i}.json') 
            for i in range(1, config.num_ciclos + 1)
        ]
        
        publish_status_update(execucao_id, {
            "type": "file_result",
            "arquivo": arquivo_nome,
            "status": "concluido",
            "output_gerado": ", ".join(outputs_gerados),
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(
            "task_completed",
            arquivo=arquivo_nome,
            outputs=outputs_gerados,
            outputs_dir=str(OUTPUTS_DIR)
        )
        
        return {"sucesso": True, "outputs": outputs_gerados}
        
    except Exception as e:
        logger.error("celery_task_failed", arquivo=arquivo_nome, erro=str(e), exc_info=True)
        
        publish_status_update(execucao_id, {
            "type": "file_result",
            "arquivo": arquivo_nome,
            "status": "falha",
            "erro": str(e),
            "timestamp": datetime.now().isoformat()
        })
        
        return {"sucesso": False, "erro": str(e)}