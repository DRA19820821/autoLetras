document.addEventListener('DOMContentLoaded', () => {
    const filesStatusContainer = document.getElementById('filesStatusContainer');

    function getBadgeClass(status) {
        switch (status) {
            case 'processando': return 'badge-info';
            case 'concluido': return 'badge-success';
            case 'falha': return 'badge-error';
            default: return 'badge-info';
        }
    }
    
    function getProgressBarClass(status) {
        switch (status) {
            case 'processando': return 'bg-blue-500';
            case 'concluido': return 'bg-green-500';
            case 'falha': return 'bg-red-500';
            default: return 'bg-gray-500';
        }
    }

    // Ouvinte para eventos SSE, gerenciado pelo HTMX
    document.body.addEventListener('htmx:sseMessage', function(event) {
        const data = JSON.parse(event.detail.data);
        console.log("SSE Received:", data);

        if (data.type === 'geral_status') {
            document.getElementById('geralStatus').textContent = data.status;
            document.getElementById('geralProgresso').textContent = `Progresso: ${data.progresso_percentual}%`;
            document.getElementById('progressBar').style.width = `${data.progresso_percentual}%`;
        } 
        else if (data.type === 'file_progress' || data.type === 'file_result') {
            const fileId = data.arquivo.replace(/\./g, '_');
            let fileElement = document.getElementById(`status-${fileId}`);
            
            if (!fileElement) { // Se o elemento não existe, cria a partir de um template
                console.warn(`Element for ${data.arquivo} not found. Creating.`);
                // Poderia ser criado dinamicamente se necessário
                return;
            }

            const etapa = fileElement.querySelector('.etapa');
            const progressBar = fileElement.querySelector('.progresso-barra');
            const badgeContainer = fileElement.querySelector('.badge');
            
            if(data.type === 'file_progress') {
                etapa.textContent = data.etapa_atual;
                progressBar.style.width = `${data.progresso_percentual}%`;
                
                if (badgeContainer.textContent.toLowerCase() !== 'processando') {
                    badgeContainer.className = `badge ${getBadgeClass('processando')}`;
                    badgeContainer.textContent = 'Processando';
                    progressBar.className = `progresso-barra h-1.5 rounded-full ${getProgressBarClass('processando')}`;
                }
            } else { // file_result
                 etapa.textContent = data.status === 'concluido' ? `Finalizado: ${data.output_gerado}` : `Erro: ${data.erro}`;
                 progressBar.style.width = '100%';
                 badgeContainer.className = `badge ${getBadgeClass(data.status)}`;
                 badgeContainer.textContent = data.status;
                 progressBar.className = `progresso-barra h-1.5 rounded-full ${getProgressBarClass(data.status)}`;
            }
        }
    });
});