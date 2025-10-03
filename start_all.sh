#!/bin/bash

# Script para iniciar o sistema completo com monitoramento
# Execute: ./start_all.sh

echo "🎵 Compositor de Músicas Educativas - Iniciando Sistema Completo"
echo "================================================================"
echo ""

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Função para verificar se comando existe
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Função para verificar se porta está em uso
port_in_use() {
    lsof -i:$1 >/dev/null 2>&1
}

# Função para aguardar serviço
wait_for_service() {
    local service=$1
    local port=$2
    local max_attempts=30
    local attempt=1
    
    echo -n "⏳ Aguardando $service na porta $port..."
    
    while [ $attempt -le $max_attempts ]; do
        if port_in_use $port; then
            echo -e " ${GREEN}✓${NC}"
            return 0
        fi
        echo -n "."
        sleep 1
        ((attempt++))
    done
    
    echo -e " ${RED}✗${NC}"
    return 1
}

# 1. Verificar Docker
echo "1. Verificando Docker..."
if command_exists docker; then
    if docker info >/dev/null 2>&1; then
        echo -e "   ${GREEN}✓${NC} Docker está rodando"
    else
        echo -e "   ${RED}✗${NC} Docker não está rodando"
        echo "   Execute: sudo systemctl start docker (Linux) ou abra Docker Desktop"
        exit 1
    fi
else
    echo -e "   ${RED}✗${NC} Docker não instalado"
    echo "   Instale Docker: https://docs.docker.com/get-docker/"
    exit 1
fi
echo ""

# 2. Verificar docker-compose
echo "2. Verificando Docker Compose..."
if command_exists docker-compose || docker compose version >/dev/null 2>&1; then
    echo -e "   ${GREEN}✓${NC} Docker Compose disponível"
else
    echo -e "   ${RED}✗${NC} Docker Compose não encontrado"
    exit 1
fi
echo ""

# 3. Iniciar Redis via Docker
echo "3. Iniciando Redis..."
if port_in_use 6379; then
    echo -e "   ${YELLOW}⚠${NC}  Redis já está rodando na porta 6379"
else
    echo "   Iniciando container Redis..."
    docker compose up -d redis
    
    if wait_for_service "Redis" 6379; then
        echo -e "   ${GREEN}✓${NC} Redis iniciado com sucesso"
    else
        echo -e "   ${RED}✗${NC} Falha ao iniciar Redis"
        exit 1
    fi
fi
echo ""

# 4. Testar conexão Redis
echo "4. Testando conexão com Redis..."
docker compose exec -T redis redis-cli ping > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "   ${GREEN}✓${NC} Redis respondendo (PONG)"
else
    echo -e "   ${RED}✗${NC} Redis não está respondendo"
    echo "   Verifique os logs: docker compose logs redis"
    exit 1
fi
echo ""

# 5. Verificar virtual environment
echo "5. Verificando ambiente Python..."
if [ -d "venv" ] || [ -d ".venv" ]; then
    echo -e "   ${GREEN}✓${NC} Virtual environment encontrado"
    
    # Ativar venv
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    else
        source venv/bin/activate
    fi
    echo -e "   ${GREEN}✓${NC} Virtual environment ativado"
else
    echo -e "   ${RED}✗${NC} Virtual environment não encontrado"
    echo "   Execute: python -m venv .venv && source .venv/bin/activate"
    exit 1
fi
echo ""

# 6. Verificar .env
echo "6. Verificando configuração..."
if [ -f ".env" ]; then
    echo -e "   ${GREEN}✓${NC} Arquivo .env encontrado"
    
    # Verificar se tem pelo menos uma API key
    if grep -q "API_KEY=sk-\|API_KEY=.*[A-Za-z0-9]" .env; then
        echo -e "   ${GREEN}✓${NC} API keys configuradas"
    else
        echo -e "   ${YELLOW}⚠${NC}  Nenhuma API key parece estar configurada"
        echo "   Configure suas API keys no arquivo .env"
    fi
