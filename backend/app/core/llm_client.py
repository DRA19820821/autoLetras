"""Cliente unificado para LLMs usando LangChain ChatModels."""
import os
from functools import lru_cache
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.chat_models.deepseek import ChatDeepseek

# Mapeamento de nomes amigáveis para nomes de modelos oficiais e provedores
MODEL_MAP = {
    # OpenAI
    "gpt-4o": ("gpt-4o", "openai"), "gpt-4-turbo": ("gpt-4-turbo", "openai"),
    # Anthropic
    "claude-3-5-sonnet": ("claude-3-5-sonnet-20240620", "anthropic"),
    "claude-3-opus": ("claude-3-opus-20240229", "anthropic"),
    "claude-sonnet-4-5": ("claude-3-5-sonnet-20240620", "anthropic"), # Mapeando para o mais próximo disponível
    # Google
    "gemini-1.5-pro": ("gemini-1.5-pro-latest", "google"),
    "gemini-pro": ("gemini-pro", "google"),
    # DeepSeek
    "deepseek-chat": ("deepseek-chat", "deepseek"),
}

@lru_cache(maxsize=10)
def get_chat_model(model_name: str, temperature: float = 0.7):
    """
    Retorna uma instância de ChatModel da LangChain para o modelo especificado.
    Usa um cache para evitar recriar o mesmo objeto.
    """
    friendly_name = model_name.lower()
    
    # Procura um mapeamento que seja um subconjunto do nome amigável
    api_name, provider = None, None
    for key, value in MODEL_MAP.items():
        if key in friendly_name:
            api_name, provider = value
            break
            
    if not (api_name and provider):
        raise ValueError(f"Modelo '{model_name}' não é suportado ou mapeado.")

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
        
    # Adicionar o provedor ao objeto para uso no throttler
    model.provider = provider
    return model