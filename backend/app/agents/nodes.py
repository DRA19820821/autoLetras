"""Nós do LangGraph para processamento de letras."""
import json
from typing import Literal
from pydantic import BaseModel, ValidationError

from app.core.llm_client import LLMClient, get_provider
from app.retry.throttler import get_throttler
from app.agents import prompts
from app.utils.logger import get_logger, set_etapa_context

logger = get_logger()


class ResultadoRevisao(BaseModel):
    """Resultado de revisão."""
    status: Literal["aprovado", "reprovado"]
    problemas: list[str]
    letra_recebida: str


class ResultadoAjuste(BaseModel):
    """Resultado de ajuste."""
    letra: str


class MusicaState(dict):
    """Estado do workflow de composição."""
    # Dados do arquivo
    arquivo: str
    tema: str
    topico: str
    conteudo: str
    estilo: str
    
    # Controle de fluxo
    ciclo_atual: int
    etapa_atual: str
    
    # Conteúdo em evolução
    letra_atual: str
    letra_anterior: str | None
    problemas_juridicos: list[str]
    problemas_linguisticos: list[str]
    
    # Contadores de loop
    tentativas_juridico: int
    tentativas_linguistico: int
    
    # Status
    status_juridico: Literal["pendente", "aprovado", "reprovado", "falha"]
    status_linguistico: Literal["pendente", "aprovado", "reprovado", "falha"]
    
    # Configuração (modelos por ciclo e função)
    config: dict
    
    # Métricas
    metricas: dict


# Cliente LLM global
llm_client = LLMClient()


async def node_compositor(state: MusicaState) -> MusicaState:
    """
    Nó compositor - cria letra inicial da música.
    """
    set_etapa_context(f"compositor_c{state['ciclo_atual']}")
    ciclo = state['ciclo_atual']
    
    logger.info("compositor_start", ciclo=ciclo)
    
    # Obter modelos configurados
    config_ciclo = state['config'][f'ciclo_{ciclo}']
    modelo_primario = config_ciclo['compositor']['primario']
    modelo_fallback = config_ciclo['compositor']['fallback']
    
    # Construir prompt
    system_prompt = prompts.COMPOSITOR_SYSTEM.format(
        tema=state['tema'],
        estilo=state['estilo']
    )
    user_prompt = prompts.COMPOSITOR_PROMPT.format(
        tema=state['tema'],
        topico=state['topico'],
        estilo=state['estilo'],
        conteudo=state['conteudo']
    )
    
    # Chamar com throttling e fallback
    provider_primario = get_provider(modelo_primario)
    throttler = get_throttler()
    
    try:
        async def _call():
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            return await llm_client.chamar_com_fallback(
                modelo_primario,
                modelo_fallback,
                full_prompt
            )
        
        resposta, usou_fallback = await throttler.call(provider_primario, _call)
        
        # Parsear JSON
        try:
            resultado = json.loads(resposta.content)
            letra = resultado.get('letra', '')
            
            if not letra:
                raise ValueError("Letra vazia no resultado")
            
            # Atualizar estado
            state['letra_atual'] = letra
            state['status_juridico'] = 'pendente'
            
            # Atualizar métricas
            state['metricas']['compositor'][ciclo] = {
                'modelo_usado': resposta.modelo_usado,
                'tokens_in': resposta.tokens_input,
                'tokens_out': resposta.tokens_output,
                'custo': resposta.custo,
                'usou_fallback': usou_fallback
            }
            
            logger.info(
                "compositor_success",
                ciclo=ciclo,
                modelo=resposta.modelo_usado,
                custo=f"${resposta.custo:.4f}"
            )
            
            return state
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error("compositor_invalid_json", erro=str(e))
            state['status_juridico'] = 'falha'
            return state
    
    except Exception as e:
        logger.error("compositor_failed", erro=str(e))
        state['status_juridico'] = 'falha'
        return state


