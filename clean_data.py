#!/usr/bin/env python3
"""
Script para limpar a pasta data e suas subpastas.

Uso:
    python clean_data.py                    # Limpeza interativa
    python clean_data.py --force            # Limpa sem confirmar
    python clean_data.py --dry-run          # Mostra o que seria deletado
    python clean_data.py --keep-structure   # Mantém pastas, remove só arquivos
    python clean_data.py --instances-only   # Limpa só pastas instance_*
"""
import os
import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime

# Cores para terminal
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def format_size(bytes):
    """Formata tamanho em bytes para formato legível."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.2f} TB"

def get_dir_size(path):
    """Calcula tamanho total de um diretório."""
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += get_dir_size(entry.path)
    except (PermissionError, FileNotFoundError):
        pass
    return total

def scan_directory(data_dir, instances_only=False):
    """Escaneia o diretório e retorna informações sobre o conteúdo."""
    if not data_dir.exists():
        return None
    
    info = {
        'total_size': 0,
        'total_files': 0,
        'total_dirs': 0,
        'instances': {},
        'other_dirs': {},
        'root_files': []
    }
    
    # Arquivos na raiz de data/
    for item in data_dir.iterdir():
        if item.is_file():
            size = item.stat().st_size
            info['root_files'].append({
                'name': item.name,
                'path': item,
                'size': size
            })
            info['total_files'] += 1
            info['total_size'] += size
        
        elif item.is_dir():
            dir_info = {
                'path': item,
                'files': 0,
                'size': 0,
                'subdirs': []
            }
            
            # Contar arquivos e tamanho
            for root, dirs, files in os.walk(item):
                dir_info['files'] += len(files)
                dir_info['subdirs'].extend(dirs)
                for file in files:
                    try:
                        file_path = Path(root) / file
                        size = file_path.stat().st_size
                        dir_info['size'] += size
                        info['total_size'] += size
                        info['total_files'] += 1
                    except:
                        pass
            
            # Classificar diretório
            if item.name.startswith('instance_'):
                info['instances'][item.name] = dir_info
            elif not instances_only:
                info['other_dirs'][item.name] = dir_info
            
            info['total_dirs'] += 1
    
    return info

def print_scan_results(info, dry_run=False):
    """Imprime os resultados do scan."""
    if not info:
        print(f"{Colors.YELLOW}📁 Pasta 'data' não existe ou está vazia{Colors.RESET}")
        return
    
    print(f"\n{Colors.CYAN}{'🔍 SIMULAÇÃO - ' if dry_run else ''}CONTEÚDO DA PASTA DATA{Colors.RESET}")
    print("=" * 70)
    
    # Resumo
    print(f"\n{Colors.BOLD}📊 RESUMO:{Colors.RESET}")
    print(f"  • Total de arquivos: {Colors.YELLOW}{info['total_files']:,}{Colors.RESET}")
    print(f"  • Total de diretórios: {Colors.YELLOW}{info['total_dirs']:,}{Colors.RESET}")
    print(f"  • Tamanho total: {Colors.YELLOW}{format_size(info['total_size'])}{Colors.RESET}")
    
    
    # Instâncias
    if info.get('instances'):
        print(f"\n{Colors.BOLD}🔹 INSTÂNCIAS:{Colors.RESET}")
        for name, data in sorted(info['instances'].items()):
            print(f"  {Colors.CYAN}{name}/{Colors.RESET}")
            print(f"    ├── Arquivos: {data['files']}")
            print(f"    ├── Tamanho: {format_size(data['size'])}")
            # Subpastas (ordenadas, únicas, mostra até 5 e indica o restante)
            subs = sorted(set(data.get('subdirs', [])))
            if subs:
                shown = subs[:5]
                remaining = len(subs) - len(shown)
                suffix = f" ... (+{remaining})" if remaining > 0 else ""
                print(f"    └── Subpastas: {', '.join(shown)}{suffix}")


    
    # Outros diretórios
    if info['other_dirs']:
        print(f"\n{Colors.BOLD}📁 OUTROS DIRETÓRIOS:{Colors.RESET}")
        for name, data in sorted(info['other_dirs'].items()):
            print(f"  {Colors.GREEN}{name}/{Colors.RESET}")
            print(f"    ├── Arquivos: {data['files']}")
            print(f"    └── Tamanho: {format_size(data['size'])}")
    
    # Arquivos na raiz
    if info['root_files']:
        print(f"\n{Colors.BOLD}📄 ARQUIVOS NA RAIZ:{Colors.RESET}")
        for file in info['root_files'][:10]:  # Mostrar até 10
            print(f"  • {file['name']} ({format_size(file['size'])})")
        if len(info['root_files']) > 10:
            print(f"  ... e mais {len(info['root_files']) - 10} arquivo(s)")
    
    print("\n" + "=" * 70)

def clean_directory(data_dir, keep_structure=False, instances_only=False, force=False):
    """Limpa o diretório data."""
    if not data_dir.exists():
        print(f"{Colors.YELLOW}⚠️  Pasta 'data' não existe{Colors.RESET}")
        return False
    
    # Scan primeiro
    info = scan_directory(data_dir, instances_only)
    
    if not info or (info['total_files'] == 0 and info['total_dirs'] == 0):
        print(f"{Colors.GREEN}✅ Pasta 'data' já está vazia{Colors.RESET}")
        return True
    
    # Mostrar o que será deletado
    print_scan_results(info)
    
    # Confirmar
    if not force:
        print(f"\n{Colors.RED}{Colors.BOLD}⚠️  ATENÇÃO!{Colors.RESET}")
        if instances_only:
            print(f"Isso irá deletar todas as pastas instance_* e seu conteúdo!")
        elif keep_structure:
            print(f"Isso irá deletar {info['total_files']} arquivo(s), mantendo as pastas!")
        else:
            print(f"Isso irá deletar TUDO dentro da pasta 'data'!")
            print(f"Total: {info['total_files']} arquivos, {info['total_dirs']} diretórios")
        
        print(f"\n{Colors.YELLOW}Deseja continuar? (s/N):{Colors.RESET} ", end='')
        response = input().strip().lower()
        
        if response != 's':
            print(f"{Colors.CYAN}❌ Operação cancelada{Colors.RESET}")
            return False
    
    # Executar limpeza
    print(f"\n{Colors.YELLOW}🧹 Iniciando limpeza...{Colors.RESET}")
    
    deleted_files = 0
    deleted_dirs = 0
    errors = []
    
    try:
        if instances_only:
            # Deletar apenas pastas instance_*
            for name, data in info['instances'].items():
                dir_path = data['path']
                try:
                    shutil.rmtree(dir_path)
                    deleted_dirs += 1
                    deleted_files += data['files']
                    print(f"  {Colors.GREEN}✓{Colors.RESET} Removido: {name}/")
                except Exception as e:
                    errors.append(f"{name}: {str(e)}")
                    print(f"  {Colors.RED}✗{Colors.RESET} Erro em {name}: {e}")
        
        elif keep_structure:
            # Manter estrutura, deletar só arquivos
            for root, dirs, files in os.walk(data_dir):
                for file in files:
                    file_path = Path(root) / file
                    try:
                        file_path.unlink()
                        deleted_files += 1
                        print(f"  {Colors.GREEN}✓{Colors.RESET} Removido: {file_path.relative_to(data_dir)}")
                    except Exception as e:
                        errors.append(f"{file}: {str(e)}")
        
        else:
            # Deletar tudo
            for item in data_dir.iterdir():
                try:
                    if item.is_file():
                        item.unlink()
                        deleted_files += 1
                        print(f"  {Colors.GREEN}✓{Colors.RESET} Removido: {item.name}")
                    elif item.is_dir():
                        num_files = sum(1 for _ in item.rglob('*') if _.is_file())
                        shutil.rmtree(item)
                        deleted_dirs += 1
                        deleted_files += num_files
                        print(f"  {Colors.GREEN}✓{Colors.RESET} Removido: {item.name}/ ({num_files} arquivos)")
                except Exception as e:
                    errors.append(f"{item.name}: {str(e)}")
                    print(f"  {Colors.RED}✗{Colors.RESET} Erro em {item.name}: {e}")
    
    except Exception as e:
        print(f"{Colors.RED}❌ Erro durante limpeza: {e}{Colors.RESET}")
        return False
    
    # Resumo
    print(f"\n{Colors.BOLD}📊 RESUMO DA LIMPEZA:{Colors.RESET}")
    print(f"  • Arquivos removidos: {Colors.GREEN}{deleted_files:,}{Colors.RESET}")
    print(f"  • Diretórios removidos: {Colors.GREEN}{deleted_dirs:,}{Colors.RESET}")
    
    if errors:
        print(f"  • Erros encontrados: {Colors.RED}{len(errors)}{Colors.RESET}")
        for error in errors[:5]:
            print(f"    - {error}")
    
    print(f"\n{Colors.GREEN}✅ Limpeza concluída!{Colors.RESET}")
    return True

def create_backup(data_dir, backup_name=None):
    """Cria backup da pasta data antes de limpar."""
    if not data_dir.exists():
        print(f"{Colors.YELLOW}⚠️  Pasta 'data' não existe{Colors.RESET}")
        return None
    
    if not backup_name:
        backup_name = f"data_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    backup_path = data_dir.parent / backup_name
    
    print(f"{Colors.CYAN}📦 Criando backup...{Colors.RESET}")
    print(f"  Origem: {data_dir}")
    print(f"  Destino: {backup_path}")
    
    try:
        shutil.copytree(data_dir, backup_path)
        size = get_dir_size(backup_path)
        print(f"{Colors.GREEN}✅ Backup criado: {backup_path} ({format_size(size)}){Colors.RESET}")
        return backup_path
    except Exception as e:
        print(f"{Colors.RED}❌ Erro ao criar backup: {e}{Colors.RESET}")
        return None

def main():
    """Função principal."""
    parser = argparse.ArgumentParser(
        description="Limpa a pasta data e suas subpastas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python clean_data.py                    # Limpeza interativa (pede confirmação)
  python clean_data.py --force            # Limpa sem confirmar
  python clean_data.py --dry-run          # Mostra o que seria deletado
  python clean_data.py --keep-structure   # Mantém pastas, remove só arquivos
  python clean_data.py --instances-only   # Limpa só pastas instance_*
  python clean_data.py --backup           # Cria backup antes de limpar
        """
    )
    
    parser.add_argument('--force', '-f', action='store_true',
                       help='Limpa sem pedir confirmação')
    parser.add_argument('--dry-run', '-n', action='store_true',
                       help='Mostra o que seria deletado sem deletar')
    parser.add_argument('--keep-structure', '-k', action='store_true',
                       help='Mantém estrutura de pastas, remove apenas arquivos')
    parser.add_argument('--instances-only', '-i', action='store_true',
                       help='Remove apenas pastas instance_*')
    parser.add_argument('--backup', '-b', action='store_true',
                       help='Cria backup antes de limpar')
    parser.add_argument('--backup-name', type=str,
                       help='Nome para o backup (padrão: data_backup_TIMESTAMP)')
    parser.add_argument('--data-dir', type=str, default='data',
                       help='Caminho para pasta data (padrão: ./data)')
    
    args = parser.parse_args()
    
    # Definir pasta data
    data_dir = Path(args.data_dir)
    if not data_dir.is_absolute():
        data_dir = Path.cwd() / data_dir
    
    print(f"\n{Colors.CYAN}{Colors.BOLD}🧹 LIMPADOR DE PASTA DATA{Colors.RESET}")
    print("=" * 70)
    print(f"📁 Pasta alvo: {Colors.YELLOW}{data_dir}{Colors.RESET}")
    
    # Dry run - apenas mostrar
    if args.dry_run:
        print(f"\n{Colors.YELLOW}🔍 MODO DRY-RUN (não deleta nada){Colors.RESET}")
        info = scan_directory(data_dir, args.instances_only)
        print_scan_results(info, dry_run=True)
        
        if info and info['total_files'] > 0:
            print(f"\n{Colors.CYAN}ℹ️  Para executar a limpeza real, remova --dry-run{Colors.RESET}")
        return
    
    # Criar backup se solicitado
    if args.backup:
        backup_path = create_backup(data_dir, args.backup_name)
        if not backup_path and not args.force:
            print(f"\n{Colors.YELLOW}Continuar sem backup? (s/N):{Colors.RESET} ", end='')
            if input().strip().lower() != 's':
                print(f"{Colors.CYAN}❌ Operação cancelada{Colors.RESET}")
                return
    
    # Executar limpeza
    success = clean_directory(
        data_dir,
        keep_structure=args.keep_structure,
        instances_only=args.instances_only,
        force=args.force
    )
    
    if success:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 Pasta 'data' limpa com sucesso!{Colors.RESET}")
    else:
        print(f"\n{Colors.YELLOW}⚠️  Limpeza não foi concluída completamente{Colors.RESET}")

if __name__ == "__main__":
    main()