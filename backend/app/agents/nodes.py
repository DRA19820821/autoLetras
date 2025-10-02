"""Nós do LangGraph para processamento de letras - CORRIGIDO."""
import json
import re
from typing import Literal, TypedDict
from pydantic import BaseModel, ValidationError

from app.core.llm_client import LLMClient, get_provider
from app.retry.throttler import get_throttler
from app.agents import prompts
from app.utils.logger import get_logger, set_etapa_context

logger = get_logger()


def sanitizar_json(texto: str) -> str:
    """
    Remove caracteres de controle inválidos de um JSON.
    
    Args:
        texto: String JSON potencialmente com caracteres inválidos
        
    Returns:
        String JSON limpa
    """
    # Remover caracteres de controle exceto \n, \r, \t que são válidos quando escapados
    # Regex: remove caracteres ASCII de controle (0x00-0x1F) exceto \n \r \t
    texto_limpo = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', texto)
    return texto_limpo


class ResultadoRevisao(BaseModel):
    """Resultado de revisão."""
    status: Literal["aprovado", "reprovado"]
    problemas: list[str]
    letra_recebida: str


class ResultadoAjuste(BaseModel):
    """Resultado de ajuste."""
    letra: str


# TypedDict para o estado (para type hints melhores)
class MusicaState(TypedDict):
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
    ciclo = state['ciclo_atual']
    set_etapa_context(f"compositor_c{ciclo}")
    
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
        
        # Parsear JSON com sanitização
        try:
            content_limpo = sanitizar_json(resposta.content)
            resultado_dict = json.loads(content_limpo)
            letra = resultado.get('letra', '')
            
            if not letra:
                raise ValueError("Letra vazia no resultado")
            
            # Atualizar estado - retornar dict com updates
            updates = {
                'letra_atual': letra,
                'status_juridico': 'pendente',
                'tentativas_juridico': 0,  # Reset para este ciclo
                'etapa_atual': 'revisor_juridico'
            }
            
            # Atualizar métricas
            if 'compositor' not in state['metricas']:
                state['metricas']['compositor'] = {}
            
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
            
            # Retornar state atualizado
            return {**state, **updates}
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error("compositor_invalid_json", erro=str(e))
            return {**state, 'status_juridico': 'falha'}
    
    except Exception as e:
        logger.error("compositor_failed", erro=str(e))
        return {**state, 'status_juridico': 'falha'}


async def node_revisor_juridico(state: MusicaState) -> MusicaState:
    """
    Nó revisor jurídico - valida precisão jurídica da letra.
    """
    ciclo = state['ciclo_atual']
    set_etapa_context(f"revisor_juridico_c{ciclo}")
    
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
        
        # Parsear e validar JSON com sanitização
        try:
            content_limpo = sanitizar_json(resposta.content)
            resultado_dict = json.loads(content_limpo)
        resultado = ResultadoRevisao(**resultado_dict)
        
        # Validar consistência
        if resultado.status == "aprovado" and resultado.problemas:
            logger.warning("revisor_inconsistente", msg="Aprovou mas listou problemas")
            resultado.status = "reprovado"
        
        # Atualizar estado
        updates = {
            'status_juridico': resultado.status,
            'problemas_juridicos': resultado.problemas,
            'etapa_atual': 'decisor_juridico'
        }
        
        logger.info(
            "revisor_juridico_complete",
            ciclo=ciclo,
            status=resultado.status,
            num_problemas=len(resultado.problemas)
        )
        
        return {**state, **updates}
        
    except Exception as e:
        logger.error("revisor_juridico_failed", erro=str(e))
        return {**state, 'status_juridico': 'falha'}


async def node_ajustador_juridico(state: MusicaState) -> MusicaState:
    """
    Nó ajustador jurídico - corrige problemas jurídicos apontados.
    """
    ciclo = state['ciclo_atual']
    set_etapa_context(f"ajustador_juridico_c{ciclo}")
    
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
        
        # Parsear JSON com sanitização
        try:
            content_limpo = sanitizar_json(resposta.content)
            resultado_dict = json.loads(content_limpo)
        resultado = ResultadoAjuste(**resultado_dict)
        
        # Atualizar estado
        updates = {
            'letra_anterior': state['letra_atual'],
            'letra_atual': resultado.letra,
            'status_juridico': 'pendente',  # Resetar para nova revisão
            'etapa_atual': 'incrementador_juridico'
        }
        
        logger.info("ajustador_juridico_complete", ciclo=ciclo)
        
        return {**state, **updates}
        
    except Exception as e:
        logger.error("ajustador_juridico_failed", erro=str(e))
        # Manter letra atual em caso de falha
        return state


async def node_revisor_linguistico(state: MusicaState) -> MusicaState:
    """
    Nó revisor linguístico - valida formatação e fonética.
    """
    ciclo = state['ciclo_atual']
    set_etapa_context(f"revisor_linguistico_c{ciclo}")
    
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
        
        # Parsear e validar JSON com sanitização
        try:
            content_limpo = sanitizar_json(resposta.content)
            resultado_dict = json.loads(content_limpo)
            resultado = ResultadoRevisao(**resultado_dict)
        
        # Validar consistência - NÃO DEVE aprovar se tiver problemas
        if resultado.status == "aprovado" and resultado.problemas:
            logger.warning("revisor_ling_inconsistente", msg="Aprovou mas tem problemas - mudando para reprovado")
            resultado.status = "reprovado"
        
        # Se não tem problemas mas reprovou, aprovar
        if resultado.status == "reprovado" and not resultado.problemas:
            logger.warning("revisor_ling_inconsistente", msg="Reprovou mas sem problemas - mudando para aprovado")
            resultado.status = "aprovado"
        
        # Atualizar estado
        updates = {
            'status_linguistico': resultado.status,
            'problemas_linguisticos': resultado.problemas,
            'etapa_atual': 'decisor_linguistico'
        }
        
        logger.info(
            "revisor_linguistico_complete",
            ciclo=ciclo,
            status=resultado.status,
            num_problemas=len(resultado.problemas)
        )
        
        return {**state, **updates}
        
    except Exception as e:
        logger.error("revisor_linguistico_failed", erro=str(e))
        return {**state, 'status_linguistico': 'falha'}


async def node_ajustador_linguistico(state: MusicaState) -> MusicaState:
    """
    Nó ajustador linguístico - corrige problemas de formatação/fonética.
    """
    ciclo = state['ciclo_atual']
    set_etapa_context(f"ajustador_linguistico_c{ciclo}")
    
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
        
        # Parsear JSON com sanitização
        try:
            content_limpo = sanitizar_json(resposta.content)
            resultado_dict = json.loads(content_limpo)
        resultado = ResultadoAjuste(**resultado_dict)
        
        # Atualizar estado
        updates = {
            'letra_anterior': state['letra_atual'],
            'letra_atual': resultado.letra,
            'status_linguistico': 'pendente',  # Resetar para nova revisão
            'etapa_atual': 'incrementador_linguistico'
        }
        
        logger.info("ajustador_linguistico_complete", ciclo=ciclo)
        
        return {**state, **updates}
        
    except Exception as e:
        logger.error("ajustador_linguistico_failed", erro=str(e))
        return state