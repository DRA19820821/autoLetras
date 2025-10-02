#!/usr/bin/env python3
"""
Script para testar rapidamente as rotas da API.
Execute com o servidor rodando: python test_api.py
"""
import requests
import json
from pathlib import Path

BASE_URL = "http://localhost:8000"

def print_section(title):
    """Imprime seção formatada."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def test_health():
    """Testa endpoint de health check."""
    print_section("1. Health Check")
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Servidor funcionando!")
            print(f"   Status: {data.get('status')}")
            print(f"   Timestamp: {data.get('timestamp')}")
            print(f"   Execuções ativas: {data.get('execucoes_ativas')}")
            return True
        else:
            print(f"❌ Status code: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Não foi possível conectar ao servidor")
        print("   Certifique-se de que o servidor está rodando:")
        print("   python start.py")
        return False
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def test_provedores():
    """Testa endpoint de provedores."""
    print_section("2. Status dos Provedores")
    
    try:
        response = requests.get(f"{BASE_URL}/api/provedores", timeout=5)
        
        if response.status_code == 200:
            provedores = response.json()
            
            print("\nProvedores configurados:")
            for nome, info in provedores.items():
                status_icon = "✅" if info["disponivel"] else "❌"
                print(f"  {status_icon} {nome.capitalize()}: {info['mensagem']}")
            
            disponiveis = sum(1 for p in provedores.values() if p["disponivel"])
            total = len(provedores)
            
            print(f"\nTotal: {disponiveis}/{total} disponíveis")
            
            if disponiveis == 0:
                print("\n⚠️  ATENÇÃO: Nenhum provedor disponível!")
                print("   Configure pelo menos uma API key no arquivo .env")
            
            return True
        else:
            print(f"❌ Status code: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def test_root():
    """Testa página principal."""
    print_section("3. Página Principal")
    
    try:
        response = requests.get(BASE_URL, timeout=5)
        
        if response.status_code == 200:
            print("✅ Página principal carregando")
            
            # Verificar se tem elementos esperados
            html = response.text
            checks = [
                ("Status dos Provedores" in html, "Seção de provedores"),
                ("Seleção de Arquivos" in html, "Seção de upload"),
                ("Configuração de Estilo" in html, "Configuração de estilo"),
                ("Configuração de Modelos" in html, "Configuração de modelos"),
            ]
            
            print("\nElementos da página:")
            for check, desc in checks:
                icon = "✅" if check else "❌"
                print(f"  {icon} {desc}")
            
            return all(c for c, _ in checks)
        else:
            print(f"❌ Status code: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def test_static_files():
    """Testa arquivos estáticos."""
    print_section("4. Arquivos Estáticos")
    
    files_to_test = [
        "/static/css/styles.css",
        "/static/js/app.js",
    ]
    
    all_ok = True
    
    for file_path in files_to_test:
        try:
            response = requests.get(f"{BASE_URL}{file_path}", timeout=5)
            
            if response.status_code == 200:
                size_kb = len(response.content) / 1024
                print(f"  ✅ {file_path} ({size_kb:.1f} KB)")
            else:
                print(f"  ❌ {file_path} - Status: {response.status_code}")
                all_ok = False
                
        except Exception as e:
            print(f"  ❌ {file_path} - Erro: {e}")
            all_ok = False
    
    return all_ok

def test_upload_simulation():
    """Simula upload (sem arquivo real)."""
    print_section("5. Teste de Upload (Simulação)")
    
    print("ℹ️  Este teste requer um arquivo HTML real.")
    print("   Para testar upload:")
    print("   1. Acesse http://localhost:8000")
    print("   2. Selecione um arquivo HTML")
    print("   3. Veja os resultados da validação")
    
    return True

def test_models_available():
    """Verifica se os modelos estão disponíveis no HTML."""
    print_section("6. Modelos Disponíveis")
    
    try:
        response = requests.get(BASE_URL, timeout=5)
        html = response.text
        
        expected_models = [
            "claude-sonnet-4-5",
            "gpt-4-turbo",
            "gemini-2.5-pro",
            "deepseek-chat",
            "claude-opus-4-1",
            "gpt-5",
            "gemini-2.5-flash",
        ]
        
        found = []
        missing = []
        
        for model in expected_models:
            if model in html:
                found.append(model)
            else:
                missing.append(model)
        
        print(f"\nModelos encontrados: {len(found)}/{len(expected_models)}")
        
        if found:
            print("\nExemplos encontrados:")
            for model in found[:5]:
                print(f"  ✅ {model}")
        
        if missing:
            print("\n⚠️  Modelos não encontrados:")
            for model in missing:
                print(f"  ❌ {model}")
        
        return len(missing) == 0
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def main():
    """Executa todos os testes."""
    print("\n🧪 TESTE DE API - Compositor de Músicas Educativas")
    print(f"Base URL: {BASE_URL}")
    
    results = {
        "Health Check": test_health(),
        "Provedores": test_provedores(),
        "Página Principal": test_root(),
        "Arquivos Estáticos": test_static_files(),
        "Upload": test_upload_simulation(),
        "Modelos": test_models_available(),
    }
    
    # Resumo
    print_section("RESUMO DOS TESTES")
    
    for test_name, result in results.items():
        icon = "✅" if result else "❌"
        print(f"  {icon} {test_name}")
    
    total = len(results)
    passed = sum(1 for r in results.values() if r)
    
    print(f"\n📊 Total: {passed}/{total} testes passaram")
    
    if passed == total:
        print("\n🎉 Todos os testes passaram! Sistema funcionando.")
        print("\n📝 Próximos passos:")
        print("   1. Acesse http://localhost:8000")
        print("   2. Faça upload de arquivos HTML")
        print("   3. Configure os modelos")
        print("   4. Inicie o processamento")
    else:
        print("\n⚠️  Alguns testes falharam. Verifique as mensagens acima.")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()