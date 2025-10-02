"""
Fábrica de modelos de chat com suporte a múltiplos provedores.
VERSÃO CORRIGIDA: Garante que o atributo 'provider' está sempre presente.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional, Union

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models.chat_models import BaseChatModel

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
    """
    model_lower = model_name.lower()
    
    if model_lower.startswith("claude"):
        return "anthropic"
    if model_lower.startswith("gemini"):
        return "google"
    if model_lower.startswith("gpt"):
        return "openai"
    if "deepseek" in model_lower:
        return "deepseek"
    
    return os.getenv("LLM_PROVIDER", "openai").strip().lower()


@lru_cache(maxsize=16)
def get_chat_model(
    model: Optional[str] = None,
    temperature: Optional[float] = None
) -> BaseChatModel:
    """
    Retorna uma instância de chat model do provedor apropriado,
    garantindo que o atributo .provider esteja sempre definido.
    """
    temp = temperature if (temperature is not None) else _env_float("LLM_TEMPERATURE", 0.2)
    timeout = _env_int("LLM_TIMEOUT", 120)
    max_retries = _env_int("LLM_MAX_RETRIES", 3)
    
    if not model:
        default_provider = os.getenv("LLM_PROVIDER", "deepseek").strip().lower()
        model_map = {
            "anthropic": "claude-sonnet-4-5",
            "openai": "gpt-4o",
            "google": "gemini-2.5-pro",
            "deepseek": "deepseek-chat",
        }
        model = model_map.get(default_provider, os.getenv("GENERIC_OPENAI_MODEL", "gpt-4o").strip())

    provider = _detect_provider_from_model(model)
    llm: BaseChatModel

    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(f"Modelo '{model}' requer ANTHROPIC_API_KEY no .env")
        
        llm = ChatAnthropic(
            model=model,
            anthropic_api_key=api_key,
            temperature=temp,
            timeout=timeout,
            max_retries=max_retries,
        )
    
    elif provider == "google":
        api_key = os.getenv("GOOGLE_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(f"Modelo '{model}' requer GOOGLE_API_KEY no .env")
        
        llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=temp,
            timeout=timeout,
            max_retries=max_retries,
        )

    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(f"Modelo '{model}' requer OPENAI_API_KEY no .env")
        
        base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None
        
        llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temp,
            timeout=timeout,
            max_retries=max_retries,
        )

    elif provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(f"Modelo '{model}' requer DEEPSEEK_API_KEY no .env")
        
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").strip()
        
        llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temp,
            timeout=timeout,
            max_retries=max_retries,
        )
    
    else: # GENERIC
        api_key = os.getenv("GENERIC_OPENAI_API_KEY", "").strip()
        base_url = os.getenv("GENERIC_OPENAI_BASE_URL", "").strip()
        if not api_key or not base_url:
            raise RuntimeError(f"Modelo '{model}' requer GENERIC_OPENAI_API_KEY e GENERIC_OPENAI_BASE_URL no .env")
        
        llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temp,
            timeout=timeout,
            max_retries=max_retries,
        )

    # CORREÇÃO CENTRAL: Adiciona o atributo 'provider' ao objeto LLM ANTES de retorná-lo.
    llm.provider = provider
    
    return llm

def get_provider_model_name() -> str:
    """
    Retorna string 'provider:model' para logs.
    """
    provider = os.getenv("LLM_PROVIDER", "deepseek").strip().lower()
    
    model_map = {
        "deepseek": os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip() or "deepseek-chat",
        "openai": os.getenv("OPENAI_MODEL", "gpt-4o").strip() or "gpt-4o",
        "anthropic": "claude-sonnet-4-5",
        "google": "gemini-2.5-pro",
        "generic": os.getenv("GENERIC_OPENAI_MODEL", "unknown-model").strip() or "unknown-model",
    }
    mdl = model_map.get(provider, "unknown")
    
    return f"{provider}:{mdl}"


if __name__ == "__main__":
    # Teste rápido com a sua lista original de modelos
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