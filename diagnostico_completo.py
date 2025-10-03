#!/usr/bin/env python3
"""
Diagnóstico completo do sistema de monitoramento.
Execute: python diagnostico_completo.py
"""
import os
import sys
import json
import time
import subprocess
from pathlib import Path

def run_command(cmd):
    """Executa comando e retorna sucesso/falha."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Timeout"
    except Exception as e:
        return False, "", str(e)

def check_redis():
    """Verifica se Redis está rodando."""
    print("\n1️⃣ Verificando Redis...")
    
    # Tentar conexão Python
    try:
        import redis
        r = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), 
                       port=int(os.getenv("REDIS_PORT", 6379)))
        r.ping()
        print("   ✅ Redis está funcionando")
        
        # Testar pub/sub
        test_channel = "test:diagnostic"
        r.publish(test_channel, "test_message")
        print("   ✅ Pub/Sub funcionando")
        return True
    except ImportError:
        print("   ❌ Biblioteca redis não instalada")
        print("      Execute: pip install redis")
        return False
    except Exception as e:
        print(f"   ❌ Redis não está rodando: {e}")
        print("\n   Soluções:")
        print("   • Docker: docker-compose up -d redis")
        print("   • WSL: wsl -e sudo service redis-server start")
        print("   • Windows: Instale e inicie o Memurai")
        return False

def check_backend():
    """Verifica se o backend está rodando."""
    print("\n2️⃣ Verificando Backend...")
    
    try:
        import requests
        response = requests.get("http://localhost:8000/", timeout=3)
        if response.status_code == 200:
            print("   ✅ Backend está rodando na porta 8000")
            return True
    except:
        pass
    
    print("   ❌ Backend não está respondendo")
    print("\n   Solução:")
    print("   • Execute: python backend/main.py")
    return False

def check_celery():
    """Verifica se o Celery worker está rodando."""
    print("\n3️⃣ Verificando Celery Worker...")
    
    # Verificar via Docker
    success, stdout, _ = run_command("docker-compose ps worker")
    if success and "Up" in stdout:
        print("   ✅ Celery Worker rodando via Docker")
        return True
    
    # Verificar processo local
    success, stdout, _ = run_command("tasklist | findstr celery")
    if success and "celery" in stdout.lower():
        print("   ✅ Celery Worker rodando localmente")
        return True
    
    print("   ❌ Celery Worker não está rodando")
    print("\n   Soluções:")
    print("   • Docker: docker-compose up -d worker")
    print("   • Local: celery -A backend.celery_worker:celery_app worker --loglevel=info --pool=solo")
    return False

def test_full_flow():
    """Testa o fluxo completo de mensagens."""
    print("\n4️⃣ Testando fluxo de mensagens...")
    
    try:
        import redis
        import json
        import uuid
        
        r = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"),
                       port=int(os.getenv("REDIS_PORT", 6379)),
                       decode_responses=True)
        
        # Simular uma execução
        execucao_id = f"test_{uuid.uuid4().hex[:8]}"
        channel = f"execucao_status:{execucao_id}"
        
        # Publicar mensagem de teste
        test_message = {
            "type": "file_progress",
            "arquivo": "teste.html",
            "etapa_atual": "Teste de diagnóstico",
            "progresso_percentual": 50
        }
        
        r.publish(channel, json.dumps(test_message))
        print(f"   ✅ Mensagem publicada no canal: {channel}")
        
        # Verificar se mensagem foi salva
        key = f"execucao:{execucao_id}"
        status_data = {"test": "data", "timestamp": time.time()}
        r.hset(key, mapping={"status": json.dumps(status_data)})
        
        recovered = r.hget(key, "status")
        if recovered:
            print("   ✅ Persistência de dados funcionando")
            r.delete(key)  # Limpar
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erro no fluxo: {e}")
        return False

def check_frontend_sse():
    """Verifica configuração SSE do frontend."""
    print("\n5️⃣ Verificando Frontend SSE...")
    
    monitoring_path = Path("frontend/templates/monitoring.html")
    if not monitoring_path.exists():
        print("   ❌ Arquivo monitoring.html não encontrado")
        return False
    
    content = monitoring_path.read_text()
    
    checks = {
        "HTMX presente": "htmx.org" in content,
        "SSE extension": "sse.js" in content or "hx-ext=\"sse\"" in content,
        "EventSource": "EventSource" in content or "sse-connect" in content,
        "Stream endpoint": "/api/execucoes/" in content and "/stream" in content
    }
    
    all_ok = True
    for check, result in checks.items():
        if result:
            print(f"   ✅ {check}")
        else:
            print(f"   ❌ {check}")
            all_ok = False
    
    if not all_ok:
        print("\n   Solução: Use o arquivo monitoring_fixed.html fornecido")
    
    return all_ok

def main():
    print("=" * 60)
    print("🔍 DIAGNÓSTICO COMPLETO - Sistema de Monitoramento")
    print("=" * 60)
    
    # Carregar .env
    if Path(".env").exists():
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Arquivo .env carregado")
    
    # Executar verificações
    results = {
        "Redis": check_redis(),
        "Backend": check_backend(),
        "Celery": check_celery(),
        "Fluxo": False,  # Será testado apenas se os anteriores funcionarem
        "Frontend": check_frontend_sse()
    }
    
    # Testar fluxo apenas se componentes básicos estiverem OK
    if results["Redis"] and results["Backend"]:
        results["Fluxo"] = test_full_flow()
    else:
        print("\n4️⃣ Testando fluxo de mensagens...")
        print("   ⏭️  Pulado (componentes básicos não estão funcionando)")
    
    # Resumo
    print("\n" + "=" * 60)
    print("📊 RESUMO DO DIAGNÓSTICO")
    print("=" * 60)
    
    for component, status in results.items():
        icon = "✅" if status else "❌"
        print(f"{icon} {component}")
    
    all_ok = all(results.values())
    
    print("\n" + "=" * 60)
    if all_ok:
        print("✅ SISTEMA FUNCIONANDO PERFEITAMENTE!")
        print("\nO monitoramento deve funcionar corretamente.")
        print("Acesse: http://localhost:8000")
    else:
        print("⚠️  PROBLEMAS DETECTADOS")
        print("\nRecomendação: Use Docker para simplicificar:")
        print("1. Instale Docker Desktop")
        print("2. Execute: .\\start-with-docker.ps1")
        print("3. Acesse: http://localhost:8000")
        
        print("\nOu corrija os componentes marcados com ❌ acima")
    
    print("=" * 60)

if __name__ == "__main__":
    main()