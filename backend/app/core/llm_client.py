"""
Fábrica de modelos de chat com suporte a múltiplos provedores.
VERSÃO CORRIGIDA: Detecta o provedor correto baseado no nome do modelo.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional, Dict, Any, Union

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI


def _env_float(name: str, default: float) -> float:
    val = os.getenv(name, "")
    if not val:
        return default
    try:
        return float(val)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    val = os.getenv(name, "")
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _detect_provider_from_model(model_name: str) -> str:
    """
    Detecta o provedor baseado no nome do modelo.
    
    Args:
        model_name: Nome do modelo (ex: "claude-sonnet-4-5", "gpt-5", "gemini-2.5-pro", "deepseek-reasoner")
        
    Returns:
        Nome do provedor: "anthropic", "openai", "google", "deepseek", ou "generic"
    """
    model_lower = model_name.lower()
    
    # Claude models
    if model_lower.startswith("claude"):
        return "anthropic"
    
    # Gemini models
    if model_lower.startswith("gemini"):
        return "google"
    
    # GPT models
    if model_lower.startswith("gpt"):
        return "openai"
    
    # DeepSeek models (inclui deepseek-chat e deepseek-reasoner)
    if "deepseek" in model_lower:
        return "deepseek"
    
    # Padrão: usar o LLM_PROVIDER do .env
    return os.getenv("LLM_PROVIDER", "openai").strip().lower()


@lru_cache(maxsize=16)
def get_chat_model(
    model: Optional[str] = None,
    temperature: Optional[float] = None
) -> Union[ChatOpenAI, ChatAnthropic, ChatGoogleGenerativeAI]:
    """
    Retorna uma instância de chat model do provedor apropriado.
    DETECTA AUTOMATICAMENTE o provedor baseado no nome do modelo.
    
    Args:
        model: Nome do modelo (ex: "claude-sonnet-4-5", "gpt-4o", "gemini-2.5-pro")
        temperature: Temperatura (opcional)
        
    Returns:
        Instância do chat model apropriado
        
    Examples:
        >>> llm = get_chat_model("claude-sonnet-4-5")  # Retorna ChatAnthropic
        >>> llm = get_chat_model("gpt-4o")              # Retorna ChatOpenAI
        >>> llm = get_chat_model("gemini-2.5-pro")      # Retorna ChatGoogleGenerativeAI
    """
    # Parâmetros globais
    temp = temperature if (temperature is not None) else _env_float("LLM_TEMPERATURE", 0.2)
    timeout = _env_int("LLM_TIMEOUT", 120)
    max_retries = _env_int("LLM_MAX_RETRIES", 3)
    
    # Se não foi passado modelo, usar o padrão do .env
    if not model:
        default_provider = os.getenv("LLM_PROVIDER", "deepseek").strip().lower()
        
        if default_provider == "anthropic":
            model = "claude-sonnet-4-5"
        elif default_provider == "openai":
            model = "gpt-4o"
        elif default_provider == "google":
            model = "gemini-2.5-pro"
        elif default_provider == "deepseek":
            model = "deepseek-chat"
        else:
            model = os.getenv("GENERIC_OPENAI_MODEL", "gpt-4o").strip()
    
    # Detectar provedor baseado no nome do modelo
    provider = _detect_provider_from_model(model)
    
    # ANTHROPIC (Claude)
    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                f"Modelo '{model}' requer ANTHROPIC_API_KEY, mas não foi encontrada no .env"
            )
        
        llm = ChatAnthropic(
            model=model,
            anthropic_api_key=api_key,
            temperature=temp,
            timeout=timeout,
            max_retries=max_retries,
        )
        
        # Adicionar atributo para throttler
        llm.provider = "anthropic"
        
        return llm
    
    # GOOGLE (Gemini)
    elif provider == "google":
        api_key = os.getenv("GOOGLE_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                f"Modelo '{model}' requer GOOGLE_API_KEY, mas não foi encontrada no .env"
            )
        
        llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=temp,
            timeout=timeout,
            max_retries=max_retries,
        )
        
        # Adicionar atributo para throttler
        llm.provider = "google"
        
        return llm
    
    # OPENAI (GPT)
    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                f"Modelo '{model}' requer OPENAI_API_KEY, mas não foi encontrada no .env"
            )
        
        base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None
        
        llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            temperature=temp,
            timeout=timeout,
            max_retries=max_retries,
        )
        
        # Adicionar atributo para identificar o provedor
        llm.provider = "openai"
        
        if base_url:
            llm.base_url = base_url
        
        return llm
    
    # DEEPSEEK (API compatível com OpenAI)
    elif provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                f"Modelo '{model}' requer DEEPSEEK_API_KEY, mas não foi encontrada no .env"
            )
        
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").strip()
        
        llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temp,
            timeout=timeout,
            max_retries=max_retries,
        )
        
        # Adicionar atributo para identificar o provedor
        llm.provider = "deepseek"
        
        return llm
    
    # GENERIC (qualquer API compatível com OpenAI)
    else:
        api_key = os.getenv("GENERIC_OPENAI_API_KEY", "").strip()
        base_url = os.getenv("GENERIC_OPENAI_BASE_URL", "").strip()
        
        if not api_key or not base_url:
            raise RuntimeError(
                f"Modelo '{model}' requer GENERIC_OPENAI_API_KEY e GENERIC_OPENAI_BASE_URL no .env"
            )
        
        llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temp,
            timeout=timeout,
            max_retries=max_retries,
        )
        
        # Adicionar atributo para identificar o provedor
        llm.provider = "generic"
        
        return llm


def get_provider_model_name() -> str:
    """
    Retorna string 'provider:model' para logs.
    """
    provider = os.getenv("LLM_PROVIDER", "deepseek").strip().lower()
    
    if provider == "deepseek":
        mdl = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip() or "deepseek-chat"
    elif provider == "openai":
        mdl = os.getenv("OPENAI_MODEL", "gpt-4o").strip() or "gpt-4o"
    elif provider == "anthropic":
        mdl = "claude-sonnet-4-5"
    elif provider == "google":
        mdl = "gemini-2.5-pro"
    elif provider == "generic":
        mdl = os.getenv("GENERIC_OPENAI_MODEL", "unknown-model").strip() or "unknown-model"
    else:
        mdl = "unknown"
    
    return f"{provider}:{mdl}"


if __name__ == "__main__":
    # Teste rápido
    print("Testando detecção de provedores:")
    print()
    
    test_models = [
        "claude-sonnet-4-5",
        "claude-opus-4-1",
        "gpt-5",
        "gpt-4o",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "deepseek-chat",
        "deepseek-reasoner",
    ]
    
    for model in test_models:
        provider = _detect_provider_from_model(model)
        print(f"  {model:30s} -> {provider}")
    
    print()
    print("Provedor padrão:", get_provider_model_name())