// Gerenciamento de upload e formulário
let selectedFiles = [];

document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('fileInput');
    const filesList = document.getElementById('filesList');
    const filesContainer = document.getElementById('filesContainer');
    const mainForm = document.getElementById('mainForm');
    const numCiclosRadios = document.querySelectorAll('input[name="numCiclos"]');
    
    // Upload de arquivos
    fileInput.addEventListener('change', async function(e) {
        const files = Array.from(e.target.files).slice(0, 15);
        
        if (files.length === 0) return;
        
        selectedFiles = files;
        
        // Upload para servidor
        const formData = new FormData();
        files.forEach(file => formData.append('files', file));
        
        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            // Mostrar arquivos validados
            filesContainer.innerHTML = data.arquivos.map(arq => {
                const statusIcon = arq.valido ? '✓' : '✗';
                const statusColor = arq.valido ? 'text-green-600' : 'text-red-600';
                const bgColor = arq.valido ? 'bg-green-50' : 'bg-red-50';
                
                return `
                    <div class="${bgColor} border rounded p-3">
                        <div class="flex items-start space-x-2">
                            <span class="${statusColor} text-xl">${statusIcon}</span>
                            <div class="flex-1">
                                <p class="font-medium">${arq.arquivo}</p>
                                ${arq.valido ? `
                                    <p class="text-sm text-gray-600">
                                        <span class="font-medium">Tema:</span> ${arq.tema}<br>
                                        <span class="font-medium">Tópico:</span> ${arq.topico}
                                    </p>
                                    ${arq.avisos.length > 0 ? `
                                        <div class="mt-1 text-sm text-yellow-700">
                                            ${arq.avisos.map(a => `⚠ ${a}`).join('<br>')}
                                        </div>
                                    ` : ''}
                                ` : `
                                    <p class="text-sm text-red-600">Erro: ${arq.erro}</p>
                                `}
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
            
            filesList.classList.remove('hidden');
            
        } catch (error) {
            alert('Erro ao fazer upload dos arquivos: ' + error.message);
        }
    });
    
    // Controle de ciclos visíveis
    numCiclosRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            const numCiclos = parseInt(this.value);
            
            for (let i = 1; i <= 3; i++) {
                const cicloDiv = document.getElementById(`ciclo${i}`);
                if (i <= numCiclos) {
                    cicloDiv.classList.remove('hidden');
                } else {
                    cicloDiv.classList.add('hidden');
                }
            }
        });
    });
    
    // Submit do formulário
    mainForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        if (selectedFiles.length === 0) {
            alert('Selecione ao menos um arquivo HTML');
            return;
        }
        
        // Coletar configuração
        const numCiclos = parseInt(document.querySelector('input[name="numCiclos"]:checked').value);
        const estilo = document.getElementById('estilo').value;
        const idEstilo = document.getElementById('idEstilo').value;
        const radical = document.getElementById('radical').value;
        
        // Montar configuração de modelos
        const config = {
            estilo,
            id_estilo: idEstilo,
            radical,
            num_ciclos: numCiclos,
        };
        
        // Coletar configuração de cada ciclo
        for (let i = 1; i <= numCiclos; i++) {
            config[`ciclo_${i}`] = {
                compositor: {
                    primario: document.getElementById(`c${i}_comp_pri`).value,
                    fallback: document.getElementById(`c${i}_comp_fall`).value
                },
                revisor_juridico: {
                    primario: document.getElementById(`c${i}_revj_pri`).value,
                    fallback: document.getElementById(`c${i}_revj_fall`).value
                },
                ajustador_juridico: {
                    primario: document.getElementById(`c${i}_ajuj_pri`).value,
                    fallback: document.getElementById(`c${i}_ajuj_fall`).value
                },
                revisor_linguistico: {
                    primario: document.getElementById(`c${i}_revl_pri`).value,
                    fallback: document.getElementById(`c${i}_revl_fall`).value
                },
                ajustador_linguistico: {
                    primario: document.getElementById(`c${i}_ajul_pri`).value,
                    fallback: document.getElementById(`c${i}_ajul_fall`).value
                }
            };
        }
        
        const payload = {
            arquivos: selectedFiles.map(f => f.name),
            config: config
        };
        
        try {
            const response = await fetch('/api/execucoes/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });
            
            const data = await response.json();
            
            // Redirecionar para página de monitoramento
            window.location.href = `/monitoring?execucao_id=${data.execucao_id}`;
            
        } catch (error) {
            alert('Erro ao iniciar processamento: ' + error.message);
        }
    });
});