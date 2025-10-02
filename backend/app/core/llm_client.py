"""Cliente unificado para LLMs usando LangChain ChatModels."""
import os
from functools import lru_cache
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.chat_models.deepseek import ChatDeepseek
from langchain_core.language_models.chat_models import BaseChatModel
from typing import Tuple

# Mapeamento de nomes amigáveis para nomes de modelos oficiais e provedores
MODEL_MAP = {
    # OpenAI
    "gpt-5": ("gpt-5", "openai"),
    "gpt-4.1": ("gpt-4.1", "openai"),
    "gpt-4o": ("gpt-4o", "openai"), 
    "gpt-4-turbo": ("gpt-4-turbo", "openai"),
    # Anthropic
    "claude-sonnet-4-5": ("claude-3-5-sonnet-20240620", "anthropic"),
    "claude-opus-4-1": ("claude-3-opus-20240229", "anthropic"),
    "claude-3-5-sonnet": ("claude-3-5-sonnet-20240620", "anthropic"),
    # Google
    "gemini-2.5-pro": ("gemini-1.5-pro-latest", "google"),
    "gemini-1.5-pro": ("gemini-1.5-pro-latest", "google"),
    "gemini-pro": ("gemini-pro", "google"),
    # DeepSeek
    "deepseek-chat": ("deepseek-chat", "deepseek"),
}

@lru_cache(maxsize=20)
def get_chat_model(model_name: str, temperature: float = 0.7) -> Tuple[BaseChatModel, str]:
    """
    Retorna uma tupla contendo a instância do ChatModel da LangChain e o nome do provedor.
    """
    friendly_name = model_name.lower()
    
    api_name, provider = None, None
    for key, value in MODEL_MAP.items():
        if key in friendly_name:
            api_name, provider = value
            break
            
    if not (api_name and provider):
        # Fallback para nomes de modelo não mapeados que podem existir
        if 'gpt' in friendly_name:
            provider = 'openai'
        elif 'claude' in friendly_name:
            provider = 'anthropic'
        elif 'gemini' in friendly_name:
            provider = 'google'
        elif 'deepseek' in friendly_name:
            provider = 'deepseek'
        else:
            raise ValueError(f"Modelo '{model_name}' não é suportado ou mapeado.")
        api_name = model_name

    if provider == "openai":
        model = ChatOpenAI(model=api_name, temperature=temperature, api_key=os.getenv("OPENAI_API_KEY"))
    elif provider == "anthropic":
        model = ChatAnthropic(model=api_name, temperature=temperature, api_key=os.getenv("ANTHROPIC_API_KEY"))
    elif provider == "google":
        model = ChatGoogleGenerativeAI(model=api_name, temperature=temperature, api_key=os.getenv("GOOGLE_API_KEY"), convert_system_message_to_human=True)
    elif provider == "deepseek":
         model = ChatDeepseek(model=api_name, temperature=temperature, api_key=os.getenv("DEEPSEEK_API_KEY"))
    else:
        raise ValueError(f"Provedor '{provider}' desconhecido.")
        
    return model, provider