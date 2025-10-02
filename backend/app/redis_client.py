import os
import redis
import json
from datetime import datetime

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
    redis_conn.publish(channel, json.dumps(message, default=str))

def set_execution_status(execucao_id: str, status_data: dict):
    """Salva o status completo de uma execução no Redis."""
    key = f"execucao:{execucao_id}"
    # Converter datetime para string ISO antes de serializar
    serializable_data = _make_json_serializable(status_data)
    redis_conn.hset(key, mapping={"status": json.dumps(serializable_data, default=str)})
    # Define um tempo de expiração para a chave (e.g., 24 horas)
    redis_conn.expire(key, 86400)

def get_execution_status(execucao_id: str) -> dict | None:
    """Recupera o status de uma execução do Redis."""
    key = f"execucao:{execucao_id}"
    status_json = redis_conn.hget(key, "status")
    if status_json:
        return json.loads(status_json)
    return None

def _make_json_serializable(obj):
    """
    Converte objetos não-serializáveis (como datetime) para formatos serializáveis.
    """
    if isinstance(obj, dict):
        return {key: _make_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_make_json_serializable(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    else:
        return obj