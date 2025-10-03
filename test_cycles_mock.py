#!/usr/bin/env python3
"""
Teste MOCK dos ciclos - não requer API keys.
Simula os nós para testar apenas a lógica do grafo.
Execute: python test_cycles_mock.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from langgraph.graph import StateGraph, START, END
from backend.app.api.schemas import MusicaState

# Mock dos nós - retornam diretamente sem chamar LLM
async def mock_compositor(state: MusicaState) -> dict:
    ciclo = state['ciclo_atual']
    print(f"  📝 Compositor (Ciclo {ciclo})")
    return {
        "letra_atual": f"Letra gerada no ciclo {ciclo}",
        "status_juridico": "pendente",
        "tentativas_juridico": 0,
        "status_linguistico": "pendente",
        "tentativas_linguistico": 0,
    }

async def mock_revisor_juridico(state: MusicaState) -> dict:
    ciclo = state['ciclo_atual']
    print(f"  ⚖️  Revisor Jurídico (Ciclo {ciclo})")
    # Sempre aprovar para seguir em frente
    return {"status_juridico": "aprovado", "problemas_juridicos": []}

async def mock_revisor_linguistico(state: MusicaState) -> dict:
    ciclo = state['ciclo_atual']
    print(f"  📖 Revisor Linguístico (Ciclo {ciclo})")
    
    # Verificar quantos ciclos existem
    num_ciclos_total = len([k for k in state['config'].keys() if k.startswith('ciclo_')])
    
    updates = {
        "status_linguistico": "aprovado",
        "problemas_linguisticos": [],
    }
    
    # Só incrementar se não for o último ciclo
    if ciclo < num_ciclos_total:
        updates["ciclo_atual"] = ciclo + 1
    
    return updates

def criar_workflow_mock(num_ciclos: int = 3) -> StateGraph:
    """Cria workflow mock para teste."""
    workflow = StateGraph(MusicaState)

    # Adicionar nós
    for ciclo in range(1, num_ciclos + 1):
        workflow.add_node(f"compositor_c{ciclo}", mock_compositor)
        workflow.add_node(f"revisor_jur_c{ciclo}", mock_revisor_juridico)
        workflow.add_node(f"revisor_ling_c{ciclo}", mock_revisor_linguistico)

    # Entrada
    workflow.add_edge(START, "compositor_c1")

    # Conexões
    for ciclo in range(1, num_ciclos + 1):
        workflow.add_edge(f"compositor_c{ciclo}", f"revisor_jur_c{ciclo}")
        workflow.add_edge(f"revisor_jur_c{ciclo}", f"revisor_ling_c{ciclo}")
        
        # Roteador linguístico
        def make_router(current_ciclo: int, total: int):
            def router(state):
                if current_ciclo >= total:
                    return END
                return f"compositor_c{current_ciclo + 1}"
            return router
        
        workflow.add_conditional_edges(
            f"revisor_ling_c{ciclo}",
            make_router(ciclo, num_ciclos)
        )

    return workflow

async def test_mock():
    """Testa workflow mock."""
    print("\n" + "=" * 60)
    print("🧪 TESTE MOCK DOS CICLOS (sem API keys)")
    print("=" * 60)
    
    # Criar e compilar
    workflow = criar_workflow_mock(num_ciclos=3)
    app = workflow.compile()
    
    # Estado inicial
    initial_state = {
        "arquivo": "teste.html",
        "tema": "Teste",
        "topico": "Mock Test",
        "conteudo": "Conteúdo de teste",
        "estilo": "funk",
        "ciclo_atual": 1,
        "letra_atual": "",
        "status_juridico": "pendente",
        "status_linguistico": "pendente",
        "config": {"ciclo_1": {}, "ciclo_2": {}, "ciclo_3": {}},
        "problemas_juridicos": [],
        "problemas_linguisticos": [],
        "tentativas_juridico": 0,
        "tentativas_linguistico": 0,
        "metricas": {}
    }
    
    print("\n🔄 Executando workflow com 3 ciclos...\n")
    
    ciclos_detectados = [1]  # Iniciar com ciclo 1 já detectado
    print("✅ Ciclo 1 iniciado (estado inicial)")
    resultado = None
    
    async for state in app.astream(initial_state):
        if isinstance(state, dict):
            for key, value in state.items():
                resultado = value
                if isinstance(value, dict) and 'ciclo_atual' in value:
                    ciclo = value['ciclo_atual']
                    # Só adicionar se for novo E dentro do limite esperado
                    if ciclo not in ciclos_detectados and ciclo <= 3:
                        ciclos_detectados.append(ciclo)
                        print(f"\n✅ Ciclo {ciclo} iniciado")
    
    print("\n" + "=" * 60)
    print("RESULTADO")
    print("=" * 60)
    print(f"Ciclos detectados: {sorted(ciclos_detectados)}")
    print(f"Ciclos esperados:  [1, 2, 3]")
    
    if resultado:
        print(f"\nEstado final:")
        print(f"  - Ciclo atual: {resultado.get('ciclo_atual', 'N/A')}")
        print(f"  - Letra: {resultado.get('letra_atual', 'N/A')[:50]}...")
    
    print("=" * 60)
    
    # Verificar sucesso
    success = len(ciclos_detectados) >= 3 and 1 in ciclos_detectados and 2 in ciclos_detectados and 3 in ciclos_detectados
    
    if success:
        print("\n✅ SUCESSO! Lógica dos ciclos está correta!")
        print("\nAgora você pode testar com API keys reais:")
        print("  python test_multiple_cycles.py")
        return True
    else:
        print(f"\n❌ FALHA! Ciclos detectados: {ciclos_detectados}")
        return False

def main():
    """Main."""
    import asyncio
    try:
        success = asyncio.run(test_mock())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()