else
    echo -e "   ${RED}✗${NC} Arquivo .env não encontrado"
    echo "   Execute: cp .env.example .env"
    exit 1
fi
echo ""

# 7. Instalar dependências (se necessário)
echo "7. Verificando dependências Python..."
python -c "import fastapi, langchain, redis, celery" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "   ${GREEN}✓${NC} Dependências instaladas"
else
    echo -e "   ${YELLOW}⚠${NC}  Instalando dependências..."
    pip install -r requirements.txt
fi
echo ""

# 8. Criar arquivos __init__.py se necessário
echo "8. Verificando estrutura do projeto..."
if [ ! -f "backend/__init__.py" ]; then
    echo "   Criando arquivos __init__.py..."
    python criar_init_files.py
fi
echo -e "   ${GREEN}✓${NC} Estrutura OK"
echo ""

# 9. Iniciar Celery Worker
echo "9. Iniciando Celery Worker..."
if pgrep -f "celery.*backend.celery_worker" > /dev/null; then
    echo -e "   ${YELLOW}⚠${NC}  Celery Worker já está rodando"
else
    echo "   Iniciando Celery em background..."
    nohup celery -A backend.celery_worker:celery_app worker \
        --loglevel=info \
        --pool=solo \
        > data/logs/celery.log 2>&1 &
    
    CELERY_PID=$!
    sleep 2
    
    if kill -0 $CELERY_PID 2>/dev/null; then
        echo -e "   ${GREEN}✓${NC} Celery Worker iniciado (PID: $CELERY_PID)"
        echo $CELERY_PID > .celery.pid
    else
        echo -e "   ${RED}✗${NC} Falha ao iniciar Celery Worker"
        echo "   Verifique os logs: tail -f data/logs/celery.log"
        exit 1
    fi
fi
echo ""

# 10. Iniciar FastAPI
echo "10. Iniciando servidor FastAPI..."
if port_in_use 8000; then
    echo -e "   ${YELLOW}⚠${NC}  Servidor já está rodando na porta 8000"
else
    echo "   Iniciando servidor em background..."
    cd backend
    nohup python main.py > ../data/logs/fastapi.log 2>&1 &
    FASTAPI_PID=$!
    cd ..
    
    if wait_for_service "FastAPI" 8000; then
        echo -e "   ${GREEN}✓${NC} Servidor FastAPI iniciado (PID: $FASTAPI_PID)"
        echo $FASTAPI_PID > .fastapi.pid
    else
        echo -e "   ${RED}✗${NC} Falha ao iniciar servidor"
        echo "   Verifique os logs: tail -f data/logs/fastapi.log"
        exit 1
    fi
fi
echo ""

# 11. Testar sistema
echo "11. Testando sistema..."
sleep 2

# Testar endpoint de health
response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health)
if [ "$response" = "200" ]; then
    echo -e "   ${GREEN}✓${NC} API respondendo corretamente"
else
    echo -e "   ${YELLOW}⚠${NC}  API retornou código $response"
fi

# Testar Redis via API
python test_redis_monitoring.py > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "   ${GREEN}✓${NC} Sistema de monitoramento funcionando"
else
    echo -e "   ${YELLOW}⚠${NC}  Verifique o sistema de monitoramento"
fi
echo ""

# Resultado final
echo "================================================================"
echo -e "${GREEN}✅ SISTEMA INICIADO COM SUCESSO!${NC}"
echo "================================================================"
echo ""
echo "📍 Acesse a aplicação em: http://localhost:8000"
echo ""
echo "📊 Monitoramento:"
echo "   - Logs FastAPI: tail -f data/logs/fastapi.log"
echo "   - Logs Celery: tail -f data/logs/celery.log"
echo "   - Logs Docker: docker compose logs -f"
echo ""
echo "🛑 Para parar o sistema:"
echo "   ./stop_all.sh"
echo ""
echo "📝 Para testar o monitoramento:"
echo "   python test_redis_monitoring.py"
echo ""