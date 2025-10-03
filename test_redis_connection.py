#!/usr/bin/env python3
"""
Script para verificar se o Redis está funcionando corretamente.
Execute: python test_redis_connection.py
"""
import os
import sys
from pathlib import Path

def test_redis():
    """Testa conexão com Redis e funcionalidades básicas."""
    
    print("🔍 Testando conexão com Redis")
    print("=" * 60)
    
    # Verificar variáveis de ambiente
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    
    print(f"Host: {redis_host}")
    print(f"Port: {redis_port}")
    print()
    
    try:
        import redis
    except ImportError:
        print("❌ Biblioteca redis-py não instalada")
        print("   Execute: pip install redis")
        return False
    
    # Teste 1: Conexão básica
    print("1. Testando conexão...")
    try:
        r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        r.ping()
        print("   ✅ Conexão estabelecida")
    except redis.ConnectionError:
        print("   ❌ Não foi possível conectar ao Redis")
        print()
        print("Possíveis soluções:")
        print("1. Se usando Docker: docker-compose up -d redis")
        print("2. Se local no WSL: sudo service redis-server start")
        print("3. Se usando Memurai: verifique se o serviço está rodando")
        return False
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False
    
    # Teste 2: Escrita e leitura
    print("2. Testando escrita/leitura...")
    try:
        test_key = "test:autoletras"
        test_value = "funcionando"
        
        r.set(test_key, test_value)
        resultado = r.get(test_key)
        
        if resultado == test_value:
            print("   ✅ Escrita/leitura OK")
        else:
            print("   ❌ Valor lido diferente do escrito")
            return False
        
        r.delete(test_key)
        
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False
    
    # Teste 3: Pub/Sub
    print("3. Testando Pub/Sub...")
    try:
        import json
        import threading
        import time
        
        received_message = None
        
        def subscriber():
            nonlocal received_message
            pubsub = r.pubsub()
            pubsub.subscribe('test:channel')
            
            for message in pubsub.listen():
                if message['type'] == 'message':
                    received_message = message['data']
                    break
        
        # Iniciar subscriber em thread separada
        sub_thread = threading.Thread(target=subscriber, daemon=True)
        sub_thread.start()
        
        # Aguardar subscriber estar pronto
        time.sleep(0.5)
        
        # Publicar mensagem
        test_message = "teste_pubsub"
        r.publish('test:channel', test_message)
        
        # Aguardar recebimento
        time.sleep(0.5)
        
        if received_message == test_message:
            print("   ✅ Pub/Sub funcionando")
        else:
            print("   ❌ Pub/Sub não funcionou")
            return False
            
    except Exception as e:
        print(f"   ❌ Erro no Pub/Sub: {e}")
        return False
    
    # Teste 4: Simular status de execução (como o app faz)
    print("4. Testando salvamento de status...")
    try:
        execucao_id = "test_123"
        status_data = {
            "execucao_id": execucao_id,
            "status": "processando",
            "arquivos": ["teste1.html", "teste2.html"],
            "progresso": 50
        }
        
        # Salvar status
        key = f"execucao:{execucao_id}"
        r.hset(key, mapping={"status": json.dumps(status_data)})
        r.expire(key, 60)  # Expira em 60 segundos
        
        # Recuperar status
        status_json = r.hget(key, "status")
        if status_json:
            recovered = json.loads(status_json)
            if recovered["execucao_id"] == execucao_id:
                print("   ✅ Salvamento de status OK")
            else:
                print("   ❌ Status recuperado incorreto")
                return False
        else:
            print("   ❌ Não foi possível recuperar status")
            return False
        
        # Limpar
        r.delete(key)
        
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False
    
    print()
    print("=" * 60)
    print("✅ REDIS FUNCIONANDO PERFEITAMENTE!")
    print("=" * 60)
    return True

def check_celery():
    """Verifica se o Celery está configurado."""
    print("\n🔍 Verificando Celery")
    print("=" * 60)
    
    try:
        import celery
        print("✅ Celery instalado")
        
        # Verificar se o worker pode ser importado
        try:
            from backend.celery_worker import celery_app
            print("✅ Worker pode ser importado")
        except ImportError as e:
            print(f"⚠️  Erro ao importar worker: {e}")
            print("   Certifique-se de executar do diretório raiz do projeto")
        
    except ImportError:
        print("❌ Celery não instalado")
        print("   Execute: pip install celery")
        return False
    
    return True

def main():
    """Função principal."""
    print("\n🧪 TESTE DE COMPONENTES DE MENSAGERIA")
    print("=" * 60)
    print()
    
    # Carregar .env se existir
    if Path(".env").exists():
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Arquivo .env carregado")
    else:
        print("⚠️  Arquivo .env não encontrado")
    
    print()
    
    # Testar Redis
    redis_ok = test_redis()
    
    # Testar Celery
    celery_ok = check_celery()
    
    # Resumo
    print("\n" + "=" * 60)
    print("📊 RESUMO")
    print("=" * 60)
    
    if redis_ok and celery_ok:
        print("✅ Tudo funcionando! O monitoramento deve funcionar.")
        print()
        print("Se ainda não funcionar, verifique:")
        print("1. Se o Celery worker está rodando")
        print("2. Se o backend está rodando")
        print("3. Os logs para erros: docker-compose logs -f")
    else:
        print("❌ Problemas detectados. Corrija-os antes de continuar.")
        print()
        print("Para usar com Docker (mais fácil):")
        print("1. Instale Docker Desktop")
        print("2. Execute: docker-compose up -d")
        print("3. Acesse: http://localhost:8000")
    
    print("=" * 60)

if __name__ == "__main__":
    main()