async def node_revisor_juridico(state: MusicaState) -> MusicaState:
    """
    Nó revisor jurídico - valida precisão jurídica da letra.
    """
    set_etapa_context(f"revisor_juridico_c{state['ciclo_atual']}")
    ciclo = state['ciclo_atual']
    
    logger.info("revisor_juridico_start", ciclo=ciclo, tentativa=state['tentativas_juridico'])
    
    # Obter modelos
    config_ciclo = state['config'][f'ciclo_{ciclo}']
    modelo_primario = config_ciclo['revisor_juridico']['primario']
    modelo_fallback = config_ciclo['revisor_juridico']['fallback']
    
    # Construir prompt
    system_prompt = prompts.REVISOR_JURIDICO_SYSTEM.format(tema=state['tema'])
    user_prompt = prompts.REVISOR_JURIDICO_PROMPT.format(
        tema=state['tema'],
        topico=state['topico'],
        conteudo=state['conteudo'],
        letra=state['letra_atual']
    )
    
    # Chamar com throttling
    provider_primario = get_provider(modelo_primario)
    throttler = get_throttler()
    
    try:
        async def _call():
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            return await llm_client.chamar_com_fallback(
                modelo_primario,
                modelo_fallback,
                full_prompt
            )
        
        resposta, usou_fallback = await throttler.call(provider_primario, _call)
        
        # Parsear e validar
        resultado_dict = json.loads(resposta.content)
        resultado = ResultadoRevisao(**resultado_dict)
        
        # Validar consistência
        if resultado.status == "aprovado" and resultado.problemas:
            logger.warning("revisor_inconsistente", msg="Aprovou mas listou problemas")
            resultado.status = "reprovado"
        
        # Atualizar estado
        state['status_juridico'] = resultado.status
        state['problemas_juridicos'] = resultado.problemas
        
        logger.info(
            "revisor_juridico_complete",
            ciclo=ciclo,
            status=resultado.status,
            num_problemas=len(resultado.problemas)
        )
        
        return state
        
    except Exception as e:
        logger.error("revisor_juridico_failed", erro=str(e))
        state['status_juridico'] = 'falha'
        return state


async def node_ajustador_juridico(state: MusicaState) -> MusicaState:
    """
    Nó ajustador jurídico - corrige problemas jurídicos apontados.
    """
    set_etapa_context(f"ajustador_juridico_c{state['ciclo_atual']}")
    ciclo = state['ciclo_atual']
    
    logger.info("ajustador_juridico_start", ciclo=ciclo, tentativa=state['tentativas_juridico'])
    
    # Obter modelos
    config_ciclo = state['config'][f'ciclo_{ciclo}']
    modelo_primario = config_ciclo['ajustador_juridico']['primario']
    modelo_fallback = config_ciclo['ajustador_juridico']['fallback']
    
    # Construir prompt
    problemas_texto = "\n".join(f"- {p}" for p in state['problemas_juridicos'])
    
    system_prompt = prompts.AJUSTADOR_JURIDICO_SYSTEM
    user_prompt = prompts.AJUSTADOR_JURIDICO_PROMPT.format(
        problemas=problemas_texto,
        letra=state['letra_atual'],
        conteudo=state['conteudo']
    )
    
    # Chamar com throttling
    provider_primario = get_provider(modelo_primario)
    throttler = get_throttler()
    
    try:
        async def _call():
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            return await llm_client.chamar_com_fallback(
                modelo_primario,
                modelo_fallback,
                full_prompt
            )
        
        resposta, usou_fallback = await throttler.call(provider_primario, _call)
        
        # Parsear
        resultado_dict = json.loads(resposta.content)
        resultado = ResultadoAjuste(**resultado_dict)
        
        # Atualizar estado
        state['letra_anterior'] = state['letra_atual']
        state['letra_atual'] = resultado.letra
        state['status_juridico'] = 'pendente'  # Resetar para nova revisão
        
        logger.info("ajustador_juridico_complete", ciclo=ciclo)
        
        return state
        
    except Exception as e:
        logger.error("ajustador_juridico_failed", erro=str(e))
        # Manter letra atual em caso de falha
        return state


