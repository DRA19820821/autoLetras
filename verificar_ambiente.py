#!/usr/bin/env python3
"""
Script de verificação completa do ambiente.
Execute: python verificar_ambiente.py
"""
import sys
import os
from pathlib import Path

def check(descricao, condicao, dica=""):
    """Verifica uma condição e imprime resultado."""
    status = "✓" if condicao else "✗"
    cor = "\033[92m" if condicao else "\033[91m"
    reset = "\033[0m"
    
    print(f"{cor}{status}{reset} {descricao}")
    if not condicao and dica:
        print(f"  → {dica}")
    
    return condicao

def main():
    print("🔍 Verificando ambiente do Compositor de Músicas Educativas")
    print("=" * 60)
    print()
    
    todos_ok = True
    
    # 1. Python
    print("1. Python")
    python_version = sys.version_info
    python_ok = python_version.major == 3 and python_version.minor >= 11
    todos_ok &= check(
        f"Python {python_version.major}.{python_version.minor}.{python_version.micro}",
        python_ok,
        "Necessário Python 3.11 ou superior"
    )
    print()
    
    # 2. Virtual Environment
    print("2. Virtual Environment")
    in_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )
    todos_ok &= check(
        "Executando em venv",
        in_venv,
        "Execute: source .venv/bin/activate (Linux/Mac) ou .venv\\Scripts\\activate (Windows)"
    )
    
    venv_exists = Path("venv").exists() or Path(".venv").exists()
    todos_ok &= check(
        "Diretório venv existe",
        venv_exists,
        "Execute: python -m venv .venv"
    )
    print()
    
    # 3. Dependências
    print("3. Dependências Python")
    deps_ok = True
    
    try:
        import fastapi
        check("FastAPI instalado", True)
    except ImportError:
        deps_ok = False
        todos_ok &= check("FastAPI instalado", False, "Execute: pip install -r requirements.txt")
    
    try:
        import langchain
        check("LangChain instalado", True)
    except ImportError:
        deps_ok = False
        todos_ok &= check("LangChain instalado", False, "Execute: pip install -r requirements.txt")
    
    try:
        import langgraph
        check("LangGraph instalado", True)
    except ImportError:
        deps_ok = False
        todos_ok &= check("LangGraph instalado", False, "Execute: pip install -r requirements.txt")
    
    try:
        import litellm
        check("LiteLLM instalado", True)
    except ImportError:
        deps_ok = False
        todos_ok &= check("LiteLLM instalado", False, "Execute: pip install -r requirements.txt")
    
    try:
        import structlog
        check("Structlog instalado", True)
    except ImportError:
        deps_ok = False
        todos_ok &= check("Structlog instalado", False, "Execute: pip install -r requirements.txt")
    
    print()
    
    # 4. Estrutura de Diretórios
    print("4. Estrutura de Diretórios")
    
    dirs = {
        "backend": "Código principal",
        "backend/app": "Módulos da aplicação",
        "frontend": "Interface web",
        "data": "Dados",
        "data/inputs": "Arquivos de entrada",
        "data/outputs": "Arquivos de saída",
        "data/logs": "Logs",
        "data/checkpoints": "Checkpoints",
    }
    
    for dir_path, desc in dirs.items():
        exists = Path(dir_path).exists()
        todos_ok &= check(
            f"{dir_path}/ - {desc}",
            exists,
            f"Execute: mkdir -p {dir_path}"
        )
    print()
    
    # 5. Arquivos __init__.py
    print("5. Arquivos __init__.py")
    
    init_files = [
        "backend/__init__.py",
        "backend/app/__init__.py",
        "backend/app/api/__init__.py",
        "backend/app/agents/__init__.py",
        "backend/app/core/__init__.py",
        "backend/app/retry/__init__.py",
        "backend/app/utils/__init__.py",
    ]
    
    for init_file in init_files:
        exists = Path(init_file).exists()
        todos_ok &= check(
            init_file,
            exists,
            "Execute: python criar_init_files.py"
        )
    print()
    
    # 6. Arquivos de Configuração
    print("6. Arquivos de Configuração")
    
    configs = {
        ".env": "Variáveis de ambiente (API keys)",
        "config.yaml": "Configurações do sistema",
        "requirements.txt": "Dependências Python",
    }
    
    for config_file, desc in configs.items():
        exists = Path(config_file).exists()
        dica = ""
        if config_file == ".env" and not exists:
            dica = "Execute: cp .env.example .env"
        
        todos_ok &= check(f"{config_file} - {desc}", exists, dica)
    print()
    
    # 7. API Keys
    print("7. API Keys (pelo menos uma necessária)")
    
    if Path(".env").exists():
        from dotenv import load_dotenv
        load_dotenv()
        
        keys = {
            "ANTHROPIC_API_KEY": "Anthropic (Claude)",
            "OPENAI_API_KEY": "OpenAI (GPT-4)",
            "GOOGLE_API_KEY": "Google (Gemini)",
            "DEEPSEEK_API_KEY": "DeepSeek",
        }
        
        alguma_key = False
        for key, desc in keys.items():
            value = os.getenv(key)
            configurada = bool(value and value != "" and not value.startswith("your-key"))
            
            if configurada:
                alguma_key = True
                # Mostrar apenas primeiros/últimos caracteres
                masked = value[:7] + "..." + value[-4:] if len(value) > 15 else "***"
                check(f"{desc} ({masked})", True)
            else:
                check(f"{desc}", False, "Opcional - adicione no .env se quiser usar")
        
        if not alguma_key:
            print()
            print("  ⚠️  NENHUMA API key configurada!")
            print("  → Edite .env e adicione pelo menos uma API key")
            todos_ok = False
    else:
        print("  ⚠️  Arquivo .env não encontrado")
        todos_ok = False
    
    print()
    
    # 8. Arquivos Principais
    print("8. Arquivos Principais do Backend")
    
    main_files = {
        "backend/main.py": "Aplicação FastAPI",
        "backend/app/agents/graph.py": "Workflow LangGraph",
        "backend/app/agents/nodes.py": "Nós do grafo",
        "backend/app/core/llm_client.py": "Cliente LLM",
        "backend/app/core/parser.py": "Parser HTML",
    }
    
    for file_path, desc in main_files.items():
        exists = Path(file_path).exists()
        todos_ok &= check(f"{file_path} - {desc}", exists)
    print()
    
    # Resumo
    print("=" * 60)
    if todos_ok:
        print("✓ ✓ ✓  TUDO OK! Sistema pronto para uso.")
        print()
        print("Execute: python run.py")
    else:
        print("✗ ✗ ✗  Problemas encontrados!")
        print()
        print("Siga as dicas acima para corrigir.")
        print("Depois execute novamente: python verificar_ambiente.py")
    print("=" * 60)
    
    return 0 if todos_ok else 1

if __name__ == "__main__":
    sys.exit(main())