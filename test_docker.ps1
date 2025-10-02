# Script de teste para verificar se o ambiente Docker está funcionando (PowerShell)

Write-Host ""
Write-Host "🐳 Testando Ambiente Docker" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

$allPassed = $true

function Test-Step {
    param(
        [string]$Description,
        [bool]$Result
    )
    
    if ($Result) {
        Write-Host "✓ $Description" -ForegroundColor Green
        return $true
    } else {
        Write-Host "✗ $Description" -ForegroundColor Red
        $script:allPassed = $false
        return $false
    }
}

# 1. Verificar se Docker está rodando
Write-Host "1. Verificando Docker..."
try {
    $dockerRunning = docker ps 2>$null
    Test-Step "Docker está rodando" ($LASTEXITCODE -eq 0)
} catch {
    Test-Step "Docker está rodando" $false
}
Write-Host ""

# 2. Verificar se containers estão rodando
Write-Host "2. Verificando containers..."
try {
    $containers = docker compose ps 2>$null
    $containersUp = $containers -match "Up"
    Test-Step "Containers estão rodando" ($containersUp.Count -gt 0)
} catch {
    Test-Step "Containers estão rodando" $false
}
Write-Host ""

# 3. Verificar Redis
Write-Host "3. Testando Redis..."
try {
    $redisPing = docker compose exec -T redis redis-cli ping 2>$null
    Test-Step "Redis respondendo" ($redisPing -match "PONG")
} catch {
    Test-Step "Redis respondendo" $false
}
Write-Host ""

# 4. Verificar Backend
Write-Host "4. Testando Backend..."
Start-Sleep -Seconds 2
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/" -TimeoutSec 5 -UseBasicParsing 2>$null
    Test-Step "Backend respondendo na porta 8000" ($response.StatusCode -eq 200)
} catch {
    Test-Step "Backend respondendo na porta 8000" $false
    Write-Host "  Aguarde alguns segundos para o backend inicializar" -ForegroundColor Yellow
}
Write-Host ""

# 5. Verificar Worker
Write-Host "5. Verificando Worker..."
try {
    $workerLogs = docker compose logs worker 2>$null
    $workerActive = $workerLogs -match "celery@"
    Test-Step "Worker Celery ativo" $workerActive
} catch {
    Test-Step "Worker Celery ativo" $false
}
Write-Host ""

# 6. Verificar .env
Write-Host "6. Verificando configuração..."
if (Test-Path .env) {
    Write-Host "✓ Arquivo .env existe" -ForegroundColor Green
    
    $envContent = Get-Content .env -Raw
    if ($envContent -match "API_KEY=sk-" -or $envContent -match "API_KEY=.*[A-Za-z0-9]") {
        Write-Host "✓ API keys configuradas" -ForegroundColor Green
    } else {
        Write-Host "⚠ Nenhuma API key parece estar configurada" -ForegroundColor Yellow
        Write-Host "  Configure pelo menos uma API key no .env" -ForegroundColor Yellow
    }
} else {
    Write-Host "✗ Arquivo .env não encontrado" -ForegroundColor Red
    Write-Host "  Execute: Copy-Item .env.example .env" -ForegroundColor Yellow
    $allPassed = $false
}
Write-Host ""

# 7. Verificar diretórios
Write-Host "7. Verificando diretórios..."
$dirs = @("data\inputs", "data\outputs", "data\checkpoints", "data\logs")
foreach ($dir in $dirs) {
    if (Test-Path $dir) {
        Write-Host "✓ $dir" -ForegroundColor Green
    } else {
        Write-Host "⚠ $dir não existe (será criado automaticamente)" -ForegroundColor Yellow
    }
}
Write-Host ""

# 8. Testar importações Python
Write-Host "8. Testando importações Python..."
try {
    $pythonTest = @"
import sys
try:
    from backend.app.api.schemas import MusicaState
    from backend.app.agents.graph import compilar_workflow
    from backend.app.core.llm_client import get_chat_model
    print('OK')
    sys.exit(0)
except ImportError as e:
    print(f'ERRO: {e}')
    sys.exit(1)
"@
    
    $result = docker compose exec -T backend python -c $pythonTest 2>$null
    Test-Step "Importações Python" ($result -match "OK")
} catch {
    Test-Step "Importações Python" $false
}
Write-Host ""

# Resumo
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "📊 Resumo do Teste" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

if ($allPassed) {
    Write-Host "✅ Todos os testes passaram!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Acesse a aplicação em:" -ForegroundColor Cyan
    Write-Host "  👉 http://localhost:8000" -ForegroundColor Yellow
} else {
    Write-Host "⚠️  Alguns testes falharam." -ForegroundColor Yellow
    Write-Host "Verifique as mensagens acima e corrija os problemas." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Comandos úteis:" -ForegroundColor Cyan
Write-Host "  Ver logs: docker compose logs -f"
Write-Host "  Parar: docker compose down"
Write-Host "  Reconstruir: docker compose build --no-cache"
Write-Host ""