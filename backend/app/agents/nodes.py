"""Nós do LangGraph refatorados para usar Saída Estruturada (Function Calling)."""
from typing import Literal, TypedDict
from langchain_core.pydantic_v1 import BaseModel, Field

from backend.app.core.llm_client import get_chat_model
from backend.app.retry.throttler import get_throttler
from backend.app.agents import prompts
from backend.app.utils.logger import get_logger, set_etapa_context
from backend.app.api.schemas import LetraMusical, ResultadoRevisao, LetraAjustada, MusicaState

logger = get_logger()

# --- Nós do Grafo com Saída Estruturada ---

async def call_llm_with_structured_output(
    modelo_primario: str,
    modelo_fallback: str,
    system_prompt: str,
    user_prompt: str,
    output_schema: BaseModel
) -> (BaseModel, bool):
    """
    Função helper para chamar um LLM com fallback e esperar uma saída estruturada.
    """
    throttler = get_throttler()
    usou_fallback = False

    async def attempt_call(model_name):
        chat_model = get_chat_model(model_name)
        structured_llm = chat_model.with_structured_output(output_schema)
        
        async def _api_call():
            return await structured_llm.ainvoke(f"{system_prompt}\n\n{user_prompt}")
        
        provider = chat_model.provider
        return await throttler.call(provider, _api_call)

    try:
        resultado = await attempt_call(modelo_primario)
        return resultado, usou_fallback
    except Exception as e:
        logger.warning("primary_model_failed", modelo=modelo_primario, erro=str(e), fallback=modelo_fallback)
        usou_fallback = True
        try:
            resultado = await attempt_call(modelo_fallback)
            return resultado, usou_fallback
        except Exception as e2:
            logger.error("fallback_model_failed", modelo=modelo_fallback, erro=str(e2))
            raise e2


async def node_compositor(state: MusicaState) -> dict:
    ciclo = state['ciclo_atual']
    set_etapa_context(f"compositor_c{ciclo}")
    logger.info("compositor_start", ciclo=ciclo)

    config_ciclo = state['config'][f'ciclo_{ciclo}']
    system_prompt = prompts.COMPOSITOR_SYSTEM.format(tema=state['tema'], estilo=state['estilo'])
    user_prompt = prompts.COMPOSITOR_PROMPT.format(tema=state['tema'], topico=state['topico'], estilo=state['estilo'], conteudo=state['conteudo'])

    try:
        resultado, _ = await call_llm_with_structured_output(
            config_ciclo['compositor']['primario'],
            config_ciclo['compositor']['fallback'],
            system_prompt, user_prompt, LetraMusical
        )
        logger.info("compositor_success", ciclo=ciclo)
        return {
            "letra_atual": resultado.letra,
            "status_juridico": "pendente",
            "tentativas_juridico": 0,
            "etapa_atual": "revisor_juridico"
        }
    except Exception as e:
        logger.error("compositor_failed", erro=str(e))
        return {"status_juridico": "falha"}


async def node_revisor_juridico(state: MusicaState) -> dict:
    ciclo = state['ciclo_atual']
    set_etapa_context(f"revisor_juridico_c{ciclo}")
    logger.info("revisor_juridico_start", ciclo=ciclo, tentativa=state['tentativas_juridico'])

    config_ciclo = state['config'][f'ciclo_{ciclo}']
    system_prompt = prompts.REVISOR_JURIDICO_SYSTEM.format(tema=state['tema'])
    user_prompt = prompts.REVISOR_JURIDICO_PROMPT.format(tema=state['tema'], topico=state['topico'], conteudo=state['conteudo'], letra=state['letra_atual'])

    try:
        resultado, _ = await call_llm_with_structured_output(
            config_ciclo['revisor_juridico']['primario'],
            config_ciclo['revisor_juridico']['fallback'],
            system_prompt, user_prompt, ResultadoRevisao
        )
        # Lógica de consistência
        if resultado.status == "aprovado" and resultado.problemas:
            resultado.status = "reprovado"
        
        logger.info("revisor_juridico_complete", ciclo=ciclo, status=resultado.status)
        return {"status_juridico": resultado.status, "problemas_juridicos": resultado.problemas}
    except Exception as e:
        logger.error("revisor_juridico_failed", erro=str(e))
        return {"status_juridico": "falha"}


