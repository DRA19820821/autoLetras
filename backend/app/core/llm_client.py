# backend/app/core/llm_client.py
"""
Fábrica de modelos de chat (LLM) para o projeto.

- Suporte a provedores OpenAI-compatible:
  * DeepSeek (recomendado neste projeto)  -> LLM_PROVIDER=deepseek
  * OpenAI                                -> LLM_PROVIDER=openai
  * Genérico OpenAI-compatible            -> LLM_PROVIDER=generic

Como usar no docker-compose (.env):
  LLM_PROVIDER=deepseek
  DEEPSEEK_API_KEY=sk-xxxx
  # opcional:
  DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
  DEEPSEEK_MODEL=deepseek-chat  # ou deepseek-reasoner

Parâmetros globais opcionais:
  LLM_TEMPERATURE=0.2
  LLM_TIMEOUT=120
  LLM_MAX_RETRIES=3

Para OPENAI:
  LLM_PROVIDER=openai
  OPENAI_API_KEY=sk-xxxx
  # opcional: OPENAI_BASE_URL (se for um proxy)

Para genérico:
  LLM_PROVIDER=generic
  GENERIC_OPENAI_API_KEY=sk-xxxx
  GENERIC_OPENAI_BASE_URL=https://host:port/v1
  GENERIC_OPENAI_MODEL=algum-modelo
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional, Dict, Any

from langchain_openai import ChatOpenAI  # pip install langchain-openai


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


def _build_chat_openai(
    *,
    model: str,
    api_key: str,
    base_url: Optional[str],
    temperature: float,
    timeout: int,
    max_retries: int,
    extra_kwargs: Optional[Dict[str, Any]] = None,
) -> ChatOpenAI:
    """
    Constrói um ChatOpenAI com parâmetros padronizados.
    """
    kwargs: Dict[str, Any] = {
        "model": model,
        "api_key": api_key,
        "temperature": temperature,
        "timeout": timeout,
        "max_retries": max_retries,
    }
    # base_url só é passado se definido (OpenAI oficial não precisa)
    if base_url:
        kwargs["base_url"] = base_url

    if extra_kwargs:
        kwargs.update(extra_kwargs)

    return ChatOpenAI(**kwargs)


@lru_cache(maxsize=16)
def get_chat_model(model: Optional[str] = None, temperature: Optional[float] = None) -> ChatOpenAI:
    """
    Retorna uma instância cacheada de ChatOpenAI conforme o provedor escolhido via envs.

    Args:
        model: nome do modelo (opcional). Se None, usa o default do provedor.
        temperature: temperatura (opcional). Se None, usa LLM_TEMPERATURE ou 0.2.

    Returns:
        ChatOpenAI
    """
    provider = os.getenv("LLM_PROVIDER", "deepseek").strip().lower()

    # Parâmetros globais
    temp = temperature if (temperature is not None) else _env_float("LLM_TEMPERATURE", 0.2)
    timeout = _env_int("LLM_TIMEOUT", 120)
    max_retries = _env_int("LLM_MAX_RETRIES", 3)

    if provider == "deepseek":
        # DeepSeek via endpoint OpenAI-compatible
        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("Faltou DEEPSEEK_API_KEY no ambiente (LLM_PROVIDER=deepseek).")

        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").strip() or None
        mdl = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip() or "deepseek-chat"

        return _build_chat_openai(
            model=mdl,
            api_key=api_key,
            base_url=base_url,
            temperature=temp,
            timeout=timeout,
            max_retries=max_retries,
        )

    elif provider == "openai":
        # OpenAI oficial
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("Faltou OPENAI_API_KEY no ambiente (LLM_PROVIDER=openai).")

        base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None  # normalmente não precisa
        # Ex.: "gpt-4o-mini", "gpt-4.1", etc. Ajuste conforme seu uso.
        mdl = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"

        return _build_chat_openai(
            model=mdl,
            api_key=api_key,
            base_url=base_url,
            temperature=temp,
            timeout=timeout,
            max_retries=max_retries,
        )

    elif provider == "generic":
        # Qualquer provedor compatível com OpenAI
        api_key = os.getenv("GENERIC_OPENAI_API_KEY", "").strip()
        base_url = os.getenv("GENERIC_OPENAI_BASE_URL", "").strip()
        if not api_key or not base_url:
            raise RuntimeError(
                "Para LLM_PROVIDER=generic, defina GENERIC_OPENAI_API_KEY e GENERIC_OPENAI_BASE_URL."
            )

        mdl = model or os.getenv("GENERIC_OPENAI_MODEL", "unknown-model").strip() or "unknown-model"

        return _build_chat_openai(
            model=mdl,
            api_key=api_key,
            base_url=base_url,
            temperature=temp,
            timeout=timeout,
            max_retries=max_retries,
        )

    else:
        raise RuntimeError(
            f"LLM_PROVIDER inválido: {provider!r}. Use 'deepseek', 'openai' ou 'generic'."
        )


# ---------- Utilitários opcionais ----------

def get_provider_model_name() -> str:
    """
    Retorna uma string 'provider:model' útil para logs/diagnóstico.
    """
    provider = os.getenv("LLM_PROVIDER", "deepseek").strip().lower()
    if provider == "deepseek":
        mdl = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip() or "deepseek-chat"
    elif provider == "openai":
        mdl = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    elif provider == "generic":
        mdl = os.getenv("GENERIC_OPENAI_MODEL", "unknown-model").strip() or "unknown-model"
    else:
        mdl = "unknown"
    return f"{provider}:{mdl}"


if __name__ == "__main__":
    # Teste rápido (não faz chamada externa).
    # Apenas constrói a instância e imprime um resumo.
    llm = get_chat_model()
    print("LLM pronto:", get_provider_model_name(), "->", type(llm).__name__)
