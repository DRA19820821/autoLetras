document.addEventListener('DOMContentLoaded', function() {
    
    // Gerencia a visibilidade dos blocos de ciclo
    const numCiclosSelect = document.getElementById('numCiclosSelect');
    if (numCiclosSelect) {
        numCiclosSelect.addEventListener('change', function() {
            const numCiclos = parseInt(this.value);
            for (let i = 1; i <= 3; i++) {
                const cicloDiv = document.getElementById(`ciclo${i}`);
                if (cicloDiv) {
                    cicloDiv.classList.toggle('hidden', i > numCiclos);
                }
            }
        });
    }

    // Lógica para coletar nomes de arquivos e redirecionar após submissão
    document.body.addEventListener('htmx:beforeRequest', function(evt) {
        // Verifica se a requisição é para iniciar uma execução
        if (evt.detail.elt.id === 'mainForm') {
            const fileInput = document.getElementById('fileInput');
            const files = fileInput.files;

            if (files.length === 0) {
                alert('Por favor, selecione ao menos um arquivo HTML.');
                evt.preventDefault(); // Cancela a requisição HTMX
                return;
            }

            // Adiciona os nomes dos arquivos ao payload do formulário
            const fileNames = Array.from(files).map(f => f.name);
            evt.detail.requestConfig.parameters['arquivos'] = JSON.stringify(fileNames);
        }
    });

    // Lida com a resposta do servidor após iniciar a execução
    document.body.addEventListener('htmx:afterRequest', function(evt) {
         if (evt.detail.elt.id === 'mainForm' && evt.detail.successful) {
            try {
                const response = JSON.parse(evt.detail.xhr.responseText);
                if (response.execucao_id) {
                    // Redireciona para a página de monitoramento
                    window.location.href = `/monitoring/${response.execucao_id}`;
                }
            } catch (e) {
                console.error("Erro ao processar resposta do formulário:", e);
                // Exibe o HTML de erro retornado pelo servidor no container de resposta
                document.getElementById('response-container').innerHTML = evt.detail.xhr.responseText;
            }
        }
    });
});