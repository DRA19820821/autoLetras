"""Endpoints para acompanhamento em tempo real de execuções.

Este módulo define um endpoint de streaming (Server‑Sent Events) que
permite aos clientes assinar atualizações de progresso e outros
eventos relacionados a uma execução específica. O Celery worker e os
diversos nós do workflow publicam mensagens no Redis através das
funções `publish_status_update` e `publish_status_update_async`. O
endpoint implementado aqui se inscreve no canal Redis associado ao
`execucao_id` e encaminha as mensagens ao cliente via SSE.

Para utilizar, a aplicação FastAPI deve incluir este roteador. O
frontend pode então abrir uma conexão `EventSource` com o caminho
`/api/execucoes/{execucao_id}/stream` e receber atualizações em tempo
real.
"""

from __future__ import annotations

import json
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.app.redis_client import async_redis_conn

router = APIRouter()


async def _redis_event_stream(execucao_id: str) -> AsyncGenerator[str, None]:
    """Gera uma sequência de eventos SSE a partir de mensagens Redis.

    Para cada mensagem publicada no canal `status_updates_{execucao_id}`,
    esta função produz uma string no formato SSE (`data: <json>\n\n`).

    Args:
        execucao_id: Identificador da execução cujos eventos devem ser
            encaminhados.

    Yields:
        Strings formatadas de acordo com o protocolo SSE contendo os
        dados da mensagem em JSON.
    """
    if async_redis_conn is None:
        # Se a conexão assíncrona não estiver disponível, o streaming
        # não funcionará. Levantamos uma exceção para informar o
        # cliente.
        raise HTTPException(status_code=500, detail="Redis async não configurado")
    channel_name = f"status_updates_{execucao_id}"
    pubsub = async_redis_conn.pubsub()
    await pubsub.subscribe(channel_name)
    try:
        # Indicar início da transmissão
        yield "data: {\"message\": \"stream-start\"}\n\n"
        async for message in pubsub.listen():
            # As mensagens podem ter tipos diferentes (subscribe,
            # message, etc.). Processamos somente as de tipo 'message'.
            if message.get("type") != "message":
                continue
            data = message.get("data")
            if data is None:
                continue
            # Os dados podem ser bytes ou string JSON. Garante
            # decodificação adequada.
            if isinstance(data, bytes):
                payload = data.decode("utf-8", errors="ignore")
            else:
                payload = str(data)
            # Verifica se o payload é JSON válido; caso contrário,
            # serializa como texto bruto.
            try:
                # Tenta carregar para garantir que seja JSON
                json.loads(payload)
                json_payload = payload
            except Exception:
                json_payload = json.dumps({"message": payload})
            yield f"data: {json_payload}\n\n"
    finally:
        # Cancelar inscrição e fechar pubsub
        try:
            await pubsub.unsubscribe(channel_name)
            await pubsub.close()
        except Exception:
            pass


@router.get("/api/execucoes/{execucao_id}/stream", summary="Stream de status da execução")
async def stream_execucao(execucao_id: str):
    """Endpoint SSE que envia atualizações de status para uma execução.

    Clients podem se conectar a este endpoint usando EventSource para
    receber mensagens de progresso em tempo real. Cada mensagem
    enviada pelo backend (worker ou nós) é encaminhada como um
    `data: <json>` no protocolo SSE.

    Args:
        execucao_id: Identificador da execução a ser monitorada.

    Returns:
        StreamingResponse com conteúdo do tipo `text/event-stream`.
    """
    event_generator = _redis_event_stream(execucao_id)
    return StreamingResponse(event_generator, media_type="text/event-stream")