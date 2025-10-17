#!/usr/bin/env python3
"""
Scripts auxiliares para gerenciar múltiplas instâncias.

distribute_files.py - Distribui arquivos entre instâncias
collect_results.py - Coleta resultados de todas as instâncias
monitor_all.py - Monitora todas as instâncias em tempo real
"""

import os
import json
import shutil
from pathlib import Path
from typing import List
import argparse

PROJECT_ROOT = Path(__file__).parent
INSTANCES_FILE = PROJECT_ROOT / ".instances.json"

def load_instances():
    """Carrega informações das instâncias ativas."""
    if INSTANCES_FILE.exists():
        with open(INSTANCES_FILE, 'r') as f:
            return json.load(f)
    return {}

# ============================================================================
# 1. DISTRIBUIR ARQUIVOS ENTRE INSTÂNCIAS
# ============================================================================

def distribute_files(source_dir: Path, instances: dict, strategy: str = "round-robin"):
    """
    Distribui arquivos HTML entre instâncias.
    
    Args:
        source_dir: Diretório com arquivos HTML
        instances: Dicionário de instâncias ativas
        strategy: 'round-robin' ou 'balanced'
    """
    html_files = list(source_dir.glob("*.html"))
    
    if not html_files:
        print("❌ Nenhum arquivo HTML encontrado em:", source_dir)
        return
    
    if not instances:
        print("❌ Nenhuma instância ativa. Execute: python orchestrator.py start")
        return
    
    print(f"\n📦 Distribuindo {len(html_files)} arquivo(s) entre {len(instances)} instância(s)")
    print(f"   Estratégia: {strategy}")
    print("=" * 70)
    
    # Ordenar instâncias por ID
    sorted_instances = sorted(instances.items(), key=lambda x: int(x[0]))
    
    # CORREÇÃO: Garantir que os arquivos sejam copiados para o diretório correto
    files_distributed = {inst_id: [] for inst_id, _ in sorted_instances}
    
    if strategy == "round-robin":
        # Distribuir sequencialmente
        for i, html_file in enumerate(html_files):
            instance_id, instance_info = sorted_instances[i % len(sorted_instances)]
            # CORREÇÃO: Usar o caminho correto (sem duplicação)
            dest_dir = Path(instance_info['data_dir']) / 'inputs'
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            dest_file = dest_dir / html_file.name
            shutil.copy2(html_file, dest_file)
            files_distributed[instance_id].append(html_file.name)
            print(f"✓ {html_file.name} → Instância {instance_id} ({dest_file})")
    
    elif strategy == "balanced":
        # Distribuir em lotes equilibrados
        files_per_instance = len(html_files) // len(sorted_instances)
        remainder = len(html_files) % len(sorted_instances)
        
        start_idx = 0
        for instance_id, instance_info in sorted_instances:
            # Distribuir lote + 1 arquivo extra para primeiras instâncias (se houver resto)
            count = files_per_instance + (1 if int(instance_id) <= remainder else 0)
            
            # CORREÇÃO: Usar o caminho correto
            dest_dir = Path(instance_info['data_dir']) / 'inputs'
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            batch = html_files[start_idx:start_idx + count]
            
            print(f"\n📁 Instância {instance_id} ({len(batch)} arquivos):")
            print(f"   Destino: {dest_dir}")
            
            for html_file in batch:
                dest_file = dest_dir / html_file.name
                shutil.copy2(html_file, dest_file)
                files_distributed[instance_id].append(html_file.name)
                print(f"   ✓ {html_file.name}")
            
            start_idx += count
    
    # Verificar distribuição
    print("\n" + "=" * 70)
    print("📊 RESUMO DA DISTRIBUIÇÃO:")
    print("=" * 70)
    for instance_id, files in files_distributed.items():
        print(f"Instância {instance_id}: {len(files)} arquivo(s)")
        if files:
            for f in files[:3]:  # Mostrar até 3 arquivos
                print(f"  - {f}")
            if len(files) > 3:
                print(f"  ... e mais {len(files) - 3}")
    
    print("\n" + "=" * 70)
    print("✅ Distribuição concluída!")
    print("\n📝 Próximos passos:")
    for instance_id, instance_info in sorted_instances:
        print(f"   {instance_id}. Acesse http://localhost:{instance_info['backend_port']}")

# ============================================================================
# 2. COLETAR RESULTADOS
# ============================================================================

