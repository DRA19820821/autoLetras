"""Pacote de rotas da API.

Este pacote agrupa os roteadores relacionados à API REST e aos
endpoints de streaming. Novos módulos devem registrar seus roteadores
aqui para que possam ser incluídos na aplicação FastAPI principal.
"""

from fastapi import APIRouter
from . import monitoring

router = APIRouter()

# Inclui o roteador de monitoramento
router.include_router(monitoring.router)