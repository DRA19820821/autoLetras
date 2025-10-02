"""
Script para testar rapidamente os provedores de LLM.
Execute: python testar_provedores.py
"""
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

# Modelos Claude disponíveis na API (Outubro 2025)
CLAUDE_MODELS_TO_TEST = [
    "claude-sonnet-4-5-20250929",
    "claude-opus-4-1-20250805", 
    "claude-3-7-sonnet-20250219",
    "claude-3-5-sonnet-20241022",
]

async def test_anthropic():
    """Testa quais modelos Claude estão disponíveis."""
    try:
        from anthropic import AsyncAnthropic
        
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("❌ ANTHROPIC_API_KEY não configurada")
            return
        
        client = AsyncAnthropic(api_key=api_key)
        
        print("\n🧪 Testando modelos Claude...")
        print("-" * 60)
        
        for model in CLAUDE_MODELS_TO_TEST:
            try:
                response = await client.messages.create(
                    model=model,
                    max_tokens=5,
                    messages=[{"role": "user", "content": "Hi"}]
                )
                print(f"✅ {model}")
                
            except Exception as e:
                error_msg = str(e)
                if "404" in error_msg or "not_found" in error_msg:
                    print(f"❌ {model} - NÃO EXISTE")
                elif "401" in error_msg:
                    print(f"⚠️  {model} - API key inválida")
                else:
                    print(f"⚠️  {model} - Erro: {error_msg[:50]}")
        
    except ImportError:
        print("❌ SDK Anthropic não instalado. Execute: pip install anthropic")
    except Exception as e:
        print(f"❌ Erro ao testar Anthropic: {e}")

async def test_openai():
    """Testa OpenAI."""
    try:
        from openai import AsyncOpenAI
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ OPENAI_API_KEY não configurada")
            return
        
        client = AsyncOpenAI(api_key=api_key)
        
        print("\n🧪 Testando OpenAI...")
        print("-" * 60)
        
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=5,
        )
        print(f"✅ OpenAI funcionando - Modelo: gpt-4o")
        
    except ImportError:
        print("❌ SDK OpenAI não instalado. Execute: pip install openai")
    except Exception as e:
        print(f"❌ Erro ao testar OpenAI: {e}")

async def test_google():
    """Testa Google."""
    try:
        import google.generativeai as genai
        
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("❌ GOOGLE_API_KEY não configurada")
            return
        
        genai.configure(api_key=api_key)
        
        print("\n🧪 Testando Google Gemini...")
        print("-" * 60)
        
        model = genai.GenerativeModel("gemini-pro")
        response = await asyncio.to_thread(
            model.generate_content,
            "Hi"
        )
        print(f"✅ Google funcionando - Modelo: gemini-pro")
        
    except ImportError:
        print("❌ SDK Google não instalado. Execute: pip install google-generativeai")
    except Exception as e:
        error_str = str(e).lower()
        if "quota" in error_str or "429" in error_str:
            print(f"⚠️  Google: Rate limit atingido (normal durante teste)")
        else:
            print(f"❌ Erro ao testar Google: {e}")

async def test_deepseek():
    """Testa DeepSeek."""
    try:
        import httpx
        
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            print("❌ DEEPSEEK_API_KEY não configurada")
            return
        
        print("\n🧪 Testando DeepSeek...")
        print("-" * 60)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 5,
                },
                timeout=10,
            )
            
            if response.status_code == 200:
                print(f"✅ DeepSeek funcionando - Modelo: deepseek-chat")
            else:
                print(f"❌ DeepSeek erro: {response.status_code}")
        
    except ImportError:
        print("❌ httpx não instalado. Execute: pip install httpx")
    except Exception as e:
        print(f"❌ Erro ao testar DeepSeek: {e}")

async def main():
    """Executa todos os testes."""
    print("=" * 60)
    print("🔍 TESTE DE PROVEDORES DE LLM")
    print("=" * 60)
    
    await test_openai()
    await test_anthropic()
    await test_google()
    await test_deepseek()
    
    print("\n" + "=" * 60)
    print("✨ Teste concluído!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())