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

    // Interceptar o submit do formulário para processar os dados
    document.body.addEventListener('htmx:configRequest', function(evt) {
        if (evt.detail.path === '/api/execucoes/') {
            const form = document.getElementById('mainForm');
            const formData = new FormData(form);
            
            // Coletar nomes dos arquivos
            const fileInput = document.getElementById('fileInput');
            const arquivos = Array.from(fileInput.files).map(f => f.name);
            
            if (arquivos.length === 0) {
                alert('Por favor, selecione ao menos um arquivo HTML.');
                evt.preventDefault();
                return false;
            }
            
            // Coletar dados do formulário
            const numCiclos = parseInt(formData.get('num_ciclos'));
            
            // Construir objeto de configuração
            const config = {
                estilo: formData.get('estilo'),
                id_estilo: formData.get('id_estilo'),
                radical: formData.get('radical'),
                num_ciclos: numCiclos,
                ciclo_1: buildCicloConfig(formData, 1),
            };
            
            // Adicionar ciclo 2 se necessário
            if (numCiclos >= 2) {
                config.ciclo_2 = buildCicloConfig(formData, 2);
            }
            
            // Adicionar ciclo 3 se necessário
            if (numCiclos >= 3) {
                config.ciclo_3 = buildCicloConfig(formData, 3);
            }
            
            // Construir payload final
            const payload = {
                arquivos: arquivos,
                config: config
            };
            
            console.log('Payload enviado:', payload);
            
            // Substituir os parâmetros do HTMX pelo nosso payload JSON
            evt.detail.headers['Content-Type'] = 'application/json';
            evt.detail.parameters = payload;
            
            return true;
        }
    });
    
    // Helper para construir configuração de um ciclo
    function buildCicloConfig(formData, cicloNum) {
        return {
            compositor: {
                primario: formData.get(`ciclo_${cicloNum}.compositor.primario`),
                fallback: formData.get(`ciclo_${cicloNum}.compositor.fallback`)
            },
            revisor_juridico: {
                primario: formData.get(`ciclo_${cicloNum}.revisor_juridico.primario`),
                fallback: formData.get(`ciclo_${cicloNum}.revisor_juridico.fallback`)
            },
            ajustador_juridico: {
                primario: formData.get(`ciclo_${cicloNum}.ajustador_juridico.primario`),
                fallback: formData.get(`ciclo_${cicloNum}.ajustador_juridico.fallback`)
            },
            revisor_linguistico: {
                primario: formData.get(`ciclo_${cicloNum}.revisor_linguistico.primario`),
                fallback: formData.get(`ciclo_${cicloNum}.revisor_linguistico.fallback`)
            },
            ajustador_linguistico: {
                primario: formData.get(`ciclo_${cicloNum}.ajustador_linguistico.primario`),
                fallback: formData.get(`ciclo_${cicloNum}.ajustador_linguistico.fallback`)
            }
        };
    }
    
    // Lidar com a resposta após iniciar execução
    document.body.addEventListener('htmx:afterRequest', function(evt) {
        if (evt.detail.elt.id === 'mainForm' && evt.detail.successful) {
            try {
                const response = JSON.parse(evt.detail.xhr.responseText);
                if (response.execucao_id) {
                    // Redirecionar para a página de monitoramento
                    console.log('Redirecionando para:', `/monitoring/${response.execucao_id}`);
                    window.location.href = `/monitoring/${response.execucao_id}`;
                }
            } catch (e) {
                console.error("Erro ao processar resposta:", e);
                document.getElementById('response-container').innerHTML = 
                    `<div class="p-4 bg-red-50 border border-red-200 rounded-lg">
                        <p class="text-red-800 font-semibold">Erro ao iniciar processamento</p>
                        <p class="text-red-600 text-sm mt-1">${e.message}</p>
                    </div>`;
            }
        } else if (evt.detail.elt.id === 'mainForm' && !evt.detail.successful) {
            // Erro na requisição
            const statusCode = evt.detail.xhr.status;
            let errorMsg = 'Erro desconhecido';
            
            try {
                const errorData = JSON.parse(evt.detail.xhr.responseText);
                errorMsg = errorData.detail || JSON.stringify(errorData);
            } catch (e) {
                errorMsg = evt.detail.xhr.responseText || `Erro HTTP ${statusCode}`;
            }
            
            document.getElementById('response-container').innerHTML = 
                `<div class="p-4 bg-red-50 border border-red-200 rounded-lg">
                    <p class="text-red-800 font-semibold">Erro ${statusCode}: Não foi possível iniciar o processamento</p>
                    <p class="text-red-600 text-sm mt-1">${errorMsg}</p>
                </div>`;
        }
    });
});