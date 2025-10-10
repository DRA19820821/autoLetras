# orchestrator.ps1 - Gerenciador de Instâncias para Windows
# Compositor de Músicas Educativas
#
# Uso:
#   .\orchestrator.ps1 start -Instances 3
#   .\orchestrator.ps1 stop -Instance 1
#   .\orchestrator.ps1 status

param(
    [Parameter(Position=0, Mandatory=$false)]
    [ValidateSet('start', 'stop', 'status', 'restart')]
    [string]$Command = 'status',
    
    [Parameter(Mandatory=$false)]
    [int]$Instances = 1,
    
    [Parameter(Mandatory=$false)]
    [int]$Instance,
    
    [Parameter(Mandatory=$false)]
    [switch]$All,
    
    [Parameter(Mandatory=$false)]
    [int]$Id
)

$BASE_PORT_BACKEND = 8000
$BASE_PORT_REDIS = 6379
$PROJECT_ROOT = $PSScriptRoot
$INSTANCES_FILE = Join-Path $PROJECT_ROOT ".instances.json"

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

function Load-Instances {
    if (Test-Path $INSTANCES_FILE) {
        return Get-Content $INSTANCES_FILE | ConvertFrom-Json -AsHashtable
    }
    return @{}
}

function Save-Instances {
    param($Instances)
    $Instances | ConvertTo-Json -Depth 10 | Set-Content $INSTANCES_FILE
}

function Test-PortAvailable {
    param([int]$Port)
    
    try {
        $connection = New-Object System.Net.Sockets.TcpClient
        $connection.Connect("localhost", $Port)
        $connection.Close()
        return $false  # Porta em uso
    }
    catch {
        return $true   # Porta disponível
    }
}

function Find-AvailablePorts {
    param(
        [int]$BaseBackend,
        [int]$BaseRedis
    )
    
    $backendPort = $BaseBackend
    while (-not (Test-PortAvailable $backendPort)) {
        $backendPort++
        if ($backendPort -gt ($BaseBackend + 100)) {
            throw "Não foi possível encontrar porta backend disponível"
        }
    }
    
    $redisPort = $BaseRedis
    while (-not (Test-PortAvailable $redisPort)) {
        $redisPort++
        if ($redisPort -gt ($BaseRedis + 100)) {
            throw "Não foi possível encontrar porta redis disponível"
        }
    }
    
    return @{
        Backend = $backendPort
        Redis = $redisPort
    }
}

function Get-NextInstanceId {
    param($Instances)
    
    if ($Instances.Count -eq 0) {
        return 1
    }
    
    $maxId = ($Instances.Keys | ForEach-Object { [int]$_ } | Measure-Object -Maximum).Maximum
    return $maxId + 1
}

function New-EnvFile {
    param(
        [string]$FilePath,
        [int]$InstanceId,
        [int]$BackendPort,
        [int]$RedisPort
    )
    
    # Carregar .env base
    $baseEnvPath = Join-Path $PROJECT_ROOT ".env"
    $baseContent = ""
    if (Test-Path $baseEnvPath) {
        $baseContent = Get-Content $baseEnvPath -Raw
    }
    
    $envContent = @"
# Instância $InstanceId - Gerado automaticamente
# $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

$baseContent

# Configurações da Instância $InstanceId
INSTANCE_ID=$InstanceId
PORT=$BackendPort
REDIS_HOST=redis_instance_$InstanceId
REDIS_PORT=$RedisPort
DATA_DIR=data/instance_$InstanceId
"@
    
    Set-Content -Path $FilePath -Value $envContent -Encoding UTF8
}