def collect_results(output_dir: Path, instances: dict):
    """
    Coleta resultados de todas as instâncias para um diretório único.

    Args:
        output_dir: Diretório de destino
        instances: Dicionário de instâncias
    """
    if not instances:
        print("❌ Nenhuma instância ativa")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📥 Coletando resultados de {len(instances)} instância(s)")
    print(f"   Destino: {output_dir}")
    print("=" * 70)

    total_files = 0
    summary = {}

    # Ordenação robusta
    def sort_key(item):
        k = str(item[0])
        return (0, int(k)) if k.isdigit() else (1, k)

    for instance_id, instance_info in sorted(instances.items(), key=sort_key):
        # CORREÇÃO: Usar o caminho correto (sem duplicação)
        source_dir = Path(instance_info['data_dir']) / "outputs"
        
        if not source_dir.exists():
            print(f"⚠️  Instância {instance_id}: sem diretório de outputs")
            summary[instance_id] = {"status": "sem_outputs", "files": 0}
            continue

        json_files = list(source_dir.glob("*.json"))

        if not json_files:
            print(f"ℹ️  Instância {instance_id}: sem resultados em {source_dir}")
            summary[instance_id] = {"status": "vazio", "files": 0}
            continue

        print(f"\n📁 Instância {instance_id} ({len(json_files)} arquivo(s)):")
        print(f"   Origem: {source_dir}")
        
        collected_files = []
        for json_file in json_files:
            # Renomeia para incluir a instância no nome final
            #new_name = f"i{instance_id}_{json_file.name}"
            p = Path(json_file)
            new_name = f"{p.stem}_i{instance_id}{p.suffix}"
            dest_file = output_dir / new_name

            shutil.copy2(json_file, dest_file)
            collected_files.append(new_name)
            print(f"   ✓ {json_file.name} → {new_name}")
            total_files += 1
        
        summary[instance_id] = {
            "status": "coletado",
            "files": len(collected_files),
            "samples": collected_files[:3]  # Primeiros 3 arquivos como amostra
        }

    # Resumo
    print("\n" + "=" * 70)
    print("📊 RESUMO DA COLETA:")
    print("=" * 70)
    for instance_id, info in summary.items():
        print(f"Instância {instance_id}: {info['status']} ({info['files']} arquivos)")
        if info.get('samples'):
            for sample in info['samples']:
                print(f"  - {sample}")
    
    print("\n" + "=" * 70)
    print(f"✅ Total: {total_files} arquivo(s) coletado(s) em: {output_dir}")


# ============================================================================
# 3. MONITORAR TODAS AS INSTÂNCIAS
# ============================================================================

def monitor_all(instances: dict, follow: bool = False):
    """
    Mostra status consolidado de todas as instâncias.
    
    Args:
        instances: Dicionário de instâncias
        follow: Se True, atualiza continuamente
    """
    import time
    import subprocess
    
    if not instances:
        print("❌ Nenhuma instância ativa")
        return
    
    def get_instance_stats(instance_info):
        """Coleta estatísticas de uma instância."""
        try:
            # Buscar status via API
            import requests
            backend_port = instance_info['backend_port']
            
            response = requests.get(
                f"http://localhost:{backend_port}/health",
                timeout=2
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'status': 'online',
                    'execucoes': data.get('execucoes_ativas', 0),
                    'input_files': data.get('input_files', 0),
                    'output_files': data.get('output_files', 0)
                }
            else:
                return {'status': 'error', 'execucoes': 0, 'input_files': 0, 'output_files': 0}
                
        except:
            return {'status': 'offline', 'execucoes': 0, 'input_files': 0, 'output_files': 0}
    
    def display_stats():
        """Exibe estatísticas de todas as instâncias."""
        os.system('clear' if os.name != 'nt' else 'cls')
        
        print("📊 MONITOR DE INSTÂNCIAS")
        print("=" * 90)
        print(f"{'ID':<4} {'Status':<10} {'Backend':<20} {'Redis':<15} {'Exec':<6} {'Input':<8} {'Output':<8}")
        print("-" * 90)
        
        for instance_id, instance_info in sorted(instances.items(), key=lambda x: int(x[0])):
            stats = get_instance_stats(instance_info)
            
            status_icon = {
                'online': '🟢',
                'offline': '🔴',
                'error': '🟡'
            }.get(stats['status'], '⚪')
            
            backend_url = f"localhost:{instance_info['backend_port']}"
            redis_url = f"localhost:{instance_info['redis_port']}"
            
            print(f"{instance_id:<4} {status_icon} {stats['status']:<8} "
                  f"{backend_url:<20} {redis_url:<15} "
                  f"{stats['execucoes']:<6} {stats['input_files']:<8} {stats['output_files']:<8}")
        
        print("=" * 90)
        
        # Mostrar diretórios
        print("\n📁 DIRETÓRIOS:")
        for instance_id, instance_info in sorted(instances.items(), key=lambda x: int(x[0])):
            print(f"   Instância {instance_id}: {instance_info['data_dir']}")
        
        if follow:
            print("\nAtualizando a cada 5 segundos... (Ctrl+C para sair)")
    
    # Primeira exibição
    display_stats()
    
    # Se follow, atualizar continuamente
    if follow:
        try:
            while True:
                time.sleep(5)
                display_stats()
        except KeyboardInterrupt:
            print("\n\n🛑 Monitoramento interrompido")

