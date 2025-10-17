📌 Uso Básico (com confirmação)
bashpython clean_data.py
Mostra o que será deletado e pede confirmação.
🚀 Exemplos de Uso
1. Ver o que seria deletado (sem deletar nada)
bashpython clean_data.py --dry-run
2. Limpar tudo sem confirmação
bashpython clean_data.py --force
3. Limpar apenas arquivos (mantém estrutura de pastas)
bashpython clean_data.py --keep-structure
4. Limpar apenas pastas instance_*
bashpython clean_data.py --instances-only
5. Criar backup antes de limpar
bashpython clean_data.py --backup
6. Combinar opções
bash# Backup + limpar só instances + sem confirmação
python clean_data.py --backup --instances-only --force

# Ver o que seria deletado das instances
python clean_data.py --instances-only --dry-run
📊 Funcionalidades do Script

Estatísticas Detalhadas: Mostra quantidade de arquivos, diretórios e tamanho total
Confirmação de Segurança: Pede confirmação antes de deletar (exceto com --force)
Backup Automático: Opção de criar backup antes de limpar
Dry Run: Visualizar o que será deletado sem deletar
Limpeza Seletiva: Pode limpar só instances ou manter estrutura
Cores no Terminal: Interface visual clara e intuitiva
Tratamento de Erros: Lista arquivos que não puderam ser deletados

⚠️ Avisos de Segurança

SEM --force: Sempre pede confirmação
COM --backup: Cria cópia de segurança antes
COM --dry-run: Apenas simula, não deleta nada

📝 Output do Script
O script mostra:

Resumo do conteúdo atual
Lista de instâncias e seus tamanhos
Quantidade de arquivos por pasta
Confirmação antes de deletar
Progresso durante a limpeza
Resumo final do que foi deletado

🔧 Casos de Uso Comuns
Após terminar um processamento grande:
# Ver o que tem na pasta
python clean_data.py --dry-run

# Fazer backup e limpar tudo
python clean_data.py --backup --force
Limpar só os outputs, manter inputs:
# Remove apenas arquivos (mantém a estrutura)
python clean_data.py --keep-structure
Resetar instâncias sem perder outros dados:
# Remove só pastas instance_*
python clean_data.py --instances-only
Script completo de reset:
# 1. Parar instâncias
python orchestrator.py stop --all

# 2. Limpar dados
python clean_data.py --force

# 3. Reiniciar instâncias
python orchestrator.py start --instances 3
O script é seguro e eficiente para gerenciar a limpeza da pasta data! 🧹
