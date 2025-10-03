"""Nós do LangGraph refatorados para usar Saída Estruturada (Function Calling)."""

from typing import Literal, TypedDict, Tuple
from pydantic import BaseModel, Field

from backend.app.core.llm_client import get_chat_model, _detect_provider_from_model
from backend.app.retry.throttler import get_throttler
from backend.app.agents import prompts
from backend.app.utils.logger import get_logger, set_etapa_context
from backend.app.api.schemas import LetraMusical, ResultadoRevisao, LetraAjustada, MusicaState

logger = get_logger()

async def call_llm_with_structured_output(
    modelo_primario: str,
    modelo_fallback: str,
    system_prompt: str,
    user_prompt: str,
    output_schema: BaseModel
) -> Tuple[BaseModel, bool]:
    """
    Função helper para chamar um LLM com fallback e esperar uma saída estruturada.

    Essa função detecta o provedor a partir do nome do modelo ao invés de
    confiar em um atributo dinâmico nos objetos LLM, uma vez que alguns
    clientes de modelo podem não permitir a adição do atributo `provider`.

    Args:
        modelo_primario: Nome do modelo primário
        modelo_fallback: Nome do modelo de fallback
        system_prompt: Prompt de sistema
        user_prompt: Prompt do usuário
        output_schema: Esquema Pydantic esperado na resposta

    Returns:
        Tupla com a resposta convertida para o schema e um boolean indicando
        se o fallback foi usado.
    """
    throttler = get_throttler()
    usou_fallback = False

    async def attempt_call(model_name: str):
        chat_model = get_chat_model(model_name)
        structured_llm = chat_model.with_structured_output(output_schema)

        async def _api_call():
            return await structured_llm.ainvoke(f"{system_prompt}\n\n{user_prompt}")

        # Detectar o provedor baseado no nome do modelo, evitando acesso a
        # atributos dinâmicos que podem não existir
        provider = _detect_provider_from_model(model_name)
        return await throttler.call(provider, _api_call)

    try:
        resultado = await attempt_call(modelo_primario)
        return resultado, usou_fallback
    except Exception as e:
        logger.warning(
            "primary_model_failed",
            modelo=modelo_primario,
            erro=str(e),
            fallback=modelo_fallback,
        )
        usou_fallback = True
        try:
            resultado = await attempt_call(modelo_fallback)
            return resultado, usou_fallback
        except Exception as e2:
            logger.error(
                "fallback_model_failed",
                modelo=modelo_fallback,
                erro=str(e2),
            )
            raise e2


