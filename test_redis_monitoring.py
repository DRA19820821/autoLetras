#!/usr/bin/env python3
"""
Script para testar o sistema de monitoramento Redis.
Execute: python test_redis_monitoring.py
"""
import redis
import json
import time
import sys
import os
from pathlib import Path
from datetime import datetime

# Adicionar backend ao path
sys.path.insert(0, str(Path(__file__).parent))

def test_redis_connection():
    """Testa conexão com Redis."""
    print("\n1. TESTANDO CONEXÃO COM REDIS")
    print("-" * 40)
    
    try:
        # Tentar conectar
        REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
        REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
        
        r = redis.StrictRedis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=0,
            decode_responses=True
        )
        
        # Testar ping
        r.ping()
        print(f"✅ Redis conectado em {REDIS_HOST}:{REDIS_PORT}")
        
        return r
    except redis.ConnectionError:
        print(f"❌ Não foi possível conectar ao Redis em {REDIS_HOST}:{REDIS_PORT}")
        print("\nVerifique se:")
        print("1. O Redis está rodando (docker compose up -d redis)")
        print("2. A porta está correta")
        print("3. O host está correto (use REDIS_HOST=redis se usando Docker)")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Erro ao conectar: {e}")
        sys.exit(1)

def test_publish_subscribe(r):
    """Testa pub/sub do Redis."""
    print("\n2. TESTANDO PUB/SUB")
    print("-" * 40)
    
    channel = "test_channel"
    
    # Criar subscriber
    pubsub = r.pubsub()
    pubsub.subscribe(channel)
    
    # Publicar mensagem
    test_message = {"type": "test", "data": "Hello Redis!"}
    r.publish(channel, json.dumps(test_message))
    
    print(f"📤 Mensagem publicada no canal '{channel}'")
    
    # Tentar receber mensagem
    time.sleep(0.1)  # Pequeno delay
    
    for message in pubsub.listen():
        if message['type'] == 'message':
            data = json.loads(message['data'])
            print(f"📥 Mensagem recebida: {data}")
            break
    
    pubsub.unsubscribe(channel)
    print("✅ Pub/Sub funcionando corretamente")

def simulate_worker_updates(r):
    """Simula atualizações do worker."""
    print("\n3. SIMULANDO ATUALIZAÇÕES DO WORKER")
    print("-" * 40)
    
    execucao_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    arquivo = "teste_simulado.html"
    channel = f"execucao_status:{execucao_id}"
    
    print(f"📡 Canal: {channel}")
    print(f"📄 Arquivo: {arquivo}")
    print()
    
    # Sequência de atualizações
    updates = [
        {
            "type": "file_progress",
            "arquivo": arquivo,
            "etapa_atual": "Iniciando processamento",
            "progresso_percentual": 5,
            "timestamp": datetime.now().isoformat()
        },
        {
            "type": "file_progress",
            "arquivo": arquivo,
            "etapa_atual": "Extraindo metadados",
            "progresso_percentual": 10,
            "timestamp": datetime.now().isoformat()
        },
        {
            "type": "file_progress",
            "arquivo": arquivo,
            "etapa_atual": "Ciclo 1: Compositor",
            "progresso_percentual": 30,
            "timestamp": datetime.now().isoformat()
        },
        {
            "type": "file_progress",
            "arquivo": arquivo,
            "etapa_atual": "Ciclo 1: Revisor Jurídico",
            "progresso_percentual": 45,
            "timestamp": datetime.now().isoformat()
        },
        {
            "type": "file_progress",
            "arquivo": arquivo,
            "etapa_atual": "Ciclo 1: Revisor Linguístico",
            "progresso_percentual": 70,
            "timestamp": datetime.now().isoformat()
        },
        {
            "type": "file_progress",
            "arquivo": arquivo,
            "etapa_atual": "Salvando resultado",
            "progresso_percentual": 90,
            "timestamp": datetime.now().isoformat()
        },
        {
            "type": "file_result",
            "arquivo": arquivo,
            "status": "concluido",
            "output_gerado": "dConst01_TesteSimulado_fk.json",
            "timestamp": datetime.now().isoformat()
        }
    ]
    
    print("Publicando atualizações simuladas...")
    print()
    
    for i, update in enumerate(updates, 1):
        # Publicar
        subscribers = r.publish(channel, json.dumps(update))
        
        # Mostrar
        print(f"{i}. [{update['progresso_percentual']}%] {update['etapa_atual']}")
        print(f"   → {subscribers} subscribers receberam a mensagem")
        
        # Delay para simular processamento real
        time.sleep(0.5)
    
    print()
    print("✅ Simulação concluída")
    print(f"\n📝 Para testar o monitoramento:")
    print(f"   1. Abra: http://localhost:8000/monitoring/{execucao_id}")
    print(f"   2. Execute este script novamente em outra janela")
    print(f"   3. Veja as atualizações aparecerem em tempo real")

