# Use uma imagem base do Python
FROM python:3.12-slim

# Defina o diretório de trabalho no container
WORKDIR /app

# Adicione o diretório de trabalho ao PYTHONPATH
# Esta é a correção principal para os ModuleNotFoundErrors
ENV PYTHONPATH=/app

# Copie os arquivos de dependências
COPY requirements.txt .

# Instale as dependências
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copie o resto do código da aplicação
COPY . .

# A porta que a aplicação vai expor
EXPOSE 8000

# Comando padrão para executar a aplicação (pode ser sobrescrito pelo docker-compose)
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]