# ============================================================================
# 4. LIMPAR OUTPUTS
# ============================================================================

def clean_outputs(instances: dict, instance_id: str = None):
    """
    Limpa outputs de instâncias.
    
    Args:
        instances: Dicionário de instâncias
        instance_id: ID específico ou None para todas
    """
    if instance_id:
        if instance_id not in instances:
            print(f"❌ Instância {instance_id} não encontrada")
            return
        
        to_clean = {instance_id: instances[instance_id]}
    else:
        to_clean = instances
    
    print(f"\n🧹 Limpando outputs de {len(to_clean)} instância(s)")
    
    for inst_id, inst_info in to_clean.items():
        # CORREÇÃO: Usar o caminho correto
        outputs_dir = Path(inst_info['data_dir']) / 'outputs'
        
        if not outputs_dir.exists():
            print(f"ℹ️  Instância {inst_id}: diretório não existe")
            continue
        
        files = list(outputs_dir.glob("*.json"))
        
        if files:
            print(f"\n📁 Instância {inst_id} ({outputs_dir}):")
            for file in files:
                file.unlink()
                print(f"   🗑️  {file.name}")
        else:
            print(f"ℹ️  Instância {inst_id}: sem arquivos")
    
    print("\n✅ Limpeza concluída!")

# ============================================================================
# 5. VALIDAR ESTRUTURA (NOVO)
# ============================================================================

def validate_structure(instances: dict):
    """
    Valida a estrutura de diretórios das instâncias.
    
    Args:
        instances: Dicionário de instâncias
    """
    print("\n🔍 VALIDANDO ESTRUTURA DE DIRETÓRIOS")
    print("=" * 70)
    
    all_ok = True
    
    for instance_id, instance_info in sorted(instances.items(), key=lambda x: int(x[0])):
        print(f"\n📁 Instância {instance_id}:")
        data_dir = Path(instance_info['data_dir'])
        
        # Verificar diretório principal
        if data_dir.exists():
            print(f"  ✅ {data_dir}")
        else:
            print(f"  ❌ {data_dir} NÃO EXISTE")
            all_ok = False
            continue
        
        # Verificar subdiretórios
        subdirs = ['inputs', 'outputs', 'checkpoints', 'logs']
        for subdir in subdirs:
            subdir_path = data_dir / subdir
            if subdir_path.exists():
                # Contar arquivos
                files = list(subdir_path.glob("*"))
                if files:
                    print(f"  ✅ {subdir}/ ({len(files)} arquivos)")
                else:
                    print(f"  ✅ {subdir}/ (vazio)")
            else:
                print(f"  ❌ {subdir}/ NÃO EXISTE")
                all_ok = False
    
    print("\n" + "=" * 70)
    if all_ok:
        print("✅ Estrutura de diretórios OK!")
    else:
        print("❌ Problemas encontrados na estrutura")
        print("\nPara corrigir, execute:")
        print("  python orchestrator.py stop --all")
        print("  python orchestrator.py start --instances N")

# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Scripts auxiliares para instâncias paralelas"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Comandos')
    
    # distribute
    dist_parser = subparsers.add_parser('distribute', help='Distribuir arquivos')
    dist_parser.add_argument('source', type=Path, help='Diretório com HTMLs')
    dist_parser.add_argument('--strategy', choices=['round-robin', 'balanced'],
                           default='balanced', help='Estratégia de distribuição')
    
    # collect
    collect_parser = subparsers.add_parser('collect', help='Coletar resultados')
    collect_parser.add_argument('--output', type=Path, default=Path('collected_results'),
                              help='Diretório de destino')
    
    # monitor
    monitor_parser = subparsers.add_parser('monitor', help='Monitorar instâncias')
    monitor_parser.add_argument('--follow', action='store_true',
                              help='Atualizar continuamente')
    
    # clean
    clean_parser = subparsers.add_parser('clean', help='Limpar outputs')
    clean_parser.add_argument('--instance', help='ID específico')
    
    # validate (novo)
    validate_parser = subparsers.add_parser('validate', help='Validar estrutura')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    instances = load_instances()
    
    if args.command == 'distribute':
        distribute_files(args.source, instances, args.strategy)
    
    elif args.command == 'collect':
        collect_results(args.output, instances)
    
    elif args.command == 'monitor':
        monitor_all(instances, args.follow)
    
    elif args.command == 'clean':
        clean_outputs(instances, args.instance)
    
    elif args.command == 'validate':
        validate_structure(instances)

if __name__ == "__main__":
    main()