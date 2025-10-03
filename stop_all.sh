#!/bin/bash

# Script para parar o sistema completo
# Execute: ./stop_all.sh

echo "🛑 Parando Sistema do Compositor de Músicas Educativas"
echo "======================================================"
echo ""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 1. Parar FastAPI
echo "1. Parando servidor FastAPI..."
if [ -f .fastapi.pid ]; then
    PID=$(cat .fastapi.pid)
    if kill -0 $PID 2>/dev/null; then
        kill $PID
        echo -e "   ${GREEN}✓${NC} Servidor parado (PID: $PID)"
    else
        echo -e "   ${YELLOW}⚠${NC}  Processo não encontrado"
    fi
    rm .fastapi.pid
else
    # Tentar encontrar pelo nome
    PIDS=$(pgrep -f "python.*main.py")
    if [ ! -z "$PIDS" ]; then
        kill $PIDS
        echo -e "   ${GREEN}✓${NC} Servidor(es) parado(s)"
    else
        echo -e "   ${YELLOW}⚠${NC}  Nenhum servidor FastAPI rodando"
    fi
fi
echo ""

# 2. Parar Celery Worker
echo "2. Parando Celery Worker..."
if [ -f .celery.pid ]; then
    PID=$(cat .celery.pid)
    if kill -0 $PID 2>/dev/null; then
        kill $PID
        echo -e "   ${GREEN}✓${NC} Worker parado (PID: $PID)"
    else
        echo -e "   ${YELLOW}⚠${NC}  Processo não encontrado"
    fi
    rm .celery.pid
else
    # Tentar encontrar pelo nome
    PIDS=$(pgrep -f "celery.*backend.celery_worker")
    if [ ! -z "$PIDS" ]; then
        kill $PIDS
        echo -e "   ${GREEN}✓${NC} Worker(s) parado(s)"
    else
        echo -e "   ${YELLOW}⚠${NC}  Nenhum Celery Worker rodando"
    fi
fi
echo ""

# 3. Parar Redis (Docker)
echo "3. Parando Redis..."
docker compose stop redis 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "   ${GREEN}✓${NC} Redis parado"
else
    echo -e "   ${YELLOW}⚠${NC}  Redis não estava rodando ou erro ao parar"
fi
echo ""

# 4. Limpar processos órfãos
echo "4. Verificando processos órfãos..."

# Verificar uvicorn
UVICORN_PIDS=$(pgrep -f "uvicorn.*backend.main")
if [ ! -z "$UVICORN_PIDS" ]; then
    kill $UVICORN_PIDS
    echo -e "   ${GREEN}✓${NC} Processos uvicorn parados"
fi

# Verificar Python na porta 8000
PYTHON_8000=$(lsof -ti:8000)
if [ ! -z "$PYTHON_8000" ]; then
    kill $PYTHON_8000
    echo -e "   ${GREEN}✓${NC} Processo na porta 8000 parado"
fi

echo -e "   ${GREEN}✓${NC} Limpeza concluída"
echo ""

# Resultado final
echo "======================================================"
echo -e "${GREEN}✅ SISTEMA PARADO${NC}"
echo "======================================================"
echo ""
echo "Para reiniciar o sistema:"
echo "   ./start_all.sh"
echo ""