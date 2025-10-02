"""Definição do grafo LangGraph para processamento de letras."""
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from typing import Dict
import sqlite3

from backend.app.agents.nodes import MusicaState, node_compositor, node_revisor_juridico, node_ajustador_juridico, node_revisor_linguistico, node_ajustador_linguistico
from backend.app.utils.logger import get_logger

logger = get_logger()

MAX_TENTATIVAS_REVISAO = 5

def criar_workflow(num_ciclos: int = 3) -> StateGraph:
    """
    Cria o workflow completo de composição com N ciclos.
    """
    workflow = StateGraph(MusicaState)

    # Adiciona todos os nós necessários para o número máximo de ciclos
    for ciclo in range(1, num_ciclos + 1):
        workflow.add_node(f"compositor_c{ciclo}", node_compositor)
        workflow.add_node(f"revisor_jur_c{ciclo}", node_revisor_juridico)
        workflow.add_node(f"ajustador_jur_c{ciclo}", node_ajustador_juridico)
        workflow.add_node(f"revisor_ling_c{ciclo}", node_revisor_linguistico)
        workflow.add_node(f"ajustador_ling_c{ciclo}", node_ajustador_linguistico)

    # O ponto de entrada é sempre o compositor do primeiro ciclo
    workflow.add_edge(START, "compositor_c1")

    # Define as conexões e a lógica de roteamento para cada ciclo
    for ciclo in range(1, num_ciclos + 1):
        # Fluxo Padrão
        workflow.add_edge(f"compositor_c{ciclo}", f"revisor_jur_c{ciclo}")
        workflow.add_edge(f"ajustador_jur_c{ciclo}", f"revisor_jur_c{ciclo}")
        workflow.add_edge(f"ajustador_ling_c{ciclo}", f"revisor_ling_c{ciclo}")

        # Roteador após a revisão jurídica
        def router_juridico(state: Dict) -> str:
            tentativas = state.get('tentativas_juridico', 0)
            if state.get('status_juridico') == 'aprovado' or tentativas >= MAX_TENTATIVAS_REVISAO:
                return f"revisor_ling_c{ciclo}"
            return f"ajustador_jur_c{ciclo}"
        
        workflow.add_conditional_edges(f"revisor_jur_c{ciclo}", router_juridico)

        # Roteador após a revisão linguística
        def router_linguistico(state: Dict) -> str:
            tentativas = state.get('tentativas_linguistico', 0)
            if state.get('status_linguistico') == 'aprovado' or tentativas >= MAX_TENTATIVAS_REVISAO:
                if ciclo >= num_ciclos:
                    return END
                return f"compositor_c{ciclo + 1}"
            return f"ajustador_ling_c{ciclo}"

        workflow.add_conditional_edges(f"revisor_ling_c{ciclo}", router_linguistico)

    return workflow

def compilar_workflow(
    num_ciclos: int = 3,
    checkpointer_path: str = "data/checkpoints/checkpoints.db"
):
    """
    Compila o workflow com o checkpointer SQLite.
    """
    workflow = criar_workflow(num_ciclos)
    
    try:
        # Criar conexão SQLite
        conn = sqlite3.connect(checkpointer_path, check_same_thread=False)
        
        # Criar checkpointer usando a conexão
        memory = SqliteSaver(conn)
        
        app = workflow.compile(checkpointer=memory)
        logger.info("workflow_compiled_successfully", num_ciclos=num_ciclos, checkpointer=checkpointer_path)
        return app
        
    except Exception as e:
        logger.error("workflow_compilation_failed", error=str(e), exc_info=True)
        logger.warning("compiling_without_checkpointer_as_fallback")
        app = workflow.compile()
        return app