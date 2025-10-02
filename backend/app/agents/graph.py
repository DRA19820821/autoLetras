"""Definição do grafo LangGraph para processamento de letras - CORRIGIDO."""
from langgraph.graph import StateGraph, START, END
# CORREÇÃO FINAL: O SqliteSaver foi movido para o pacote 'langgraph.sqlite'.
from langgraph.sqlite import SqliteSaver
from typing import Literal

# CORREÇÃO: Imports ajustados para usar o caminho absoluto do projeto.
from backend.app.agents.nodes import (
    MusicaState,
    node_compositor,
    node_revisor_juridico,
    node_ajustador_juridico,
    node_revisor_linguistico,
    node_ajustador_linguistico,
)
from backend.app.utils.logger import get_logger

logger = get_logger()

MAX_TENTATIVAS_REVISAO = 5


def criar_workflow(num_ciclos: int = 3) -> StateGraph:
    """
    Cria workflow completo de composição com N ciclos.
    """
    workflow = StateGraph(MusicaState)

    # Adicionar nós para cada ciclo
    for ciclo in range(1, num_ciclos + 1):
        workflow.add_node(f"compositor_c{ciclo}", node_compositor)
        workflow.add_node(f"revisor_jur_c{ciclo}", node_revisor_juridico)
        workflow.add_node(f"ajustador_jur_c{ciclo}", node_ajustador_juridico)
        workflow.add_node(f"revisor_ling_c{ciclo}", node_revisor_linguistico)
        workflow.add_node(f"ajustador_ling_c{ciclo}", node_ajustador_linguistico)

    # Definir fluxo para cada ciclo
    for ciclo in range(1, num_ciclos + 1):
        if ciclo == 1:
            workflow.add_edge(START, f"compositor_c{ciclo}")

        workflow.add_edge(f"compositor_c{ciclo}", f"revisor_jur_c{ciclo}")

        # Roteador Jurídico
        def router_juridico(state: MusicaState) -> str:
            tentativas = state.get('tentativas_juridico', 0)
            if state['status_juridico'] == 'aprovado' or tentativas >= MAX_TENTATIVAS_REVISAO:
                return f"revisor_ling_c{state['ciclo_atual']}"
            return f"ajustador_jur_c{state['ciclo_atual']}"

        workflow.add_conditional_edges(
            f"revisor_jur_c{ciclo}",
            router_juridico,
            {
                f"revisor_ling_c{ciclo}": f"revisor_ling_c{ciclo}",
                f"ajustador_jur_c{ciclo}": f"ajustador_jur_c{ciclo}"
            }
        )
        
        # Nó para incrementar tentativas jurídicas
        def incrementador_juridico(state: MusicaState) -> dict:
            return {"tentativas_juridico": state.get('tentativas_juridico', 0) + 1}
        workflow.add_node(f"inc_jur_c{ciclo}", incrementador_juridico)
        workflow.add_edge(f"ajustador_jur_c{ciclo}", f"inc_jur_c{ciclo}")
        workflow.add_edge(f"inc_jur_c{ciclo}", f"revisor_jur_c{ciclo}")


        # Roteador Linguístico
        def router_linguistico(state: MusicaState) -> str:
            ciclo_atual = state['ciclo_atual']
            tentativas = state.get('tentativas_linguistico', 0)
            if state['status_linguistico'] == 'aprovado' or tentativas >= MAX_TENTATIVAS_REVISAO:
                if ciclo_atual >= num_ciclos:
                    return END
                return f"compositor_c{ciclo_atual + 1}"
            return f"ajustador_ling_c{ciclo_atual}"

        mapa_rotas_ling = {f"ajustador_ling_c{ciclo}": f"ajustador_ling_c{ciclo}", END: END}
        if ciclo < num_ciclos:
            mapa_rotas_ling[f"compositor_c{ciclo + 1}"] = f"compositor_c{ciclo + 1}"

        workflow.add_conditional_edges(f"revisor_ling_c{ciclo}", router_linguistico, mapa_rotas_ling)
        
        # Nó para incrementar tentativas linguísticas
        def incrementador_linguistico(state: MusicaState) -> dict:
            return {"tentativas_linguistico": state.get('tentativas_linguistico', 0) + 1}
        workflow.add_node(f"inc_ling_c{ciclo}", incrementador_linguistico)
        workflow.add_edge(f"ajustador_ling_c{ciclo}", f"inc_ling_c{ciclo}")
        workflow.add_edge(f"inc_ling_c{ciclo}", f"revisor_ling_c{ciclo}")

        # Nó para avançar para o próximo ciclo
        def proximo_ciclo(state: MusicaState) -> dict:
            return {
                "ciclo_atual": state['ciclo_atual'] + 1,
                "tentativas_juridico": 0,
                "tentativas_linguistico": 0
            }
        if ciclo < num_ciclos:
             workflow.add_node(f"proximo_ciclo_c{ciclo}", proximo_ciclo)
             workflow.add_edge(f"compositor_c{ciclo + 1}", f"proximo_ciclo_c{ciclo}")


    return workflow


def compilar_workflow(
    num_ciclos: int = 3,
    checkpointer_path: str = "data/checkpoints/checkpoints.db"
):
    """
    Compila workflow com checkpointer.
    """
    workflow = criar_workflow(num_ciclos)
    
    try:
        memory = SqliteSaver.from_conn_string(checkpointer_path)
        app = workflow.compile(checkpointer=memory)
        logger.info("workflow_compiled", num_ciclos=num_ciclos, checkpointer=checkpointer_path)
        return app
        
    except Exception as e:
        logger.error("workflow_compilation_failed", erro=str(e), exc_info=True)
        logger.warning("compiling_without_checkpointer")
        app = workflow.compile()
        return app