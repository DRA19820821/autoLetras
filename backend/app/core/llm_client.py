"""Cliente unificado para LLMs usando SDKs oficiais (SEM LiteLLM)."""
import os
import asyncio
import time
from typing import Optional
from pydantic import BaseModel

# SDKs oficiais
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
import google.generativeai as genai
import httpx

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.utils.logger import get_logger

logger = get_logger()


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


# Modelos suportados por provedor
MODELOS_OPENAI = {
    "gpt-5": "gpt-5",
    "gpt-4.1": "gpt-4.1",
    "gpt-4.1-mini": "gpt-4.1-mini",
    "gpt-4.1-nano": "gpt-4.1-nano",
    "gpt-4-turbo": "gpt-4-turbo-2024-04-09",
    "gpt-4o": "gpt-4o",
    "o4-mini": "o4-mini",
}

MODELOS_ANTHROPIC = {
    "claude-sonnet-4-5": "claude-sonnet-4-5-20250929",
    "claude-opus-4-1": "claude-opus-4-1-20250805",
    "claude-opus-4": "claude-opus-4-20250522",
    "claude-sonnet-4": "claude-3-7-sonnet-20250219",  # Claude 3.7 é o mais recente Sonnet antes do 4.5
    "claude-3-7-sonnet": "claude-3-7-sonnet-20250219",
    "claude-3-5-sonnet": "claude-3-5-sonnet-20241022",
}

MODELOS_GOOGLE = {
    "gemini-2.5-pro": "gemini-2.5-pro",
    "gemini-2.5-flash": "gemini-2.5-flash",
    "gemini-2.5-flash-lite": "gemini-2.5-flash-lite",
    "gemini-2.0-flash": "gemini-2.0-flash",
    "gemini-pro": "gemini-pro",
    "gemini-1.5-pro": "gemini-1.5-pro",
}

MODELOS_DEEPSEEK = {
    "deepseek-v3": "deepseek-chat",
    "deepseek-v3.1": "deepseek-chat",
    "deepseek-chat": "deepseek-chat",
    "deepseek-r1": "deepseek-reasoner",
    "deepseek-reasoner": "deepseek-reasoner",
}


# Custos por 1M tokens (USD) - Outubro 2025
CUSTOS_MODELOS = {
    # OpenAI
    "gpt-5": {"input": 2.5, "output": 10.0},
    "gpt-4.1": {"input": 2.5, "output": 10.0},
    "gpt-4.1-mini": {"input": 0.15, "output": 0.60},
    "gpt-4.1-nano": {"input": 0.075, "output": 0.30},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "o4-mini": {"input": 1.0, "output": 4.0},
    
    # Anthropic
    "claude-sonnet-4-5": {"input": 3.0, "output": 15.0},
    "claude-opus-4-1": {"input": 15.0, "output": 75.0},
    "claude-opus-4": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4": {"input": 3.0, "output": 15.0},
    "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
    
    # Google
    "gemini-2.5-pro": {"input": 1.25, "output": 5.0},
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.5-flash-lite": {"input": 0.0375, "output": 0.15},
    "gemini-2.0-flash": {"input": 0.075, "output": 0.30},
    "gemini-pro": {"input": 0.50, "output": 1.50},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.0},
    
    # DeepSeek
    "deepseek-chat": {"input": 0.14, "output": 0.28},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
}


def get_provider(modelo: str) -> str:
    """Determina provedor baseado no modelo."""
    modelo_lower = modelo.lower()
    
    if any(m in modelo_lower for m in ["gpt", "o4-mini"]):
        return "openai"
    elif "claude" in modelo_lower:
        return "anthropic"
    elif "gemini" in modelo_lower:
        return "google"
    elif "deepseek" in modelo_lower:
        return "deepseek"
    
    return "openai"  # default


