"""Aplicação FastAPI principal para o AutoLetras.

Este módulo inicializa a aplicação FastAPI, configura middlewares
necessários (como CORS) e inclui os roteadores definidos em
`backend.app.api`. Ele também define um ponto de entrada para
execução via Uvicorn. A adição deste módulo permite que o
componente de monitoramento via Server‑Sent Events funcione
corretamente quando executado com `uvicorn backend.app.main:app`.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import router as api_router

# Criar instância da aplicação
app = FastAPI(title="AutoLetras Backend", version="1.0.0")

# Configurar CORS (libera todas as origens, métodos e cabeçalhos). Em
# ambiente de produção, ajuste conforme necessário.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar as rotas da API, incluindo streaming
app.include_router(api_router)


@app.get("/health", summary="Verifica se a API está ativa")
async def health_check():
    """Endpoint simples de verificação de saúde.

    Retorna uma mensagem indicando que a API está em execução. Pode
    ser utilizado por orquestradores ou load balancers para checar
    disponibilidade.
    """
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=False)