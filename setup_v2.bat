@echo off
REM Script de setup para Windows
REM Compositor de Músicas Educativas

echo.
echo Compositor de Musicas Educativas - Setup
echo ============================================
echo.

REM Verificar Python
echo Verificando Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python nao encontrado. Instale Python 3.12+ primeiro.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo [OK] Python %PYTHON_VERSION% encontrado
echo.

REM Criar virtual environment
echo Criando ambiente virtual...
if not exist "venv" (
    python -m venv venv
    echo [OK] Virtual environment criado
) else (
    echo [AVISO] Virtual environment ja existe
)
echo.

REM Ativar venv
echo Ativando virtual environment...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [ERROR] Erro ao ativar virtual environment
    pause
    exit /b 1
)
echo [OK] Virtual environment ativado
echo.


REM Criar estrutura de diretórios
echo Criando estrutura de diretorios...
if not exist "data\inputs" mkdir data\inputs
if not exist "data\outputs" mkdir data\outputs
if not exist "data\checkpoints" mkdir data\checkpoints
if not exist "data\logs" mkdir data\logs
if not exist "data\configs" mkdir data\configs
if not exist "frontend\static\css" mkdir frontend\static\css
if not exist "frontend\static\js" mkdir frontend\static\js
if not exist "frontend\templates" mkdir frontend\templates
if not exist "backend\app\api" mkdir backend\app\api
if not exist "backend\app\agents" mkdir backend\app\agents
if not exist "backend\app\core" mkdir backend\app\core
if not exist "backend\app\retry" mkdir backend\app\retry
if not exist "backend\app\utils" mkdir backend\app\utils
if not exist "backend\tests" mkdir backend\tests

REM Criar .gitkeep files
type nul > data\inputs\.gitkeep
type nul > data\outputs\.gitkeep
type nul > data\checkpoints\.gitkeep
type nul > data\logs\.gitkeep

echo [OK] Estrutura de diretorios criada
echo.

REM Configurar .env
echo Configurando arquivo .env...
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo [OK] Arquivo .env criado a partir de .env.example
        echo [IMPORTANTE] Edite o arquivo .env e adicione suas API keys!
    ) else (
        echo [AVISO] .env.example nao encontrado, criando .env basico...
        (
            echo # API Keys
            echo ANTHROPIC_API_KEY=
            echo OPENAI_API_KEY=
            echo GOOGLE_API_KEY=
            echo DEEPSEEK_API_KEY=
            echo.
            echo # Throttling
            echo THROTTLE_OPENAI=5
            echo THROTTLE_ANTHROPIC=5
            echo THROTTLE_GOOGLE=8
            echo THROTTLE_DEEPSEEK=3
            echo.
            echo # Paths
            echo DATA_DIR=data
            echo CHECKPOINTS_DB=data/checkpoints/checkpoints.db
            echo.
            echo # Logging
            echo LOG_LEVEL=INFO
            echo LOG_FORMAT=legivel
            echo.
            echo # Server
            echo HOST=0.0.0.0
            echo PORT=8000
        ) > .env
        echo [OK] Arquivo .env basico criado
    )
) else (
    echo [AVISO] Arquivo .env ja existe, pulando...
)
echo.

REM Verificar config.yaml
echo Verificando config.yaml...
if not exist "config.yaml" (
    echo [ERROR] config.yaml nao encontrado!
    echo Execute este script no diretorio raiz do projeto.
    pause
    exit /b 1
)
echo [OK] config.yaml encontrado
echo.

REM Testar importações
echo Testando importacoes Python...
python -c "import fastapi, langchain, langgraph, litellm, structlog; print('[OK] Todas as dependencias principais importadas')" 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Erro ao importar dependencias
    pause
    exit /b 1
)
echo.

REM Instruções finais
echo ============================================
echo [SUCESSO] Setup concluido com sucesso!
echo.
echo Proximos passos:
echo.
echo 1. Edite o arquivo .env e adicione suas API keys:
echo    notepad .env
echo.
echo 2. Execute o servidor:
echo    python backend\main.py
echo.
echo 3. Acesse a interface web:
echo    http://localhost:8000
echo.
echo 4. (Opcional) Configure throttling em config.yaml
echo.
echo Para mais informacoes, consulte o README.md
echo.
echo Academia do Raciocinio
echo ============================================
echo.
pause