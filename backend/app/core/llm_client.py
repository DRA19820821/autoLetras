"""Cliente unificado para LLMs via LiteLLM."""
import os
import asyncio
from typing import Dict, Any, Optional
from pydantic import BaseModel
import litellm
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.utils.logger import get_logger

logger = get_logger()


class InvalidResponseError(Exception):
    """Resposta inválida do LLM."""
    pass


class RateLimitError(Exception):
    """Rate limit atingido."""
    def __init__(self, retry_after: int = 5):
        self.retry_after = retry_after
        super().__init__(f"Rate limit, retry após {retry_after}s")


class APIError5xx(Exception):
    """Erro 5xx da API."""
    pass


class LLMResponse(BaseModel):
    """Resposta estruturada de LLM."""
    content: str
    tokens_input: int
    tokens_output: int
    custo: float
    modelo_usado: str
    latencia_ms: int


# Mapeamento de provedores
PROVIDER_MAP = {
    "gpt-4": "openai",
    "gpt-4-turbo": "openai",
    "claude-sonnet-4-5": "anthropic",
    "claude-sonnet-4": "anthropic",
    "gemini-2.5-pro": "google",
    "gemini-pro": "google",
    "deepseek-r1": "deepseek",
    "deepseek-chat": "deepseek",
}


def get_provider(modelo: str) -> str:
    """Retorna provedor baseado no modelo."""
    for key, provider in PROVIDER_MAP.items():
        if key in modelo.lower():
            return provider
    return "openai"  # Default


# Custos aproximados por 1K tokens (USD)
CUSTOS_MODELOS = {
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "claude-sonnet-4-5": {"input": 0.003, "output": 0.015},
    "claude-sonnet-4": {"input": 0.003, "output": 0.015},
    "gemini-2.5-pro": {"input": 0.00125, "output": 0.005},
    "gemini-pro": {"input": 0.00125, "output": 0.005},
    "deepseek-r1": {"input": 0.001, "output": 0.002},
    "deepseek-chat": {"input": 0.0001, "output": 0.0002},
}


def calcular_custo(modelo: str, tokens_input: int, tokens_output: int) -> float:
    """Calcula custo de uma chamada."""
    custos = CUSTOS_MODELOS.get(modelo, {"input": 0.01, "output": 0.03})
    custo_input = (tokens_input / 1000) * custos["input"]
    custo_output = (tokens_output / 1000) * custos["output"]
    return custo_input + custo_output


class LLMClient:
    """Cliente unificado para chamadas de LLM com retry."""
    
    def __init__(self):
        # Configurar LiteLLM
        litellm.set_verbose = False
        self.timeout_base = 60
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type((TimeoutError, APIError5xx)),
    )
    async def chamar(
        self,
        modelo: str,
        prompt: str,
        temperatura: float = 0.7,
        max_tokens: int = 4000,
        timeout_override: Optional[int] = None,
    ) -> LLMResponse:
        """
        Chama LLM com retry automático.
        
        Args:
            modelo: Nome do modelo
            prompt: Prompt a enviar
            temperatura: Temperatura (criatividade)
            max_tokens: Máximo de tokens na resposta
            timeout_override: Override do timeout padrão
            
        Returns:
            LLMResponse com resultado
            
        Raises:
            RateLimitError: Se rate limit atingido
            APIError5xx: Se erro 5xx
            TimeoutError: Se timeout
            InvalidResponseError: Se resposta inválida
        """
        import time
        start = time.time()
        
        provider = get_provider(modelo)
        timeout = timeout_override or self.timeout_base
        
        try:
            # Chamar via LiteLLM
            response = await asyncio.to_thread(
                litellm.completion,
                model=modelo,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperatura,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            
            # Extrair resposta
            content = response.choices[0].message.content
            tokens_input = response.usage.prompt_tokens
            tokens_output = response.usage.completion_tokens
            
            # Calcular custo
            custo = calcular_custo(modelo, tokens_input, tokens_output)
            
            latencia_ms = int((time.time() - start) * 1000)
            
            logger.info(
                "llm_call_success",
                modelo=modelo,
                provider=provider,
                tokens_in=tokens_input,
                tokens_out=tokens_output,
                custo=f"${custo:.4f}",
                latencia_ms=latencia_ms,
            )
            
            return LLMResponse(
                content=content,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                custo=custo,
                modelo_usado=modelo,
                latencia_ms=latencia_ms,
            )
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Classificar erro
            if "rate limit" in error_str or "429" in error_str:
                retry_after = 5  # Tentar extrair do header se possível
                logger.warning(
                    "rate_limit",
                    modelo=modelo,
                    provider=provider,
                    retry_after=retry_after,
                )
                raise RateLimitError(retry_after)
            
            elif any(code in error_str for code in ["500", "502", "503", "504"]):
                logger.warning(
                    "api_5xx_error",
                    modelo=modelo,
                    provider=provider,
                    erro=str(e),
                )
                raise APIError5xx(str(e))
            
            elif "timeout" in error_str:
                logger.warning(
                    "timeout_error",
                    modelo=modelo,
                    provider=provider,
                    timeout=timeout,
                )
                raise TimeoutError(f"Timeout após {timeout}s")
            
            else:
                # Erro não recuperável
                logger.error(
                    "llm_call_failed",
                    modelo=modelo,
                    provider=provider,
                    erro=str(e),
                )
                raise
    
    async def chamar_com_fallback(
        self,
        modelo_primario: str,
        modelo_fallback: str,
        prompt: str,
        **kwargs
    ) -> tuple[LLMResponse, bool]:
        """
        Chama LLM com fallback automático.
        
        Args:
            modelo_primario: Modelo principal
            modelo_fallback: Modelo de fallback
            prompt: Prompt
            **kwargs: Argumentos adicionais para chamar()
            
        Returns:
            Tupla (resposta, usou_fallback)
        """
        # Tentar primário
        try:
            resposta = await self.chamar(modelo_primario, prompt, **kwargs)
            return resposta, False
        
        except Exception as e:
            logger.warning(
                "fallback_triggered",
                modelo_primario=modelo_primario,
                modelo_fallback=modelo_fallback,
                motivo=str(e),
            )
            
            # Tentar fallback
            try:
                resposta = await self.chamar(modelo_fallback, prompt, **kwargs)
                logger.info(
                    "fallback_success",
                    modelo_usado=modelo_fallback,
                )
                return resposta, True
            
            except Exception as e2:
                logger.error(
                    "fallback_failed",
                    modelo_primario=modelo_primario,
                    modelo_fallback=modelo_fallback,
                    erro_primario=str(e),
                    erro_fallback=str(e2),
                )
                raise Exception(
                    f"Ambos modelos falharam: {modelo_primario} e {modelo_fallback}"
                )