def calcular_custo(modelo: str, tokens_input: int, tokens_output: int) -> float:
    """Calcula custo de uma chamada."""
    # Buscar custos exatos
    modelo_base = modelo.lower().replace("-", "_")
    
    for key, custos in CUSTOS_MODELOS.items():
        if key.replace("-", "_") in modelo_base:
            custo_in = (tokens_input / 1_000_000) * custos["input"]
            custo_out = (tokens_output / 1_000_000) * custos["output"]
            return custo_in + custo_out
    
    # Fallback: custos médios
    logger.warning("custo_nao_encontrado", modelo=modelo, msg="Usando custos padrão")
    return (tokens_input / 1_000_000) * 2.0 + (tokens_output / 1_000_000) * 8.0


class LLMClient:
    """Cliente unificado usando SDKs oficiais."""
    
    def __init__(self):
        # Inicializar clientes oficiais
        self.openai_client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY")
        ) if os.getenv("OPENAI_API_KEY") else None
        
        self.anthropic_client = AsyncAnthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        ) if os.getenv("ANTHROPIC_API_KEY") else None
        
        # Google precisa de configuração diferente
        if google_key := os.getenv("GOOGLE_API_KEY"):
            genai.configure(api_key=google_key)
        
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
        Chama LLM usando SDK oficial do provedor.
        
        Args:
            modelo: Nome do modelo
            prompt: Prompt a enviar
            temperatura: Temperatura (criatividade)
            max_tokens: Máximo de tokens na resposta
            timeout_override: Override do timeout padrão
            
        Returns:
            LLMResponse com resultado
        """
        start = time.time()
        provider = get_provider(modelo)
        timeout = timeout_override or self.timeout_base
        
        try:
            if provider == "openai":
                response = await self._call_openai(
                    modelo, prompt, temperatura, max_tokens, timeout
                )
            elif provider == "anthropic":
                response = await self._call_anthropic(
                    modelo, prompt, temperatura, max_tokens, timeout
                )
            elif provider == "google":
                response = await self._call_google(
                    modelo, prompt, temperatura, max_tokens, timeout
                )
            elif provider == "deepseek":
                response = await self._call_deepseek(
                    modelo, prompt, temperatura, max_tokens, timeout
                )
            else:
                raise ValueError(f"Provedor desconhecido: {provider}")
            
            latencia_ms = int((time.time() - start) * 1000)
            response.latencia_ms = latencia_ms
            
            logger.info(
                "llm_call_success",
                modelo=modelo,
                provider=provider,
                tokens_in=response.tokens_input,
                tokens_out=response.tokens_output,
                custo=f"${response.custo:.4f}",
                latencia_ms=latencia_ms,
            )
            
            return response
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Classificar erro
            if "rate" in error_str or "429" in error_str:
                logger.warning("rate_limit", modelo=modelo, provider=provider)
                raise RateLimitError(5)
            
            elif any(code in error_str for code in ["500", "502", "503", "504"]):
                logger.warning("api_5xx_error", modelo=modelo, erro=str(e))
                raise APIError5xx(str(e))
            
            elif "timeout" in error_str:
                logger.warning("timeout_error", modelo=modelo, timeout=timeout)
                raise TimeoutError(f"Timeout após {timeout}s")
            
            else:
                logger.error("llm_call_failed", modelo=modelo, erro=str(e))
                raise
    
    async def _call_openai(
        self, modelo: str, prompt: str, temperatura: float, max_tokens: int, timeout: int
    ) -> LLMResponse:
        """Chama OpenAI usando SDK oficial."""
        if not self.openai_client:
            raise ValueError("OpenAI API key não configurada")
        
        # Mapear para nome oficial
        model_name = MODELOS_OPENAI.get(modelo.lower(), modelo)
        
        response = await self.openai_client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperatura,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        
        content = response.choices[0].message.content
        tokens_in = response.usage.prompt_tokens
        tokens_out = response.usage.completion_tokens
        custo = calcular_custo(modelo, tokens_in, tokens_out)
        
        return LLMResponse(
            content=content,
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            custo=custo,
            modelo_usado=modelo,
            latencia_ms=0,
        )
    
    async def _call_anthropic(
        self, modelo: str, prompt: str, temperatura: float, max_tokens: int, timeout: int
    ) -> LLMResponse:
        """Chama Anthropic usando SDK oficial."""
        if not self.anthropic_client:
            raise ValueError("Anthropic API key não configurada")
        
        # Mapear para nome oficial
        model_name = MODELOS_ANTHROPIC.get(modelo.lower(), modelo)
        
        response = await self.anthropic_client.messages.create(
            model=model_name,
            max_tokens=max_tokens,
            temperature=temperatura,
            messages=[{"role": "user", "content": prompt}],
            timeout=timeout,
        )
        
        content = response.content[0].text
        tokens_in = response.usage.input_tokens
        tokens_out = response.usage.output_tokens
        custo = calcular_custo(modelo, tokens_in, tokens_out)
        
        return LLMResponse(
            content=content,
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            custo=custo,
            modelo_usado=modelo,
            latencia_ms=0,
        )
    
    async def _call_google(
        self, modelo: str, prompt: str, temperatura: float, max_tokens: int, timeout: int
    ) -> LLMResponse:
        """Chama Google usando SDK oficial."""
        # Mapear para nome oficial
        model_name = MODELOS_GOOGLE.get(modelo.lower(), modelo)
        
        # Criar modelo
        model = genai.GenerativeModel(model_name)
        
        # Configuração
        generation_config = genai.types.GenerationConfig(
            temperature=temperatura,
            max_output_tokens=max_tokens,
        )
        
        # Chamar de forma síncrona (wrapper para async)
        response = await asyncio.to_thread(
            model.generate_content,
            prompt,
            generation_config=generation_config,
        )
        
        content = response.text
        
        # Google nem sempre retorna contagem de tokens detalhada
        # Estimativa baseada no conteúdo
        tokens_in = len(prompt) // 4
        tokens_out = len(content) // 4
        custo = calcular_custo(modelo, tokens_in, tokens_out)
        
        return LLMResponse(
            content=content,
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            custo=custo,
            modelo_usado=modelo,
            latencia_ms=0,
        )
    
    async def _call_deepseek(
        self, modelo: str, prompt: str, temperatura: float, max_tokens: int, timeout: int
    ) -> LLMResponse:
        """Chama DeepSeek via API direta."""
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DeepSeek API key não configurada")
        
        # Mapear para nome oficial
        model_name = MODELOS_DEEPSEEK.get(modelo.lower(), "deepseek-chat")
        
        # Chamar API OpenAI-compatible
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperatura,
                    "max_tokens": max_tokens,
                },
                timeout=timeout,
            )
            
            if response.status_code != 200:
                raise Exception(f"DeepSeek API error: {response.status_code} - {response.text}")
            
            data = response.json()
            
            content = data["choices"][0]["message"]["content"]
            tokens_in = data["usage"]["prompt_tokens"]
            tokens_out = data["usage"]["completion_tokens"]
            custo = calcular_custo(modelo, tokens_in, tokens_out)
            
            return LLMResponse(
                content=content,
                tokens_input=tokens_in,
                tokens_output=tokens_out,
                custo=custo,
                modelo_usado=modelo,
                latencia_ms=0,
            )
    
    async def chamar_com_fallback(
        self,
        modelo_primario: str,
        modelo_fallback: str,
        prompt: str,
        **kwargs
    ) -> tuple[LLMResponse, bool]:
        """
        Chama LLM com fallback automático.
        
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
                logger.info("fallback_success", modelo_usado=modelo_fallback)
                return resposta, True
            
            except Exception as e2:
                logger.error(
                    "fallback_failed",
                    modelo_primario=modelo_primario,
                    modelo_fallback=modelo_fallback,
                )
                raise Exception(
                    f"Ambos modelos falharam: {modelo_primario} e {modelo_fallback}"
                )