async def node_compositor(state: MusicaState) -> dict:
    ciclo = state['ciclo_atual']
    set_etapa_context(f"compositor_c{ciclo}")
    logger.info("compositor_start", ciclo=ciclo)

    config_ciclo = state['config'][f'ciclo_{ciclo}']
    system_prompt = prompts.COMPOSITOR_SYSTEM.format(tema=state['tema'], estilo=state['estilo'])
    user_prompt = prompts.COMPOSITOR_PROMPT.format(
        tema=state['tema'], topico=state['topico'], estilo=state['estilo'], conteudo=state['conteudo']
    )
    try:
        resultado, _ = await call_llm_with_structured_output(
            config_ciclo['compositor']['primario'],
            config_ciclo['compositor']['fallback'],
            system_prompt,
            user_prompt,
            LetraMusical,
        )
        logger.info("compositor_success", ciclo=ciclo)
        return {
            "letra_atual": resultado.letra,
            "status_juridico": "pendente",
            "tentativas_juridico": 0,
            "etapa_atual": "revisor_juridico",
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
    user_prompt = prompts.REVISOR_JURIDICO_PROMPT.format(
        tema=state['tema'], topico=state['topico'], conteudo=state['conteudo'], letra=state['letra_atual']
    )
    try:
        resultado, _ = await call_llm_with_structured_output(
            config_ciclo['revisor_juridico']['primario'],
            config_ciclo['revisor_juridico']['fallback'],
            system_prompt,
            user_prompt,
            ResultadoRevisao,
        )
        # Lógica de consistência
        if resultado.status == "aprovado" and resultado.problemas:
            resultado.status = "reprovado"
        logger.info("revisor_juridico_complete", ciclo=ciclo, status=resultado.status)
        if resultado.status == "reprovado":
            return {
            "status_juridico": resultado.status, 
            "problemas_juridicos": resultado.problemas,
            "tentativas_juridico": state.get("tentativas_juridico", 0) + 1
            }
        else:
            return {"status_juridico": resultado.status, "problemas_juridicos": resultado.problemas}
            
    except Exception as e:
        """
        Em caso de falha no LLM (exemplo: erro de requisição ou exceção interna),
        incrementamos o número de tentativas e marcamos o status como "falha".

        O incremento é importante para que o roteador de revisão jurídica possa
        eventualmente encerrar o ciclo após exceder o limite de tentativas,
        evitando loops que estouram o limite de recursão do grafo. Sem esse
        incremento, o valor de `tentativas_juridico` permanece 0 e o fluxo
        retornará indefinidamente para o ajustador jurídico, causando o erro
        "Recursion limit of 100 reached without hitting a stop condition".
        """
        logger.error("revisor_juridico_failed", erro=str(e))
        return {
            "status_juridico": "falha",
            "tentativas_juridico": state.get("tentativas_juridico", 0) + 1,
        }


async def node_ajustador_juridico(state: MusicaState) -> dict:
    ciclo = state['ciclo_atual']
    set_etapa_context(f"ajustador_juridico_c{ciclo}")
    logger.info("ajustador_juridico_start", ciclo=ciclo)

    config_ciclo = state['config'][f'ciclo_{ciclo}']
    problemas_texto = "\n".join(f"- {p}" for p in state['problemas_juridicos'])
    system_prompt = prompts.AJUSTADOR_JURIDICO_SYSTEM
    user_prompt = prompts.AJUSTADOR_JURIDICO_PROMPT.format(
        problemas=problemas_texto, letra=state['letra_atual'], conteudo=state['conteudo']
    )
    try:
        resultado, _ = await call_llm_with_structured_output(
            config_ciclo['ajustador_juridico']['primario'],
            config_ciclo['ajustador_juridico']['fallback'],
            system_prompt,
            user_prompt,
            LetraAjustada,
        )
        logger.info("ajustador_juridico_complete", ciclo=ciclo)
        return {
            "letra_anterior": state['letra_atual'],
            "letra_atual": resultado.letra,
            "status_juridico": "pendente",
        }
    except Exception as e:
        """
        Se o ajustador jurídico falhar (por exemplo, devido a erro no LLM),
        incrementamos `tentativas_juridico` para permitir que o roteador avance
        após o número máximo de tentativas. Também marcamos o status como
        "falha" para sinalizar que a revisão não pode continuar com sucesso.
        """
        logger.error("ajustador_juridico_failed", erro=str(e))
        return {
            "status_juridico": "falha",
            "tentativas_juridico": state.get("tentativas_juridico", 0) + 1,
        }


async def node_revisor_linguistico(state: MusicaState) -> dict:
    ciclo = state['ciclo_atual']
    set_etapa_context(f"revisor_linguistico_c{ciclo}")
    logger.info("revisor_linguistico_start", ciclo=ciclo, tentativa=state['tentativas_linguistico'])
    config_ciclo = state['config'][f'ciclo_{ciclo}']
    system_prompt = prompts.REVISOR_LINGUISTICO_SYSTEM
    user_prompt = prompts.REVISOR_LINGUISTICO_PROMPT.format(
        tema=state['tema'], topico=state['topico'], letra=state['letra_atual']
    )
    try:
        resultado, _ = await call_llm_with_structured_output(
            config_ciclo['revisor_linguistico']['primario'],
            config_ciclo['revisor_linguistico']['fallback'],
            system_prompt,
            user_prompt,
            ResultadoRevisao,
        )
        # Lógica de consistência
        if resultado.status == "aprovado" and resultado.problemas:
            resultado.status = "reprovado"
        logger.info("revisor_linguistico_complete", ciclo=ciclo, status=resultado.status)
        if resultado.status == "reprovado":
            return {
            "status_linguistico": resultado.status, 
            "problemas_linguisticos": resultado.problemas,
            "tentativas_linguistico": state.get("tentativas_linguistico", 0) + 1
            }
        else:
            return {"status_linguistico": resultado.status, "problemas_linguisticos": resultado.problemas}
            
    except Exception as e:
        """
        Em caso de falha no revisor linguístico, incrementamos o contador de
        tentativas e retornamos um status de "falha". O incremento evita
        recursão infinita no grafo quando há erros consecutivos.
        """
        logger.error("revisor_linguistico_failed", erro=str(e))
        return {
            "status_linguistico": "falha",
            "tentativas_linguistico": state.get("tentativas_linguistico", 0) + 1,
        }


async def node_ajustador_linguistico(state: MusicaState) -> dict:
    ciclo = state['ciclo_atual']
    set_etapa_context(f"ajustador_linguistico_c{ciclo}")
    logger.info("ajustador_linguistico_start", ciclo=ciclo)
    config_ciclo = state['config'][f'ciclo_{ciclo}']
    problemas_texto = "\n".join(f"- {p}" for p in state['problemas_linguisticos'])
    system_prompt = prompts.AJUSTADOR_LINGUISTICO_SYSTEM
    user_prompt = prompts.AJUSTADOR_LINGUISTICO_PROMPT.format(
        problemas=problemas_texto, letra=state['letra_atual']
    )
    try:
        resultado, _ = await call_llm_with_structured_output(
            config_ciclo['ajustador_linguistico']['primario'],
            config_ciclo['ajustador_linguistico']['fallback'],
            system_prompt,
            user_prompt,
            LetraAjustada,
        )
        logger.info("ajustador_linguistico_complete", ciclo=ciclo)
        return {
            "letra_anterior": state['letra_atual'],
            "letra_atual": resultado.letra,
            "status_linguistico": "pendente",
        }
    except Exception as e:
        """
        Se o ajustador linguístico falhar, atualizamos `tentativas_linguistico`
        para que o roteamento possa eventualmente parar após exceder o limite
        definido. Marcamos também o status como "falha".
        """
        logger.error("ajustador_linguistico_failed", erro=str(e))
        return {
            "status_linguistico": "falha",
            "tentativas_linguistico": state.get("tentativas_linguistico", 0) + 1,
        }