async def node_revisor_linguistico(state: MusicaState) -> MusicaState:
    """
    Nó revisor linguístico - valida formatação e fonética.
    """
    set_etapa_context(f"revisor_linguistico_c{state['ciclo_atual']}")
    ciclo = state['ciclo_atual']
    
    logger.info("revisor_linguistico_start", ciclo=ciclo, tentativa=state['tentativas_linguistico'])
    
    # Obter modelos
    config_ciclo = state['config'][f'ciclo_{ciclo}']
    modelo_primario = config_ciclo['revisor_linguistico']['primario']
    modelo_fallback = config_ciclo['revisor_linguistico']['fallback']
    
    # Construir prompt
    system_prompt = prompts.REVISOR_LINGUISTICO_SYSTEM
    user_prompt = prompts.REVISOR_LINGUISTICO_PROMPT.format(
        tema=state['tema'],
        topico=state['topico'],
        letra=state['letra_atual']
    )
    
    # Chamar com throttling
    provider_primario = get_provider(modelo_primario)
    throttler = get_throttler()
    
    try:
        async def _call():
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            return await llm_client.chamar_com_fallback(
                modelo_primario,
                modelo_fallback,
                full_prompt
            )
        
        resposta, usou_fallback = await throttler.call(provider_primario, _call)
        
        # Parsear e validar
        resultado_dict = json.loads(resposta.content)
        resultado = ResultadoRevisao(**resultado_dict)
        
        # Validar consistência
        if resultado.status == "aprovado" and resultado.problemas:
            logger.warning("revisor_ling_inconsistente")
            resultado.status = "reprovado"
        
        # Atualizar estado
        state['status_linguistico'] = resultado.status
        state['problemas_linguisticos'] = resultado.problemas
        
        logger.info(
            "revisor_linguistico_complete",
            ciclo=ciclo,
            status=resultado.status,
            num_problemas=len(resultado.problemas)
        )
        
        return state
        
    except Exception as e:
        logger.error("revisor_linguistico_failed", erro=str(e))
        state['status_linguistico'] = 'falha'
        return state


async def node_ajustador_linguistico(state: MusicaState) -> MusicaState:
    """
    Nó ajustador linguístico - corrige problemas de formatação/fonética.
    """
    set_etapa_context(f"ajustador_linguistico_c{state['ciclo_atual']}")
    ciclo = state['ciclo_atual']
    
    logger.info("ajustador_linguistico_start", ciclo=ciclo, tentativa=state['tentativas_linguistico'])
    
    # Obter modelos
    config_ciclo = state['config'][f'ciclo_{ciclo}']
    modelo_primario = config_ciclo['ajustador_linguistico']['primario']
    modelo_fallback = config_ciclo['ajustador_linguistico']['fallback']
    
    # Construir prompt
    problemas_texto = "\n".join(f"- {p}" for p in state['problemas_linguisticos'])
    
    system_prompt = prompts.AJUSTADOR_LINGUISTICO_SYSTEM
    user_prompt = prompts.AJUSTADOR_LINGUISTICO_PROMPT.format(
        problemas=problemas_texto,
        letra=state['letra_atual']
    )
    
    # Chamar com throttling
    provider_primario = get_provider(modelo_primario)
    throttler = get_throttler()
    
    try:
        async def _call():
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            return await llm_client.chamar_com_fallback(
                modelo_primario,
                modelo_fallback,
                full_prompt
            )
        
        resposta, usou_fallback = await throttler.call(provider_primario, _call)
        
        # Parsear
        resultado_dict = json.loads(resposta.content)
        resultado = ResultadoAjuste(**resultado_dict)
        
        # Atualizar estado
        state['letra_anterior'] = state['letra_atual']
        state['letra_atual'] = resultado.letra
        state['status_linguistico'] = 'pendente'  # Resetar para nova revisão
        
        logger.info("ajustador_linguistico_complete", ciclo=ciclo)
        
        return state
        
    except Exception as e:
        logger.error("ajustador_linguistico_failed", erro=str(e))
        return state