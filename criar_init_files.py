"""
Script para criar todos os arquivos __init__.py necessários.
Execute: python criar_init_files.py
"""
from pathlib import Path

# Diretórios que precisam de __init__.py
diretorios = [
    "backend",
    "backend/app",
    "backend/app/api",
    "backend/app/agents",
    "backend/app/core",
    "backend/app/retry",
    "backend/app/utils",
    "backend/tests",
]

def criar_init_files():
    """Cria arquivos __init__.py em todos os diretórios necessários."""
    for diretorio in diretorios:
        dir_path = Path(diretorio)
        
        # Criar diretório se não existir
        dir_path.mkdir(parents=True, exist_ok=True)
        
        # Criar __init__.py
        init_file = dir_path / "__init__.py"
        
        if not init_file.exists():
            # Conteúdo do __init__.py baseado no diretório
            if "backend" == diretorio:
                content = '"""Backend package."""\n'
            elif "app" in diretorio:
                nome = diretorio.split("/")[-1]
                content = f'"""{nome.capitalize()} module."""\n'
            else:
                content = ""
            
            with open(init_file, "w", encoding="utf-8") as f:
                f.write(content)
            
            print(f"✓ Criado: {init_file}")
        else:
            print(f"○ Já existe: {init_file}")

if __name__ == "__main__":
    print("Criando arquivos __init__.py...")
    print()
    criar_init_files()
    print()
    print("✓ Concluído!")