# 🎵 Guia de Uso - Múltiplas Instâncias

## 📋 Visão Geral

O sistema suporta executar múltiplas instâncias em paralelo, cada uma com seu próprio backend, worker e Redis. Isso permite processar grandes volumes de arquivos simultaneamente.

## 🚀 Início Rápido

### 1. Iniciar Instâncias

```bash
# Iniciar 3 instâncias
python orchestrator.py start --instances 3

# Ou iniciar uma instância específica
python orchestrator.py start --id 1
```

### 2. Verificar Status

```bash
# Ver status de todas as instâncias
python orchestrator.py status

# Monitorar em tempo real
python helper_scripts.py monitor --follow
```

### 3. Distribuir Arquivos

```bash
# Distribuir arquivos HTML entre as instâncias (estratégia balanceada)
python helper_scripts.py distribute pasta_com_htmls --strategy balanced

# Ou usar round-robin
python helper_scripts.py distribute pasta_com_htmls --strategy round-robin
```

### 4. Processar

Acesse cada instância no navegador:
- Instância 1: http://localhost:8000
- Instância 2: http://localhost:8001
- Instância 3: http://localhost:8002

Configure e inicie o processamento em cada uma.

### 5. Coletar Resultados

```bash
# Coletar todos os resultados em uma pasta
python helper_scripts.py collect --output resultados_finais
```

### 6. Parar Instâncias

```bash
# Parar uma instância específica
python orchestrator.py stop --instance 1

# Parar todas
python orchestrator.py stop --all
```

## 📁 Estrutura de Diretórios

```
projeto/
├── data/
│   ├── instance_1/
│   │   ├── inputs/      # Arquivos HTML para processar
│   │   ├── outputs/     # Resultados JSON
│   │   ├── checkpoints/ # Estados do workflow
│   │   └── logs/        # Logs da instância
│   ├── instance_2/
│   │   └── ...
│   └── instance_3/
│       └── ...
```

## 🔧 Comandos Úteis

### Orchestrator

```bash
# Iniciar múltiplas instâncias
python orchestrator.py start --instances N

# Iniciar instância específica
python orchestrator.py start --id ID

# Parar instância
python orchestrator.py stop --instance ID

# Parar todas
python orchestrator.py stop --all

# Ver status
python orchestrator.py status

# Reiniciar instância
python orchestrator.py restart ID
```

### Helper Scripts

```bash
# Distribuir arquivos
python helper_scripts.py distribute DIR [--strategy balanced|round-robin]

# Coletar resultados
python helper_scripts.py collect [--output DIR]

# Monitorar instâncias
python helper_scripts.py monitor [--follow]

# Limpar outputs
python helper_scripts.py clean [--instance ID]

# Validar estrutura
python helper_scripts.py validate
```

### Testes

```bash
# Testar sistema completo
python test_instances.py
```

## 📊 Exemplo de Workflow Completo

### Cenário: Processar 90 arquivos HTML usando 3 instâncias

```bash
# 1. Iniciar 3 instâncias
python orchestrator.py start --instances 3

# 2. Verificar que estão rodando
python orchestrator.py status

# 3. Distribuir os 90 arquivos (30 por instância)
python helper_scripts.py distribute meus_htmls --strategy balanced

# 4. Verificar distribuição
python helper_scripts.py validate

# 5. Processar em cada instância
# Abrir em 3 abas do navegador:
# - http://localhost:8000 (processar 30 arquivos)
# - http://localhost:8001 (processar 30 arquivos)
# - http://localhost:8002 (processar 30 arquivos)

# 6. Monitorar progresso
python helper_scripts.py monitor --follow

# 7. Após conclusão, coletar resultados
python helper_scripts.py collect --output resultados_completos

# 8. Parar instâncias
python orchestrator.py stop --all
```

## 🐳 Docker

Cada instância usa containers Docker separados:

- `redis_instance_N`: Redis dedicado
- `backend_instance_N`: FastAPI backend
- `worker_instance_N`: Celery worker

### Ver logs Docker

```bash
# Logs de uma instância específica
docker compose -f docker-compose.instance_1.yml logs -f

# Logs de um serviço específico
docker compose -f docker-compose.instance_1.yml logs -f worker
```

## ⚠️ Solução de Problemas

### Problema: Duplicação de pastas

**Sintoma:** Pastas aparecem como `data/instance_1/instance_1/`

**Solução:** 
1. Pare todas as instâncias: `python orchestrator.py stop --all`
2. Remova arquivos de configuração antigos: `rm .env.instance_* docker-compose.instance_*.yml`
3. Reinicie: `python orchestrator.py start --instances N`

### Problema: Arquivos não encontrados

**Sintoma:** "Arquivo não encontrado" ao processar

**Solução:**
1. Verifique onde os arquivos foram colocados: `python helper_scripts.py validate`
2. Redistribua se necessário: `python helper_scripts.py distribute DIR`

### Problema: Porta em uso

**Sintoma:** "Porta X já está em uso"

**Solução:**
1. Verifique processos: `docker ps`
2. Pare containers órfãos: `docker stop $(docker ps -q)`
3. Reinicie instâncias

## 📈 Monitoramento e Métricas

### Ver estatísticas em tempo real

```bash
# Monitor interativo
python helper_scripts.py monitor --follow
```

### Verificar saúde das APIs

```bash
# Para cada instância
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
```

## 💡 Dicas

1. **Balanceamento de carga**: Use `--strategy balanced` para distribuir igualmente
2. **Processamento em lote**: Configure todas as instâncias antes de iniciar
3. **Logs centralizados**: Cada instância tem sua pasta de logs em `data/instance_N/logs/`
4. **Backup**: Os resultados ficam em `data/instance_N/outputs/` até serem coletados

## 🔍 Verificação Final

Após processar, verifique:

```bash
# 1. Validar estrutura
python helper_scripts.py validate

# 2. Contar arquivos processados
find data -name "*.json" -type f | wc -l

# 3. Verificar se há erros nos logs
grep -r "ERROR" data/*/logs/

# 4. Coletar todos os resultados
python helper_scripts.py collect --output resultados_finais
```

## 📝 Observações

- Cada instância é independente e tem seu próprio Redis
- Os arquivos de configuração (.env.instance_N) são gerados automaticamente
- Os dados são preservados mesmo após parar as instâncias
- Use `clean` para limpar outputs antes de novo processamento

---

**Versão:** 1.0
**Última atualização:** Outubro 2025