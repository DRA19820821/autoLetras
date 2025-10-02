import os
import redis
import json

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# Pool de conexão para reutilização
redis_pool = redis.ConnectionPool(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

def get_redis_connection():
    """Retorna uma conexão Redis do pool."""
    return redis.Redis(connection_pool=redis_pool)

redis_conn = get_redis_connection()

def publish_status_update(execucao_id: str, message: dict):
    """Publica uma atualização de status no canal Redis."""
    channel = f"execucao_status:{execucao_id}"
    redis_conn.publish(channel, json.dumps(message))

def set_execution_status(execucao_id: str, status_data: dict):
    """Salva o status completo de uma execução no Redis."""
    key = f"execucao:{execucao_id}"
    # Armazena como um hash para permitir atualizações de campos individuais se necessário
    redis_conn.hset(key, mapping={"status": json.dumps(status_data)})
    # Define um tempo de expiração para a chave (e.g., 24 horas)
    redis_conn.expire(key, 86400)

def get_execution_status(execucao_id: str) -> dict | None:
    """Recupera o status de uma execução do Redis."""
    key = f"execucao:{execucao_id}"
    status_json = redis_conn.hget(key, "status")
    if status_json:
        return json.loads(status_json)
    return None