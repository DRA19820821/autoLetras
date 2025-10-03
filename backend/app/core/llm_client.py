"""Camada de abstração de modelos de linguagem para a aplicação AutoLetras.

Este módulo oferece funções utilitárias para instanciar modelos de linguagem
compartilhados de forma agnóstica ao provedor, bem como detectar o provedor
correto a partir do nome do modelo. Ele também injeta um atributo `provider`
nas instâncias retornadas, contornando restrições impostas por algumas
bibliotecas que não expõem essa informação por padrão. Esse atributo é
utilizado por outras partes da aplicação (por exemplo, o `throttler`) para
gerenciar limites de chamadas por provedor.

Se novos modelos ou provedores forem adicionados, atualize a função
`_detect_provider_from_model` e a lógica de criação em `get_chat_model`.
"""

from __future__ import annotations

import os
from typing import Optional

# Importações condicionais para evitar erros caso algumas bibliotecas não
# estejam instaladas no ambiente. Cada import é envolvido em um bloco try
# individual para permitir o uso parcial caso apenas alguns provedores
# estejam disponíveis.
try:
    from langchain_openai import ChatOpenAI  # type: ignore
except Exception:
    ChatOpenAI = None  # type: ignore

try:
    from langchain_anthropic import ChatAnthropic  # type: ignore
except Exception:
    ChatAnthropic = None  # type: ignore

try:
    from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore
except Exception:
    ChatGoogleGenerativeAI = None  # type: ignore

try:
    # O pacote `langchain_deepseek` fornece integração com DeepSeek.
    # Ver https://python.langchain.com/api_reference/deepseek/chat_models/langchain_deepseek.chat_models.ChatDeepSeek.html
    from langchain_deepseek import ChatDeepSeek  # type: ignore
except Exception:
    ChatDeepSeek = None  # type: ignore

# Deepseek e outros provedores podem ser suportados conforme necessário.


def _detect_provider_from_model(model_name: str) -> str:
    """Detecta o provedor com base no nome do modelo.

    A heurística é simples:

    - Nomes iniciados por "claude" → Anthropic.
    - Nomes iniciados por "gemini" → Google Generative AI.
    - Nomes iniciados por "gpt" → OpenAI.
    - Se contiver "deepseek" → DeepSeek.
    - Caso contrário, usa a variável de ambiente ``LLM_PROVIDER`` como
      valor padrão; se não definida, assume OpenAI.

    Args:
        model_name: Nome do modelo a ser inferido.

    Returns:
        Nome do provedor reconhecido.
    """
    prefix = model_name.lower()
    if prefix.startswith("claude"):
        return "anthropic"
    if prefix.startswith("gemini"):
        return "google"
    if prefix.startswith("gpt"):
        return "openai"
    if "deepseek" in prefix:
        return "deepseek"
    return os.getenv("LLM_PROVIDER", "openai").lower()


def get_chat_model(model_name: str, temperature: float = 0.7, **kwargs) -> object:
    """Instancia um modelo de chat conforme o provedor detectado.

    Além de retornar a instância, injeta dinamicamente um atributo
    ``provider`` na instância para compatibilidade com código que
    referencia essa informação. Caso um provedor não esteja instalado,
    lança uma ``ValueError`` explicitando o erro.

    Args:
        model_name: Identificador do modelo. Por exemplo ``"gpt-4"`` ou
            ``"claude-2"``. Usado para inferir o provedor e para ser
            passado ao construtor do modelo.
        temperature: Temperatura a ser passada ao modelo, quando aplicável.
        **kwargs: Parâmetros adicionais específicos do provedor.

    Returns:
        Instância da classe de modelo apropriada, com o atributo ``provider``
        definido.
    """
    provider = _detect_provider_from_model(model_name)

    # Instanciar o modelo conforme o provedor.
    # Adicionamos parâmetros de limite de tokens quando não fornecidos,
    # pois alguns modelos têm valores padrão muito baixos que podem
    # truncar saídas estruturadas. Ajustar esse limite ajuda a evitar
    # erros como "max_tokens" stop reason, que causam validações
    # incompletas em Pydantic.
    if provider == "openai":
        if ChatOpenAI is None:
            raise ValueError(
                "Biblioteca langchain_openai não está instalada."
            )
        # OpenAI usa `max_tokens` para limitar a resposta. Se não
        # especificado pelo usuário, definimos um valor alto para
        # permitir que respostas estruturadas sejam completas.
        if "max_tokens" not in kwargs:
            # Para modelos OpenAI é seguro usar um valor elevado (p.ex. 4096)
            # para permitir respostas longas sem cortar prematuramente. Esse
            # valor ainda está abaixo do limite de muitas variantes modernas.
            kwargs["max_tokens"] = 12000
        llm = ChatOpenAI(model=model_name, temperature=temperature, **kwargs)
    elif provider == "anthropic":
        if ChatAnthropic is None:
            raise ValueError(
                "Biblioteca langchain_anthropic não está instalada."
            )
        # Anthropic usa `max_tokens_to_sample` (alias `max_tokens`).
        if "max_tokens" not in kwargs:
            # Claude Sonnet 4.5 e Opus 4.1 suportam saídas muito longas (até
            # dezenas de milhares de tokens). Definimos 8192 como valor
            # padrão para minimizar riscos de truncamento.
            kwargs["max_tokens"] = 12000
        llm = ChatAnthropic(model=model_name, temperature=temperature, **kwargs)
    elif provider == "google":
        if ChatGoogleGenerativeAI is None:
            raise ValueError(
                "Biblioteca langchain_google_genai não está instalada."
            )
        # Google usa `max_output_tokens` para limitar a saída.
        if "max_output_tokens" not in kwargs:
            # Google Gemini permite saídas longas; definimos um limite alto
            # para evitar truncamentos prematuros.
            kwargs["max_output_tokens"] = 12000
        # Para Google Generative AI, o parâmetro de temperatura possui nome
        # diferente. Fornecemos via kwargs caso esteja disponível.
        llm = ChatGoogleGenerativeAI(model=model_name, temperature=temperature, **kwargs)
    elif provider == "deepseek":
        # Suporte para DeepSeek. Necessita do pacote `langchain_deepseek` instalado
        # e da variável de ambiente DEEPSEEK_API_KEY. A classe ChatDeepSeek aceita
        # `max_tokens` como parâmetro de tamanho de resposta.
        if ChatDeepSeek is None:
            raise ValueError(
                "Biblioteca langchain_deepseek não está instalada."
            )
        if "max_tokens" not in kwargs:
            # DeepSeek também suporta respostas longas; usamos 4096 tokens
            # como valor padrão para permitir saídas completas.
            kwargs["max_tokens"] = 8000
        llm = ChatDeepSeek(model=model_name, temperature=temperature, **kwargs)
    else:
        raise ValueError(f"Provedor de LLM '{provider}' não suportado.")

    # Injeta dinamicamente o atributo provider. Usamos setattr para
    # contornar casos em que as classes não permitem novas atribuições.
    try:
        setattr(llm, "provider", provider)
    except Exception:
        # Caso o objeto seja imutável (p.ex. Pydantic), encapsulamos em
        # um objeto simples que expõe a interface e o atributo extra.
        class ModelWrapper:
            def __init__(self, base, prov):
                self._base = base
                self.provider = prov

            def __getattr__(self, name):
                return getattr(self._base, name)

        llm = ModelWrapper(llm, provider)

    return llm


__all__ = ["get_chat_model", "_detect_provider_from_model"]