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
    
    if strategy == "round-robin":
        # Distribuir sequencialmente
        for i, html_file in enumerate(html_files):
            instance_id, instance_info = sorted_instances[i % len(sorted_instances)]
            dest_dir = Path(instance_info['data_dir']) / 'inputs'
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            shutil.copy2(html_file, dest_dir)
            print(f"✓ {html_file.name} → Instância {instance_id}")
    
    elif strategy == "balanced":
        # Distribuir em lotes equilibrados
        files_per_instance = len(html_files) // len(sorted_instances)
        remainder = len(html_files) % len(sorted_instances)
        
        start_idx = 0
        for instance_id, instance_info in sorted_instances:
            # Distribuir lote + 1 arquivo extra para primeiras instâncias (se houver resto)
            count = files_per_instance + (1 if int(instance_id) <= remainder else 0)
            
            dest_dir = Path(instance_info['data_dir']) / 'inputs'
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            batch = html_files[start_idx:start_idx + count]
            
            print(f"\n📁 Instância {instance_id} ({len(batch)} arquivos):")
            for html_file in batch:
                shutil.copy2(html_file, dest_dir)
                print(f"   ✓ {html_file.name}")
            
            start_idx += count
    
    print("\n" + "=" * 70)
    print("✅ Distribuição concluída!")
    print("\n📝 Próximos passos:")
    for instance_id, instance_info in sorted_instances:
        print(f"   {instance_id}. Acesse http://localhost:{instance_info['backend_port']}")

# ============================================================================
# 2. COLETAR RESULTADOS
# ============================================================================

from pathlib import Path
import shutil

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

    # Ordenação robusta: tenta converter o id para int; se não der, usa string
    def sort_key(item):
        k = str(item[0])
        return (0, int(k)) if k.isdigit() else (1, k)

    for instance_id, instance_info in sorted(instances.items(), key=sort_key):
        # Novo layout: <data_dir>/instance_<id>/outputs
        base_dir = Path(instance_info['data_dir'])
        source_dir = base_dir / f"instance_{instance_id}" / "outputs"

        # Fallback para layout antigo: <data_dir>/outputs
        if not source_dir.exists():
            legacy_dir = base_dir / "outputs"
            if legacy_dir.exists():
                source_dir = legacy_dir

        if not source_dir.exists():
            print(f"⚠️  Instância {instance_id}: sem diretório de outputs (verificado: {source_dir})")
            continue

        json_files = list(source_dir.glob("*.json"))

        if not json_files:
            print(f"ℹ️  Instância {instance_id}: sem resultados em {source_dir}")
            continue

        print(f"\n📁 Instância {instance_id} ({len(json_files)} arquivo(s)) de {source_dir}:")
        for json_file in json_files:
            # Renomeia para incluir a instância no nome final
            new_name = f"i{instance_id}_{json_file.name}"
            dest_file = output_dir / new_name

            shutil.copy2(json_file, dest_file)
            print(f"   ✓ {json_file.name} → {new_name}")
            total_files += 1

    print("\n" + "=" * 70)
    print(f"✅ {total_files} arquivo(s) coletado(s) em: {output_dir}")


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
                    'execucoes': data.get('execucoes_ativas', 0)
                }
            else:
                return {'status': 'error', 'execucoes': 0}
                
        except:
            return {'status': 'offline', 'execucoes': 0}
    
    def display_stats():
        """Exibe estatísticas de todas as instâncias."""
        os.system('clear' if os.name != 'nt' else 'cls')
        
        print("📊 MONITOR DE INSTÂNCIAS")
        print("=" * 80)
        print(f"{'ID':<4} {'Status':<10} {'Backend':<20} {'Redis':<15} {'Execuções':<12}")
        print("-" * 80)
        
        for instance_id, instance_info in sorted(instances.items(), key=lambda x: int(x[0])):
            stats = get_instance_stats(instance_info)
            
            status_icon = {
                'online': '🟢',
                'offline': '🔴',
                'error': '🟡'
            }.get(stats['status'], '⚪')
            
            backend_url = f"localhost:{instance_info['backend_port']}"
            redis_url = f"localhost:{instance_info['redis_port']}"
            
            print(f"{instance_id:<4} {status_icon} {stats['status']:<8} {backend_url:<20} {redis_url:<15} {stats['execucoes']:<12}")
        
        print("=" * 80)
        
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
        outputs_dir = Path(inst_info['data_dir']) / 'outputs'
        
        if not outputs_dir.exists():
            continue
        
        files = list(outputs_dir.glob("*.json"))
        
        if files:
            print(f"\n📁 Instância {inst_id}:")
            for file in files:
                file.unlink()
                print(f"   🗑️  {file.name}")
        else:
            print(f"ℹ️  Instância {inst_id}: sem arquivos")
    
    print("\n✅ Limpeza concluída!")

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

if __name__ == "__main__":
    main()