async def node_ajustador_juridico(state: MusicaState) -> dict:
    ciclo = state['ciclo_atual']
    set_etapa_context(f"ajustador_juridico_c{ciclo}")
    logger.info("ajustador_juridico_start", ciclo=ciclo)
    
    config_ciclo = state['config'][f'ciclo_{ciclo}']
    problemas_texto = "\n".join(f"- {p}" for p in state['problemas_juridicos'])
    system_prompt = prompts.AJUSTADOR_JURIDICO_SYSTEM
    user_prompt = prompts.AJUSTADOR_JURIDICO_PROMPT.format(problemas=problemas_texto, letra=state['letra_atual'], conteudo=state['conteudo'])

    try:
        resultado, _ = await call_llm_with_structured_output(
            config_ciclo['ajustador_juridico']['primario'],
            config_ciclo['ajustador_juridico']['fallback'],
            system_prompt, user_prompt, LetraAjustada
        )
        logger.info("ajustador_juridico_complete", ciclo=ciclo)
        return {"letra_anterior": state['letra_atual'], "letra_atual": resultado.letra, "status_juridico": "pendente"}
    except Exception as e:
        logger.error("ajustador_juridico_failed", erro=str(e))
        return {} # Mantém o estado atual em caso de falha


async def node_revisor_linguistico(state: MusicaState) -> dict:
    ciclo = state['ciclo_atual']
    set_etapa_context(f"revisor_linguistico_c{ciclo}")
    logger.info("revisor_linguistico_start", ciclo=ciclo, tentativa=state['tentativas_linguistico'])

    config_ciclo = state['config'][f'ciclo_{ciclo}']
    system_prompt = prompts.REVISOR_LINGUISTICO_SYSTEM
    user_prompt = prompts.REVISOR_LINGUISTICO_PROMPT.format(tema=state['tema'], topico=state['topico'], letra=state['letra_atual'])

    try:
        resultado, _ = await call_llm_with_structured_output(
            config_ciclo['revisor_linguistico']['primario'],
            config_ciclo['revisor_linguistico']['fallback'],
            system_prompt, user_prompt, ResultadoRevisao
        )
        if resultado.status == "aprovado" and resultado.problemas:
            resultado.status = "reprovado"
        if resultado.status == "reprovado" and not resultado.problemas:
             resultado.status = "aprovado"

        logger.info("revisor_linguistico_complete", ciclo=ciclo, status=resultado.status)
        return {"status_linguistico": resultado.status, "problemas_linguisticos": resultado.problemas}
    except Exception as e:
        logger.error("revisor_linguistico_failed", erro=str(e))
        return {"status_linguistico": "falha"}


async def node_ajustador_linguistico(state: MusicaState) -> dict:
    ciclo = state['ciclo_atual']
    set_etapa_context(f"ajustador_linguistico_c{ciclo}")
    logger.info("ajustador_linguistico_start", ciclo=ciclo)

    config_ciclo = state['config'][f'ciclo_{ciclo}']
    problemas_texto = "\n".join(f"- {p}" for p in state['problemas_linguisticos'])
    system_prompt = prompts.AJUSTADOR_LINGUISTICO_SYSTEM
    user_prompt = prompts.AJUSTADOR_LINGUISTICO_PROMPT.format(problemas=problemas_texto, letra=state['letra_atual'])
    
    try:
        resultado, _ = await call_llm_with_structured_output(
            config_ciclo['ajustador_linguistico']['primario'],
            config_ciclo['ajustador_linguistico']['fallback'],
            system_prompt, user_prompt, LetraAjustada
        )
        logger.info("ajustador_linguistico_complete", ciclo=ciclo)
        return {"letra_anterior": state['letra_atual'], "letra_atual": resultado.letra, "status_linguistico": "pendente"}
    except Exception as e:
        logger.error("ajustador_linguistico_failed", erro=str(e))
        return {}