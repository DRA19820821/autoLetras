#!/usr/bin/env python3
"""
Diagnóstico completo do problema de monitoramento.
Execute ENQUANTO um processamento está rodando.
"""
import os
import sys
import redis
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def check_redis_connection():
    """Verifica conexão Redis."""
    print("\n" + "="*60)
    print("1. TESTE DE CONEXÃO REDIS")
    print("="*60)
    
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    
    try:
        r = redis.StrictRedis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=0,
            decode_responses=True
        )
        r.ping()
        print(f"✓ Redis conectado em {REDIS_HOST}:{REDIS_PORT}")
        return r
    except Exception as e:
        print(f"✗ ERRO: {e}")
        return None

def check_worker_import():
    """Verifica se o worker consegue importar redis_client."""
    print("\n" + "="*60)
    print("2. TESTE DE IMPORTAÇÃO NO WORKER")
    print("="*60)
    
    try:
        from backend.app.redis_client import publish_status_update, redis_conn
        print("✓ publish_status_update importado")
        print("✓ redis_conn importado")
        
        # Testar conexão do redis_conn
        redis_conn.ping()
        print("✓ redis_conn funcional")
        
        return True
    except Exception as e:
        print(f"✗ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_active_executions(r):
    """Lista execuções ativas."""
    print("\n" + "="*60)
    print("3. EXECUÇÕES ATIVAS")
    print("="*60)
    
    # Procurar por chaves de execução
    keys = r.keys("execucao:*")
    
    if not keys:
        print("✗ Nenhuma execução encontrada no Redis")
        print("  Isso indica que o worker NÃO está salvando status")
        return None
    
    print(f"✓ Encontradas {len(keys)} execuções:")
    for key in keys:
        status_json = r.hget(key, "status")
        if status_json:
            status = json.loads(status_json)
            print(f"  - {key}: {status.get('status', 'unknown')}")
    
    return keys[0] if keys else None

def listen_to_channel(r, execucao_id):
    """Escuta canal específico por 10 segundos."""
    print("\n" + "="*60)
    print(f"4. ESCUTANDO CANAL (10 segundos)")
    print("="*60)
    
    if not execucao_id:
        print("✗ Nenhum execucao_id fornecido")
        return
    
    channel = f"execucao_status:{execucao_id}"
    print(f"Canal: {channel}")
    
    pubsub = r.pubsub()
    pubsub.subscribe(channel)
    
    print("Aguardando mensagens... (Ctrl+C para sair)")
    
    import time
    timeout = time.time() + 10
    message_count = 0
    
    try:
        for message in pubsub.listen():
            if time.time() > timeout:
                break
            
            if message['type'] == 'message':
                message_count += 1
                data = json.loads(message['data'])
                print(f"\n✓ MENSAGEM RECEBIDA #{message_count}:")
                print(f"  Tipo: {data.get('type')}")
                print(f"  Arquivo: {data.get('arquivo')}")
                print(f"  Etapa: {data.get('etapa_atual')}")
                print(f"  Progresso: {data.get('progresso_percentual')}%")
    except KeyboardInterrupt:
        pass
    
    pubsub.unsubscribe(channel)
    
    if message_count == 0:
        print("\n✗ NENHUMA MENSAGEM RECEBIDA!")
        print("  PROBLEMA: O worker NÃO está publicando mensagens")
        print("\n  CAUSA PROVÁVEL:")
        print("  1. A função update_status() não está sendo chamada")
        print("  2. A função publish_status_update() está falhando silenciosamente")
        print("  3. O worker está usando Redis diferente do backend")
    else:
        print(f"\n✓ Recebidas {message_count} mensagens")

def test_manual_publish(r):
    """Testa publicação manual."""
    print("\n" + "="*60)
    print("5. TESTE DE PUBLICAÇÃO MANUAL")
    print("="*60)
    
    execucao_id = "test_" + datetime.now().strftime("%H%M%S")
    channel = f"execucao_status:{execucao_id}"
    
    message = {
        "type": "file_progress",
        "arquivo": "teste_manual.html",
        "etapa_atual": "Teste manual de publicação",
        "progresso_percentual": 50,
        "timestamp": datetime.now().isoformat()
    }
    
    num_subs = r.publish(channel, json.dumps(message))
    print(f"✓ Mensagem publicada")
    print(f"  Canal: {channel}")
    print(f"  Subscribers: {num_subs}")
    
    if num_subs == 0:
        print("\n⚠ ATENÇÃO: 0 subscribers!")
        print("  Isso significa que nenhum cliente SSE está escutando")
        print("  Mas isso é normal se não há navegador aberto")

def check_celery_logs():
    """Verifica se há logs do celery."""
    print("\n" + "="*60)
    print("6. VERIFICANDO LOGS DO CELERY")
    print("="*60)
    
    log_paths = [
        Path("data/logs/celery.log"),
        Path("/app/data/logs/celery.log"),
    ]
    
    for log_path in log_paths:
        if log_path.exists():
            print(f"✓ Log encontrado: {log_path}")
            
            # Ler últimas 20 linhas
            with open(log_path, 'r') as f:
                lines = f.readlines()
                last_lines = lines[-20:] if len(lines) > 20 else lines
            
            # Procurar por status_update
            has_update = any("status_update" in line.lower() for line in last_lines)
            
            if has_update:
                print("✓ Encontrado 'status_update' nos logs")
                for line in last_lines:
                    if "status_update" in line.lower():
                        print(f"  {line.strip()[:100]}")
            else:
                print("✗ NÃO encontrado 'status_update' nos logs")
                print("  Isso confirma que update_status() não está sendo chamado")
            
            return
    
    print("✗ Nenhum arquivo de log encontrado")
    print("  Verifique se o worker está rodando")

def main():
    print("="*60)
    print("DIAGNÓSTICO COMPLETO - MONITORAMENTO SSE")
    print("="*60)
    print("\nINSTRUÇÕES:")
    print("1. Inicie um processamento no navegador")
    print("2. Execute este script ENQUANTO processa")
    print("3. Analise os resultados")
    print()
    
    input("Pressione ENTER quando o processamento estiver rodando...")
    
    # Carregar .env
    if Path(".env").exists():
        from dotenv import load_dotenv
        load_dotenv()
    
    # 1. Testar Redis
    r = check_redis_connection()
    if not r:
        print("\n✗ FALHA CRÍTICA: Redis não está acessível")
        return
    
    # 2. Testar importações
    if not check_worker_import():
        print("\n✗ FALHA CRÍTICA: Worker não consegue importar redis_client")
        return
    
    # 3. Verificar execuções ativas
    exec_key = check_active_executions(r)
    
    # 4. Se houver execução, escutar canal
    if exec_key:
        execucao_id = exec_key.replace("execucao:", "")
        listen_to_channel(r, execucao_id)
    else:
        print("\n⚠ Nenhuma execução ativa - teste manual:")
        test_manual_publish(r)
    
    # 5. Verificar logs
    check_celery_logs()
    
    # Resumo
    print("\n" + "="*60)
    print("RESUMO E PRÓXIMOS PASSOS")
    print("="*60)
    
    print("\nSe você viu:")
    print("  ✗ 'NENHUMA MENSAGEM RECEBIDA'")
    print("  ✗ 'NÃO encontrado status_update nos logs'")
    print("\nENTÃO:")
    print("  → O worker NÃO está chamando update_status()")
    print("  → A correção do celery_worker.py NÃO foi aplicada")
    print("\nSOLUÇÃO:")
    print("  1. Pare os containers: docker compose down")
    print("  2. Aplique a correção do celery_worker.py")
    print("  3. Rebuild: docker compose build --no-cache worker")
    print("  4. Inicie: docker compose up -d")
    print("  5. Execute este script novamente")

if __name__ == "__main__":
    main()