function New-ComposeFile {
    param(
        [string]$FilePath,
        [int]$InstanceId,
        [int]$BackendPort,
        [int]$RedisPort
    )
    
    $composeContent = @"
version: '3.8'

services:
  redis_instance_$InstanceId`:
    image: redis:7-alpine
    container_name: redis_instance_$InstanceId
    ports:
      - "$RedisPort`:6379"
    volumes:
      - redis_data_instance_$InstanceId`:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - autoletras_instance_$InstanceId

  backend_instance_$InstanceId`:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: backend_instance_$InstanceId
    ports:
      - "$BackendPort`:8000"
    volumes:
      - ./data/instance_$InstanceId`:/app/data
      - ./backend:/app/backend
      - ./frontend:/app/frontend
    env_file:
      - .env.instance_$InstanceId
    environment:
      - REDIS_HOST=redis_instance_$InstanceId
      - REDIS_PORT=6379
      - PORT=8000
      - INSTANCE_ID=$InstanceId
      - PYTHONPATH=/app
    depends_on:
      redis_instance_$InstanceId`:
        condition: service_healthy
    command: uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
    networks:
      - autoletras_instance_$InstanceId

  worker_instance_$InstanceId`:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: worker_instance_$InstanceId
    volumes:
      - ./data/instance_$InstanceId`:/app/data
      - ./backend:/app/backend
    env_file:
      - .env.instance_$InstanceId
    environment:
      - REDIS_HOST=redis_instance_$InstanceId
      - REDIS_PORT=6379
      - INSTANCE_ID=$InstanceId
      - PYTHONPATH=/app
    depends_on:
      redis_instance_$InstanceId`:
        condition: service_healthy
    command: celery -A backend.celery_worker:celery_app worker --loglevel=info --pool=threads --concurrency=3
    networks:
      - autoletras_instance_$InstanceId

volumes:
  redis_data_instance_$InstanceId`:

networks:
  autoletras_instance_$InstanceId`:
    driver: bridge
"@
    
    Set-Content -Path $FilePath -Value $composeContent -Encoding UTF8
}

# ============================================================================
# COMANDOS PRINCIPAIS
# ============================================================================

function Start-Instance {
    param([int]$InstanceId)
    
    $instances = Load-Instances
    
    if ($instances.ContainsKey($InstanceId.ToString())) {
        Write-Host "[ERRO] Instancia $InstanceId ja esta rodando!" -ForegroundColor Red
        return $false
    }
    
    # Encontrar portas disponíveis
    $ports = Find-AvailablePorts -BaseBackend ($BASE_PORT_BACKEND + $InstanceId - 1) `
                                  -BaseRedis ($BASE_PORT_REDIS + $InstanceId - 1)
    
    Write-Host ""
    Write-Host ">>> Iniciando instancia $InstanceId <<<" -ForegroundColor Cyan
    Write-Host "    Backend: porta $($ports.Backend)" -ForegroundColor Gray
    Write-Host "    Redis: porta $($ports.Redis)" -ForegroundColor Gray
    
    # Criar diretórios
    $dataDir = Join-Path $PROJECT_ROOT "data\instance_$InstanceId"
    @('inputs', 'outputs', 'checkpoints', 'logs') | ForEach-Object {
        $dir = Join-Path $dataDir $_
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    
    # Criar arquivos de configuração
    $envFile = Join-Path $PROJECT_ROOT ".env.instance_$InstanceId"
    $composeFile = Join-Path $PROJECT_ROOT "docker-compose.instance_$InstanceId.yml"
    
    New-EnvFile -FilePath $envFile -InstanceId $InstanceId `
                -BackendPort $ports.Backend -RedisPort $ports.Redis
    
    New-ComposeFile -FilePath $composeFile -InstanceId $InstanceId `
                    -BackendPort $ports.Backend -RedisPort $ports.Redis
    
    # Iniciar containers
    try {
        $projectName = "autoletras_instance_$InstanceId"
        
        docker compose -f $composeFile -p $projectName up -d
        
        if ($LASTEXITCODE -ne 0) {
            throw "Erro ao iniciar containers"
        }
        
        # Salvar informações
        $instances[$InstanceId.ToString()] = @{
            id = $InstanceId
            backend_port = $ports.Backend
            redis_port = $ports.Redis
            started_at = (Get-Date).ToString("o")
            data_dir = $dataDir
            env_file = $envFile
            compose_file = $composeFile
            project_name = $projectName
        }
        
        Save-Instances -Instances $instances
        
        Write-Host ""
        Write-Host "[OK] Instancia $InstanceId iniciada com sucesso!" -ForegroundColor Green
        Write-Host "    URL: http://localhost:$($ports.Backend)" -ForegroundColor Cyan
        Write-Host "    Redis: localhost:$($ports.Redis)" -ForegroundColor Cyan
        Write-Host "    Dados: $dataDir" -ForegroundColor Gray
        
        return $true
    }
    catch {
        Write-Host "[ERRO] Erro ao iniciar instancia: $_" -ForegroundColor Red
        
        # Limpar arquivos criados
        Remove-Item -Path $envFile -ErrorAction SilentlyContinue
        Remove-Item -Path $composeFile -ErrorAction SilentlyContinue
        
        return $false
    }
}

function Stop-Instance {
    param([int]$InstanceId)
    
    $instances = Load-Instances
    $key = $InstanceId.ToString()
    
    if (-not $instances.ContainsKey($key)) {
        Write-Host "[ERRO] Instancia $InstanceId nao encontrada!" -ForegroundColor Red
        return $false
    }
    
    $instance = $instances[$key]
    
    Write-Host ""
    Write-Host ">>> Parando instancia $InstanceId <<<" -ForegroundColor Yellow
    
    try {
        docker compose -f $instance.compose_file -p $instance.project_name down
        
        # Remover arquivos de configuração
        Remove-Item -Path $instance.env_file -ErrorAction SilentlyContinue
        Remove-Item -Path $instance.compose_file -ErrorAction SilentlyContinue
        
        # Remover da lista
        $instances.Remove($key)
        Save-Instances -Instances $instances
        
        Write-Host "[OK] Instancia $InstanceId parada com sucesso!" -ForegroundColor Green
        Write-Host "    Dados preservados em: $($instance.data_dir)" -ForegroundColor Gray
        
        return $true
    }
    catch {
        Write-Host "[ERRO] Erro ao parar instancia: $_" -ForegroundColor Red
        return $false
    }
}

function Stop-AllInstances {
    $instances = Load-Instances
    
    if ($instances.Count -eq 0) {
        Write-Host "[INFO] Nenhuma instancia rodando" -ForegroundColor Cyan
        return
    }
    
    Write-Host ""
    Write-Host ">>> Parando $($instances.Count) instancia(s) <<<" -ForegroundColor Yellow
    
    foreach ($instanceId in $instances.Keys) {
        Stop-Instance -InstanceId ([int]$instanceId)
    }
    
    Write-Host ""
    Write-Host "[OK] Todas as instancias foram paradas!" -ForegroundColor Green
}

function Show-Status {
    $instances = Load-Instances
    
    if ($instances.Count -eq 0) {
        Write-Host ""
        Write-Host "[INFO] Nenhuma instancia rodando" -ForegroundColor Cyan
        return
    }
    
    Write-Host ""
    Write-Host "STATUS DAS INSTANCIAS ($($instances.Count) ativa(s))" -ForegroundColor Cyan
    Write-Host ("=" * 80)
    
    foreach ($instanceId in ($instances.Keys | Sort-Object { [int]$_ })) {
        $info = $instances[$instanceId]
        
        Write-Host ""
        Write-Host ">>> Instancia $instanceId <<<" -ForegroundColor Cyan
        Write-Host "    Backend: http://localhost:$($info.backend_port)" -ForegroundColor White
        Write-Host "    Redis: localhost:$($info.redis_port)" -ForegroundColor White
        Write-Host "    Dados: $($info.data_dir)" -ForegroundColor Gray
        Write-Host "    Iniciada: $($info.started_at)" -ForegroundColor Gray
        
        # Verificar containers
        try {
            $psOutput = docker compose -f $info.compose_file -p $info.project_name ps --format json 2>$null
            
            if ($psOutput) {
                $containers = $psOutput | ConvertFrom-Json
                $running = ($containers | Where-Object { $_.State -eq 'running' }).Count
                Write-Host "    Containers: $running/$($containers.Count) rodando" -ForegroundColor Green
            }
            else {
                Write-Host "    [AVISO] Status desconhecido" -ForegroundColor Yellow
            }
        }
        catch {
            Write-Host "    [AVISO] Erro ao verificar: $_" -ForegroundColor Yellow
        }
    }
    
    Write-Host ""
    Write-Host ("=" * 80)
}

function Start-MultipleInstances {
    param([int]$Count)
    
    Write-Host ""
    Write-Host ">>> Iniciando $Count instancia(s) <<<" -ForegroundColor Cyan
    
    $successCount = 0
    $instances = Load-Instances
    
    for ($i = 1; $i -le $Count; $i++) {
        $nextId = Get-NextInstanceId -Instances $instances
        
        if (Start-Instance -InstanceId $nextId) {
            $successCount++
            $instances = Load-Instances  # Recarregar após cada sucesso
            Start-Sleep -Seconds 2
        }
    }
    
    Write-Host ""
    Write-Host "[OK] $successCount/$Count instancia(s) iniciada(s) com sucesso!" -ForegroundColor Green
    
    if ($successCount -gt 0) {
        Show-Status
    }
}

# ============================================================================
# MAIN
# ============================================================================

switch ($Command) {
    'start' {
        if ($Id) {
            Start-Instance -InstanceId $Id
        }
        else {
            Start-MultipleInstances -Count $Instances
        }
    }
    
    'stop' {
        if ($All) {
            Stop-AllInstances
        }
        elseif ($Instance) {
            Stop-Instance -InstanceId $Instance
        }
        else {
            Write-Host "[ERRO] Especifique -Instance <ID> ou -All" -ForegroundColor Red
        }
    }
    
    'status' {
        Show-Status
    }
    
    'restart' {
        if ($Instance) {
            Stop-Instance -InstanceId $Instance
            Start-Sleep -Seconds 2
            Start-Instance -InstanceId $Instance
        }
        else {
            Write-Host "[ERRO] Especifique -Instance <ID>" -ForegroundColor Red
        }
    }
}