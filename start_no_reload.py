#!/usr/bin/env python3
"""
Script de execução DIRETO - sem verificações.
Use este se run.py não funcionar.

Execute: python start.py
"""
import os
import sys
from pathlib import Path

def main():
    """Função principal."""
    # Mudar para diretório backend
    backend_dir = Path(__file__).parent / "backend"
    os.chdir(backend_dir)

    # Adicionar backend ao path
    sys.path.insert(0, str(backend_dir))

    print("🎵 Iniciando Compositor de Músicas Educativas")
    print(f"📂 Diretório: {os.getcwd()}")
    print()

    # Importar e executar uvicorn
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=True
    )

if __name__ == '__main__':
    main()