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

    // Interceptar o submit do formulário
    const mainForm = document.getElementById('mainForm');
    if (mainForm) {
        mainForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const submitBtn = document.getElementById('submitBtn');
            const responseContainer = document.getElementById('response-container');
            
            // Desabilitar botão
            submitBtn.disabled = true;
            submitBtn.innerHTML = '⏳ Processando...';
            
            try {
                // Coletar arquivos
                const fileInput = document.getElementById('fileInput');
                const arquivos = Array.from(fileInput.files).map(f => f.name);
                
                if (arquivos.length === 0) {
                    throw new Error('Por favor, selecione ao menos um arquivo HTML.');
                }
                
                // Coletar dados do formulário
                const formData = new FormData(mainForm);
                const numCiclos = parseInt(document.getElementById('numCiclosSelect').value);
                
                // Construir payload
                const payload = {
                    arquivos: arquivos,
                    config: {
                        estilo: document.getElementById('estilo').value,
                        id_estilo: document.getElementById('id_estilo').value,
                        radical: document.getElementById('radical').value,
                        num_ciclos: numCiclos,
                        ciclo_1: buildCicloConfig(1),
                    }
                };
                
                // Adicionar ciclos adicionais
                if (numCiclos >= 2) {
                    payload.config.ciclo_2 = buildCicloConfig(2);
                }
                if (numCiclos >= 3) {
                    payload.config.ciclo_3 = buildCicloConfig(3);
                }
                
                console.log('Enviando payload:', payload);
                
                // Enviar via fetch
                const response = await fetch('/api/execucoes/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(payload)
                });
                
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || `Erro HTTP ${response.status}`);
                }
                
                const data = await response.json();
                console.log('Resposta:', data);
                
                if (data.execucao_id) {
                    // Redirecionar para monitoramento
                    window.location.href = `/monitoring/${data.execucao_id}`;
                } else {
                    throw new Error('ID de execução não recebido');
                }
                
            } catch (error) {
                console.error('Erro:', error);
                responseContainer.innerHTML = `
                    <div class="p-4 bg-red-50 border border-red-200 rounded-lg mb-4">
                        <p class="text-red-800 font-semibold">❌ Erro ao iniciar processamento</p>
                        <p class="text-red-600 text-sm mt-1">${error.message}</p>
                    </div>
                `;
                
                // Reabilitar botão
                submitBtn.disabled = false;
                submitBtn.innerHTML = '🚀 Iniciar Processamento';
            }
        });
    }
    
    // Helper para construir configuração de um ciclo
    function buildCicloConfig(cicloNum) {
        return {
            compositor: {
                primario: getSelectValue(`ciclo_${cicloNum}_compositor_primario`),
                fallback: getSelectValue(`ciclo_${cicloNum}_compositor_fallback`)
            },
            revisor_juridico: {
                primario: getSelectValue(`ciclo_${cicloNum}_revisor_juridico_primario`),
                fallback: getSelectValue(`ciclo_${cicloNum}_revisor_juridico_fallback`)
            },
            ajustador_juridico: {
                primario: getSelectValue(`ciclo_${cicloNum}_ajustador_juridico_primario`),
                fallback: getSelectValue(`ciclo_${cicloNum}_ajustador_juridico_fallback`)
            },
            revisor_linguistico: {
                primario: getSelectValue(`ciclo_${cicloNum}_revisor_linguistico_primario`),
                fallback: getSelectValue(`ciclo_${cicloNum}_revisor_linguistico_fallback`)
            },
            ajustador_linguistico: {
                primario: getSelectValue(`ciclo_${cicloNum}_ajustador_linguistico_primario`),
                fallback: getSelectValue(`ciclo_${cicloNum}_ajustador_linguistico_fallback`)
            }
        };
    }
    
    // Helper para pegar valor de select
    function getSelectValue(name) {
        const element = document.querySelector(`[name="${name}"]`);
        if (!element) {
            console.error(`Select não encontrado: ${name}`);
            return null;
        }
        return element.value;
    }
});