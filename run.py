#!/usr/bin/env python3
"""
Script simplificado para executar o servidor do Compositor de Músicas Educativas.
"""
import os
import sys
from pathlib import Path
import subprocess

def verificar_ambiente():
    """Verifica se o ambiente está configurado corretamente."""
    erros = []
    
    # Verificar venv
    if not Path("venv").exists():
        erros.append("❌ Virtual environment não encontrado. Execute setup.sh ou setup.bat primeiro.")
    
    # Verificar .env
    if not Path(".env").exists():
        erros.append("❌ Arquivo .env não encontrado. Copie .env.example para .env e configure as API keys.")
    
    # Verificar config.yaml
    if not Path("config.yaml").exists():
        erros.append("❌ Arquivo config.yaml não encontrado.")
    
    # Verificar diretórios
    dirs_necessarios = ["data", "backend", "frontend"]
    for dir_name in dirs_necessarios:
        if not Path(dir_name).exists():
            erros.append(f"❌ Diretório '{dir_name}' não encontrado.")
    
    return erros

def main():
    """Função principal."""
    print("🎵 Compositor de Músicas Educativas")
    print("=" * 50)
    print()
    
    # Verificar ambiente
    print("Verificando ambiente...")
    erros = verificar_ambiente()
    
    if erros:
        print("\n⚠️  Problemas encontrados:\n")
        for erro in erros:
            print(f"  {erro}")
        print("\nPor favor, corrija os problemas acima antes de continuar.")
        print("Execute './setup.sh' (Linux/Mac) ou 'setup.bat' (Windows) para configurar.")
        sys.exit(1)
    
    print("✓ Ambiente OK")
    print()
    
    # Verificar se está em venv
    in_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )
    
    if not in_venv:
        print("⚠️  Ativando virtual environment...")
        
        # Determinar comando de ativação baseado no SO
        if sys.platform == "win32":
            activate_script = "venv\\Scripts\\activate.bat"
            print(f"\nExecute: {activate_script}")
            print("E então: python run.py")
        else:
            activate_script = "source venv/bin/activate"
            print(f"\nExecute: {activate_script}")
            print("E então: python run.py")
        
        sys.exit(0)
    
    # Executar servidor
    print("Iniciando servidor FastAPI...")
    print()
    print("=" * 50)
    print("📍 URL: http://localhost:8000")
    print("📊 Documentação API: http://localhost:8000/docs")
    print()
    print("Pressione Ctrl+C para parar o servidor")
    print("=" * 50)
    print()
    
    try:
        # Executar com uvicorn
        subprocess.run([
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host", os.getenv("HOST", "0.0.0.0"),
            "--port", os.getenv("PORT", "8000"),
            "--reload"
        ])
    except KeyboardInterrupt:
        print("\n\n🛑 Servidor parado")
    except Exception as e:
        print(f"\n❌ Erro ao iniciar servidor: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()