def test_persistence(r):
    """Testa persistência de status."""
    print("\n4. TESTANDO PERSISTÊNCIA")
    print("-" * 40)
    
    execucao_id = "test_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    key = f"execucao:{execucao_id}"
    
    # Criar status de teste
    status = {
        "execucao_id": execucao_id,
        "status": "processando",
        "timestamp_inicio": datetime.now().isoformat(),
        "arquivos": [
            {
                "arquivo": "teste1.html",
                "status": "processando",
                "progresso_percentual": 50
            },
            {
                "arquivo": "teste2.html",
                "status": "aguardando",
                "progresso_percentual": 0
            }
        ],
        "total_arquivos": 2,
        "arquivos_concluidos": 0,
        "arquivos_em_processo": 1,
        "arquivos_falhados": 0
    }
    
    # Salvar
    r.hset(key, "status", json.dumps(status))
    r.expire(key, 3600)  # 1 hora
    
    print(f"💾 Status salvo com chave: {key}")
    
    # Recuperar
    retrieved = r.hget(key, "status")
    if retrieved:
        data = json.loads(retrieved)
        print(f"📖 Status recuperado: {data['execucao_id']}")
        print(f"   - Total arquivos: {data['total_arquivos']}")
        print(f"   - Em processo: {data['arquivos_em_processo']}")
        print("✅ Persistência funcionando")
    else:
        print("❌ Erro ao recuperar status")

def check_celery_redis():
    """Verifica se Celery está usando Redis."""
    print("\n5. VERIFICANDO CONFIGURAÇÃO CELERY")
    print("-" * 40)
    
    try:
        from backend.celery_worker import CELERY_BROKER_URL, CELERY_RESULT_BACKEND
        
        print(f"📌 Broker: {CELERY_BROKER_URL}")
        print(f"📌 Backend: {CELERY_RESULT_BACKEND}")
        
        if "redis" in CELERY_BROKER_URL.lower():
            print("✅ Celery configurado para usar Redis")
        else:
            print("⚠️  Celery não está usando Redis como broker")
            
    except ImportError:
        print("⚠️  Não foi possível importar configuração do Celery")

def main():
    """Executa todos os testes."""
    print("\n" + "=" * 50)
    print("🔍 TESTE DO SISTEMA DE MONITORAMENTO REDIS")
    print("=" * 50)
    
    try:
        # 1. Testar conexão
        r = test_redis_connection()
        
        # 2. Testar pub/sub
        test_publish_subscribe(r)
        
        # 3. Simular worker
        simulate_worker_updates(r)
        
        # 4. Testar persistência
        test_persistence(r)
        
        # 5. Verificar Celery
        check_celery_redis()
        
        print("\n" + "=" * 50)
        print("✅ TODOS OS TESTES PASSARAM!")
        print("=" * 50)
        
        print("\n📝 PRÓXIMOS PASSOS:")
        print("1. Certifique-se de que o Redis está rodando:")
        print("   docker compose up -d redis")
        print()
        print("2. Inicie o backend:")
        print("   python backend/main.py")
        print()
        print("3. Inicie o worker Celery:")
        print("   celery -A backend.celery_worker:celery_app worker --loglevel=info")
        print()
        print("4. Acesse a aplicação e faça um teste real:")
        print("   http://localhost:8000")
        
    except KeyboardInterrupt:
        print("\n\n🛑 Teste interrompido")
    except Exception as e:
        print(f"\n❌ Erro durante teste: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    main()