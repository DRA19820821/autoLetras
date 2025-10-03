# =====================================
# Setup Docker - Windows 11
# Compositor de Músicas Educativas
# =====================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " 🚀 SETUP DOCKER - WINDOWS 11" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Função para pausar
function Pause-Script {
    Write-Host ""
    Write-Host "Pressione ENTER para continuar..." -ForegroundColor Yellow
    Read-Host
}

# =========================
# ETAPA 1: Verificar Docker
# =========================
Write-Host "ETAPA 1: Verificando Docker Desktop" -ForegroundColor Green
Write-Host "------------------------------------"

$dockerInstalled = $false
try {
    $dockerVersion = docker --version 2>$null
    if ($dockerVersion) {
        Write-Host "✅ Docker encontrado: $dockerVersion" -ForegroundColor Green
        $dockerInstalled = $true
    }
} catch {
    Write-Host "❌ Docker NÃO está instalado" -ForegroundColor Red
}

if (-not $dockerInstalled) {
    Write-Host ""
    Write-Host "⚠️  Docker Desktop não está instalado!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Por favor, siga estes passos:" -ForegroundColor Cyan
    Write-Host "1. Baixe o Docker Desktop em:" -ForegroundColor White
    Write-Host "   https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "2. Instale o Docker Desktop" -ForegroundColor White
    Write-Host "3. Reinicie o computador" -ForegroundColor White
    Write-Host "4. Execute este script novamente" -ForegroundColor White
    Write-Host ""
    exit 1
}

# Verificar se Docker está rodando
Write-Host ""
Write-Host "Verificando se Docker está rodando..."
$dockerRunning = $false
try {
    docker ps 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Docker está rodando" -ForegroundColor Green
        $dockerRunning = $true
    }
} catch {}

if (-not $dockerRunning) {
    Write-Host "⚠️  Docker Desktop não está rodando!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Por favor:" -ForegroundColor Cyan
    Write-Host "1. Abra o Docker Desktop (procure no Menu Iniciar)" -ForegroundColor White
    Write-Host "2. Aguarde aparecer 'Docker Desktop is running'" -ForegroundColor White
    Write-Host "3. Execute este script novamente" -ForegroundColor White
    Write-Host ""
    
    # Tentar abrir Docker Desktop
    $openDocker = Read-Host "Deseja que eu tente abrir o Docker Desktop? (s/n)"
    if ($openDocker -eq 's') {
        Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe" -ErrorAction SilentlyContinue
        Write-Host ""
        Write-Host "Aguarde o Docker iniciar completamente (cerca de 30 segundos)..." -ForegroundColor Yellow
        Write-Host "Depois execute este script novamente." -ForegroundColor Yellow
    }
    exit 1
}

Pause-Script

# =========================
# ETAPA 2: Verificar .env
# =========================
Write-Host ""
Write-Host "ETAPA 2: Configurando arquivo .env" -ForegroundColor Green
Write-Host "-----------------------------------"

if (-not (Test-Path ".env")) {
    Write-Host "📝 Criando arquivo .env..." -ForegroundColor Yellow
    
    # Criar .env básico
    $envContent = @"
# ===================================
# CONFIGURAÇÃO PARA DOCKER
# ===================================

# API Keys - ADICIONE PELO MENOS UMA!
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_API_KEY=
DEEPSEEK_API_KEY=

# Redis - NÃO ALTERE (Docker)
REDIS_HOST=redis
REDIS_PORT=6379

# Caminhos
DATA_DIR=data
CHECKPOINTS_DB=data/checkpoints/checkpoints.db

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=legivel

# Server
HOST=0.0.0.0
PORT=8000

# Python
PYTHONPATH=/app
"@
    
    $envContent | Out-File -FilePath ".env" -Encoding UTF8
    Write-Host "✅ Arquivo .env criado" -ForegroundColor Green
    Write-Host ""
    Write-Host "⚠️  IMPORTANTE: Você precisa adicionar suas API Keys!" -ForegroundColor Yellow
    Write-Host ""
    
    $editNow = Read-Host "Deseja editar o .env agora para adicionar as API Keys? (s/n)"
    if ($editNow -eq 's') {
        notepad .env
        Write-Host ""
        Write-Host "Adicione pelo menos uma API Key e salve o arquivo." -ForegroundColor Yellow
        Pause-Script
    } else {
        Write-Host ""
        Write-Host "⚠️  Lembre-se de adicionar as API Keys antes de usar!" -ForegroundColor Yellow
        Write-Host "   Use: notepad .env" -ForegroundColor Cyan
    }
} else {
    Write-Host "✅ Arquivo .env já existe" -ForegroundColor Green
    
    # Verificar se tem alguma API key
    $envContent = Get-Content ".env" -Raw
    $hasApiKey = $false
    
    if ($envContent -match "API_KEY=\S+") {
        $hasApiKey = $true
        Write-Host "✅ API Keys detectadas" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Nenhuma API Key configurada!" -ForegroundColor Yellow
        Write-Host ""
        $editNow = Read-Host "Deseja adicionar API Keys agora? (s/n)"
        if ($editNow -eq 's') {
            notepad .env
            Pause-Script
        }
    }
}

Pause-Script

# =========================
# ETAPA 3: Criar Diretórios
# =========================
Write-Host ""
Write-Host "ETAPA 3: Criando estrutura de diretórios" -ForegroundColor Green
Write-Host "-----------------------------------------"

$directories = @(
    "data",
    "data\inputs",
    "data\outputs",
    "data\checkpoints",
    "data\logs"
)

foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "📁 Criado: $dir" -ForegroundColor Green
    } else {
        Write-Host "✅ Existe: $dir" -ForegroundColor Gray
    }
}

Pause-Script

# =========================
# ETAPA 4: Limpar Containers Antigos
# =========================
Write-Host ""
Write-Host "ETAPA 4: Limpando containers antigos" -ForegroundColor Green
Write-Host "-------------------------------------"

Write-Host "Parando containers existentes..."
docker-compose down 2>$null
Write-Host "✅ Containers limpos" -ForegroundColor Green

Pause-Script

# =========================
# ETAPA 5: Construir Imagens
# =========================
Write-Host ""
Write-Host "ETAPA 5: Construindo imagens Docker" -ForegroundColor Green
Write-Host "------------------------------------"
Write-Host ""
Write-Host "⏳ Isso pode demorar 2-5 minutos na primeira vez..." -ForegroundColor Yellow
Write-Host ""

docker-compose build --no-cache

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "❌ Erro ao construir imagens!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Possíveis soluções:" -ForegroundColor Yellow
    Write-Host "1. Verifique sua conexão com a internet" -ForegroundColor White
    Write-Host "2. Tente novamente: docker-compose build" -ForegroundColor White
    exit 1
}

Write-Host ""
Write-Host "✅ Imagens construídas com sucesso!" -ForegroundColor Green

Pause-Script

# =========================
# ETAPA 6: Iniciar Containers
# =========================
Write-Host ""
Write-Host "ETAPA 6: Iniciando containers" -ForegroundColor Green
Write-Host "------------------------------"

docker-compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "❌ Erro ao iniciar containers!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "⏳ Aguardando serviços iniciarem (10 segundos)..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# =========================
# ETAPA 7: Verificar Status
# =========================
Write-Host ""
Write-Host "ETAPA 7: Verificando status dos serviços" -ForegroundColor Green
Write-Host "-----------------------------------------"
Write-Host ""

$services = @{
    "redis" = "Banco de dados Redis"
    "backend" = "Servidor FastAPI"
    "worker" = "Processador Celery"
}

$allRunning = $true
foreach ($service in $services.Keys) {
    $status = docker-compose ps $service 2>$null | Select-String "Up"
    if ($status) {
        Write-Host "✅ $service está rodando - $($services[$service])" -ForegroundColor Green
    } else {
        Write-Host "❌ $service NÃO está rodando - $($services[$service])" -ForegroundColor Red
        $allRunning = $false
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan

if ($allRunning) {
    Write-Host ""
    Write-Host "🎉 SUCESSO! TUDO ESTÁ FUNCIONANDO!" -ForegroundColor Green
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "📌 ACESSE A APLICAÇÃO:" -ForegroundColor Yellow
    Write-Host "   http://localhost:8000" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "📝 INSTRUÇÕES DE USO:" -ForegroundColor Yellow
    Write-Host "   1. Faça upload de arquivos HTML" -ForegroundColor White
    Write-Host "   2. Configure o estilo musical" -ForegroundColor White
    Write-Host "   3. Escolha os modelos de IA" -ForegroundColor White
    Write-Host "   4. Clique em 'Iniciar Processamento'" -ForegroundColor White
    Write-Host "   5. Acompanhe o progresso em tempo real!" -ForegroundColor White
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "🛠️  COMANDOS ÚTEIS:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Ver logs em tempo real:" -ForegroundColor Cyan
    Write-Host "  docker-compose logs -f" -ForegroundColor White
    Write-Host ""
    Write-Host "Ver logs de um serviço específico:" -ForegroundColor Cyan
    Write-Host "  docker-compose logs -f backend" -ForegroundColor White
    Write-Host "  docker-compose logs -f worker" -ForegroundColor White
    Write-Host "  docker-compose logs -f redis" -ForegroundColor White
    Write-Host ""
    Write-Host "Parar tudo:" -ForegroundColor Cyan
    Write-Host "  docker-compose down" -ForegroundColor White
    Write-Host ""
    Write-Host "Reiniciar tudo:" -ForegroundColor Cyan
    Write-Host "  docker-compose restart" -ForegroundColor White
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    
    # Abrir navegador
    $openBrowser = Read-Host "Deseja abrir o navegador agora? (s/n)"
    if ($openBrowser -eq 's') {
        Start-Process "http://localhost:8000"
    }
    
    Write-Host ""
    Write-Host "Deseja ver os logs em tempo real? (s/n)" -ForegroundColor Yellow
    $showLogs = Read-Host
    if ($showLogs -eq 's') {
        Write-Host ""
        Write-Host "Mostrando logs (Ctrl+C para sair):" -ForegroundColor Cyan
        Write-Host "========================================" -ForegroundColor Cyan
        docker-compose logs -f
    }
    
} else {
    Write-Host ""
    Write-Host "⚠️  ALGUNS SERVIÇOS NÃO INICIARAM" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Tente os seguintes comandos:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "1. Ver o que está errado:" -ForegroundColor White
    Write-Host "   docker-compose logs" -ForegroundColor Gray
    Write-Host ""
    Write-Host "2. Reiniciar tudo:" -ForegroundColor White
    Write-Host "   docker-compose down" -ForegroundColor Gray
    Write-Host "   docker-compose up -d" -ForegroundColor Gray
    Write-Host ""
    Write-Host "3. Reconstruir se necessário:" -ForegroundColor White
    Write-Host "   docker-compose build --no-cache" -ForegroundColor Gray
    Write-Host "   docker-compose up -d" -ForegroundColor Gray
}