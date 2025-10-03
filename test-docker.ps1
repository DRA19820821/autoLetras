# Script de Teste Rápido - Docker
# Execute após o setup para verificar se tudo funciona

Write-Host ""
Write-Host "🧪 TESTE RÁPIDO DO SISTEMA" -ForegroundColor Cyan
Write-Host "===========================" -ForegroundColor Cyan
Write-Host ""

$allTests = $true

# Teste 1: Docker está rodando?
Write-Host "1. Docker" -ForegroundColor Yellow
try {
    docker --version | Out-Null
    Write-Host "   ✅ Docker instalado" -ForegroundColor Green
    
    docker ps | Out-Null
    Write-Host "   ✅ Docker rodando" -ForegroundColor Green
} catch {
    Write-Host "   ❌ Docker não está funcionando" -ForegroundColor Red
    $allTests = $false
}

# Teste 2: Containers estão up?
Write-Host ""
Write-Host "2. Containers" -ForegroundColor Yellow

$containers = @("redis", "backend", "worker")
foreach ($container in $containers) {
    $status = docker-compose ps $container 2>$null | Select-String "Up"
    if ($status) {
        Write-Host "   ✅ $container rodando" -ForegroundColor Green
    } else {
        Write-Host "   ❌ $container parado" -ForegroundColor Red
        $allTests = $false
    }
}

# Teste 3: Redis funcionando?
Write-Host ""
Write-Host "3. Redis" -ForegroundColor Yellow
$redisPong = docker-compose exec -T redis redis-cli ping 2>$null
if ($redisPong -match "PONG") {
    Write-Host "   ✅ Redis respondendo" -ForegroundColor Green
} else {
    Write-Host "   ❌ Redis não responde" -ForegroundColor Red
    $allTests = $false
}

# Teste 4: Backend acessível?
Write-Host ""
Write-Host "4. Backend" -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000" -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "   ✅ Backend acessível em http://localhost:8000" -ForegroundColor Green
    }
} catch {
    Write-Host "   ❌ Backend não está respondendo" -ForegroundColor Red
    Write-Host "   Aguarde mais alguns segundos e tente novamente" -ForegroundColor Yellow
    $allTests = $false
}

# Teste 5: API Keys configuradas?
Write-Host ""
Write-Host "5. Configuração" -ForegroundColor Yellow
if (Test-Path ".env") {
    $envContent = Get-Content ".env" -Raw
    $hasKey = $false
    
    if ($envContent -match "ANTHROPIC_API_KEY=sk-") { $hasKey = $true }
    if ($envContent -match "OPENAI_API_KEY=sk-") { $hasKey = $true }
    if ($envContent -match "GOOGLE_API_KEY=\w+") { $hasKey = $true }
    if ($envContent -match "DEEPSEEK_API_KEY=\w+") { $hasKey = $true }
    
    if ($hasKey) {
        Write-Host "   ✅ API Keys configuradas" -ForegroundColor Green
    } else {
        Write-Host "   ⚠️  Nenhuma API Key detectada" -ForegroundColor Yellow
        Write-Host "      Adicione suas keys no arquivo .env" -ForegroundColor Gray
    }
    
    if ($envContent -match "REDIS_HOST=redis") {
        Write-Host "   ✅ Redis configurado para Docker" -ForegroundColor Green
    } else {
        Write-Host "   ❌ REDIS_HOST deve ser 'redis' para Docker" -ForegroundColor Red
        $allTests = $false
    }
} else {
    Write-Host "   ❌ Arquivo .env não encontrado" -ForegroundColor Red
    $allTests = $false
}

# Resultado Final
Write-Host ""
Write-Host "===========================" -ForegroundColor Cyan
if ($allTests) {
    Write-Host "✅ SISTEMA PRONTO PARA USO!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Acesse: http://localhost:8000" -ForegroundColor Cyan
    Write-Host ""
    
    $openBrowser = Read-Host "Abrir no navegador agora? (s/n)"
    if ($openBrowser -eq 's') {
        Start-Process "http://localhost:8000"
    }
} else {
    Write-Host "⚠️  ALGUNS TESTES FALHARAM" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Soluções:" -ForegroundColor Cyan
    Write-Host "1. Aguarde 30 segundos e tente novamente" -ForegroundColor White
    Write-Host "2. Reinicie os containers: docker-compose restart" -ForegroundColor White
    Write-Host "3. Veja os logs: docker-compose logs" -ForegroundColor White
}
Write-Host "===========================" -ForegroundColor Cyan