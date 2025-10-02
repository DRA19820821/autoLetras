#!/usr/bin/env python3
"""
Script de execução corrigido - garante paths corretos.
Execute: python start.py
"""
import os
import sys
from pathlib import Path

def main():
    """Função principal."""
    # Diretório raiz do projeto
    PROJECT_ROOT = Path(__file__).parent.absolute()
    BACKEND_DIR = PROJECT_ROOT / "backend"
    
    print("🎵 Compositor de Músicas Educativas")
    print("=" * 60)
    print(f"📂 Diretório do projeto: {PROJECT_ROOT}")
    print(f"📂 Diretório backend: {BACKEND_DIR}")
    print()
    
    # Verificar se backend existe
    if not BACKEND_DIR.exists():
        print("❌ Diretório 'backend' não encontrado!")
        print(f"   Esperado em: {BACKEND_DIR}")
        sys.exit(1)
    
    # Verificar se main.py existe
    main_py = BACKEND_DIR / "main.py"
    if not main_py.exists():
        print("❌ Arquivo 'backend/main.py' não encontrado!")
        print(f"   Esperado em: {main_py}")
        sys.exit(1)
    
    # Adicionar backend ao path ANTES de mudar de diretório
    sys.path.insert(0, str(BACKEND_DIR))
    print(f"✓ Adicionado ao sys.path: {BACKEND_DIR}")
    
    # NÃO mudar de diretório - manter no root para paths relativos funcionarem
    # Os caminhos em main.py são relativos ao root do projeto
    print(f"✓ Working directory: {os.getcwd()}")
    print()
    
    # Verificar estrutura
    print("Verificando estrutura de diretórios...")
    required_dirs = [
        PROJECT_ROOT / "data",
        PROJECT_ROOT / "data/inputs",
        PROJECT_ROOT / "data/outputs",
        PROJECT_ROOT / "frontend",
        PROJECT_ROOT / "frontend/static",
        PROJECT_ROOT / "frontend/templates",
    ]
    
    for dir_path in required_dirs:
        if dir_path.exists():
            print(f"  ✓ {dir_path.relative_to(PROJECT_ROOT)}")
        else:
            print(f"  ⚠ {dir_path.relative_to(PROJECT_ROOT)} não encontrado")
    
    print()
    print("=" * 60)
    print("🚀 Iniciando servidor...")
    print("📍 URL: http://localhost:8000")
    print("📊 API Docs: http://localhost:8000/docs")
    print()
    print("Pressione Ctrl+C para parar")
    print("=" * 60)
    print()
    
    try:
        # Importar uvicorn
        import uvicorn
        
        # Executar servidor
        # IMPORTANTE: usar "backend.main:app" porque adicionamos backend/ ao path
        uvicorn.run(
            "backend.main:app",
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", 8000)),
            reload=True,
            reload_dirs=[str(BACKEND_DIR)]
        )
        
    except KeyboardInterrupt:
        print("\n\n🛑 Servidor parado")
    except Exception as e:
        print(f"\n❌ Erro ao iniciar servidor: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()