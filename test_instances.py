#!/usr/bin/env python3
"""
Script para testar o sistema de múltiplas instâncias.
Execute após iniciar as instâncias com orchestrator.py

Uso:
    python test_instances.py
"""
import os
import sys
import json
import shutil
import time
import requests
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent
INSTANCES_FILE = PROJECT_ROOT / ".instances.json"

def load_instances():
    """Carrega informações das instâncias ativas."""
    if INSTANCES_FILE.exists():
        with open(INSTANCES_FILE, 'r') as f:
            return json.load(f)
    return {}

def create_test_html(filename: str, tema: str, topico: str, conteudo: str):
    """Cria um arquivo HTML de teste."""
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{tema} - {topico} - Guia Completo</title>
</head>
<body>
    <section id="fundamentacao">
        <h1>{tema}</h1>
        <h2>{topico}</h2>
        <p>{conteudo}</p>
    </section>
</body>
</html>"""
    return html

def test_instance_structure():
    """Testa a estrutura de diretórios das instâncias."""
    print("\n" + "=" * 70)
    print("1️⃣  VERIFICANDO ESTRUTURA DE DIRETÓRIOS")
    print("=" * 70)
    
    instances = load_instances()
    
    if not instances:
        print("❌ Nenhuma instância ativa")
        print("   Execute: python orchestrator.py start --instances 3")
        return False
    
    all_ok = True
    
    for instance_id, info in instances.items():
        print(f"\n📁 Instância {instance_id}:")
        data_dir = Path(info['data_dir'])
        
        # Verificar se não há duplicação
        expected_path = PROJECT_ROOT / "data" / f"instance_{instance_id}"
        if data_dir != expected_path:
            print(f"  ⚠️  Caminho inesperado: {data_dir}")
            print(f"     Esperado: {expected_path}")
        
        # Verificar subdiretórios
        for subdir in ['inputs', 'outputs', 'checkpoints', 'logs']:
            subdir_path = data_dir / subdir
            if subdir_path.exists():
                print(f"  ✅ {subdir_path.relative_to(PROJECT_ROOT)}")
            else:
                print(f"  ❌ {subdir_path.relative_to(PROJECT_ROOT)} NÃO EXISTE")
                all_ok = False
    
    return all_ok

def test_instance_apis():
    """Testa as APIs de cada instância."""
    print("\n" + "=" * 70)
    print("2️⃣  TESTANDO APIs DAS INSTÂNCIAS")
    print("=" * 70)
    
    instances = load_instances()
    all_ok = True
    
    for instance_id, info in instances.items():
        print(f"\n🔹 Instância {instance_id} (porta {info['backend_port']}):")
        
        try:
            # Testar health endpoint
            response = requests.get(
                f"http://localhost:{info['backend_port']}/health",
                timeout=3
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ API respondendo")
                print(f"     Instance ID: {data.get('instance_id', 'N/A')}")
                print(f"     Data Dir: {data.get('data_dir', 'N/A')}")
                print(f"     Input files: {data.get('input_files', 0)}")
                print(f"     Output files: {data.get('output_files', 0)}")
            else:
                print(f"  ❌ API retornou status {response.status_code}")
                all_ok = False
                
        except requests.exceptions.ConnectionError:
            print(f"  ❌ Não foi possível conectar")
            all_ok = False
        except Exception as e:
            print(f"  ❌ Erro: {e}")
            all_ok = False
    
    return all_ok

def test_file_distribution():
    """Testa a distribuição de arquivos."""
    print("\n" + "=" * 70)
    print("3️⃣  TESTANDO DISTRIBUIÇÃO DE ARQUIVOS")
    print("=" * 70)
    
    instances = load_instances()
    
    if not instances:
        print("❌ Nenhuma instância ativa")
        return False
    
    # Criar diretório temporário com arquivos de teste
    test_dir = PROJECT_ROOT / "test_files"
    test_dir.mkdir(exist_ok=True)
    
    # Criar arquivos de teste
    num_files = len(instances) * 2  # 2 arquivos por instância
    print(f"\n📝 Criando {num_files} arquivos de teste...")
    
    test_files = []
    for i in range(num_files):
        filename = f"teste_{i+1:02d}.html"
        filepath = test_dir / filename
        
        html_content = create_test_html(
            filename=filename,
            tema=f"Tema Teste {i+1}",
            topico=f"Tópico {i+1}",
            conteudo=f"Este é o conteúdo de teste número {i+1}. " * 10
        )
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        test_files.append(filename)
        print(f"  ✅ {filename}")
    
    # Distribuir arquivos usando round-robin
    print(f"\n📦 Distribuindo arquivos entre {len(instances)} instância(s)...")
    
    sorted_instances = sorted(instances.items(), key=lambda x: int(x[0]))
    
    for i, test_file in enumerate(test_files):
        instance_id, instance_info = sorted_instances[i % len(sorted_instances)]
        
        source = test_dir / test_file
        dest_dir = Path(instance_info['data_dir']) / 'inputs'
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / test_file
        
        shutil.copy2(source, dest)
        print(f"  ✅ {test_file} → Instância {instance_id}")
    
    # Verificar distribuição
    print("\n🔍 Verificando distribuição...")
    all_ok = True
    
    for instance_id, instance_info in sorted_instances:
        inputs_dir = Path(instance_info['data_dir']) / 'inputs'
        if inputs_dir.exists():
            files = list(inputs_dir.glob("*.html"))
            print(f"  Instância {instance_id}: {len(files)} arquivo(s)")
            if len(files) == 0:
                all_ok = False
        else:
            print(f"  Instância {instance_id}: ❌ Diretório não existe")
            all_ok = False
    
    # Limpar arquivos de teste
    shutil.rmtree(test_dir, ignore_errors=True)
    
    return all_ok

def test_file_upload():
    """Testa o upload de arquivo via API."""
    print("\n" + "=" * 70)
    print("4️⃣  TESTANDO UPLOAD VIA API")
    print("=" * 70)
    
    instances = load_instances()
    
    if not instances:
        print("❌ Nenhuma instância ativa")
        return False
    
    # Testar upload em uma instância
    instance_id = list(instances.keys())[0]
    instance_info = instances[instance_id]
    
    print(f"\n🔸 Testando upload na instância {instance_id}...")
    
    # Criar arquivo de teste
    test_file = "upload_test.html"
    test_content = create_test_html(
        filename=test_file,
        tema="Upload Test",
        topico="API Test",
        conteudo="Testando upload via API"
    )
    
    # Preparar arquivo para upload
    files = {
        'files': (test_file, test_content, 'text/html')
    }
    
    try:
        # Fazer upload
        response = requests.post(
            f"http://localhost:{instance_info['backend_port']}/api/upload",
            files=files,
            timeout=5
        )
        
        if response.status_code == 200:
            print(f"  ✅ Upload bem-sucedido")
            
            # Verificar se arquivo foi salvo
            expected_path = Path(instance_info['data_dir']) / 'inputs' / test_file
            if expected_path.exists():
                print(f"  ✅ Arquivo salvo em: {expected_path}")
                # Limpar
                expected_path.unlink()
                return True
            else:
                print(f"  ❌ Arquivo não encontrado em: {expected_path}")
                return False
        else:
            print(f"  ❌ Upload falhou com status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"  ❌ Erro no upload: {e}")
        return False

def main():
    """Executa todos os testes."""
    print("\n" + "🧪" * 35)
    print("   TESTE DO SISTEMA DE MÚLTIPLAS INSTÂNCIAS")
    print("🧪" * 35)
    
    # Carregar instâncias
    instances = load_instances()
    
    if not instances:
        print("\n❌ Nenhuma instância ativa!")
        print("\nPara iniciar instâncias:")
        print("  python orchestrator.py start --instances 3")
        sys.exit(1)
    
    print(f"\n📊 Instâncias ativas: {len(instances)}")
    for instance_id, info in instances.items():
        print(f"   • Instância {instance_id}: http://localhost:{info['backend_port']}")
    
    # Executar testes
    results = {}
    
    print("\n🔄 Executando testes...")
    
    # Teste 1: Estrutura
    results['estrutura'] = test_instance_structure()
    time.sleep(1)
    
    # Teste 2: APIs
    results['apis'] = test_instance_apis()
    time.sleep(1)
    
    # Teste 3: Distribuição
    results['distribuicao'] = test_file_distribution()
    time.sleep(1)
    
    # Teste 4: Upload
    results['upload'] = test_file_upload()
    
    # Resumo
    print("\n" + "=" * 70)
    print("📊 RESUMO DOS TESTES")
    print("=" * 70)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASSOU" if passed else "❌ FALHOU"
        print(f"  {test_name.capitalize()}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 TODOS OS TESTES PASSARAM!")
        print("\nO sistema está pronto para uso:")
        print("1. Distribua arquivos: python helper_scripts.py distribute <dir_com_htmls>")
        print("2. Acesse cada instância e processe")
        print("3. Colete resultados: python helper_scripts.py collect")
    else:
        print("⚠️  ALGUNS TESTES FALHARAM")
        print("\nVerifique os problemas acima e tente:")
        print("1. Parar instâncias: python orchestrator.py stop --all")
        print("2. Reiniciar: python orchestrator.py start --instances 3")
        print("3. Executar testes novamente: python test_instances.py")
    
    print("=" * 70)

if __name__ == "__main__":
    main()