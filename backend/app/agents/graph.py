"""Definição do grafo LangGraph para processamento de letras."""
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from app.agents.nodes import (
    MusicaState,
    node_compositor,
    node_revisor_juridico,
    node_ajustador_juridico,
    node_revisor_linguistico,
    node_ajustador_linguistico,
)
from app.utils.logger import get_logger

logger = get_logger()

MAX_TENTATIVAS_REVISAO = 5


def criar_workflow(num_ciclos: int = 3) -> StateGraph:
    """
    Cria workflow completo de composição com N ciclos.
    
    Args:
        num_ciclos: Número de ciclos a executar (1-3)
        
    Returns:
        StateGraph compilado
    """
    workflow = StateGraph(MusicaState)
    
    # Adicionar nós para cada ciclo
    for ciclo in range(1, num_ciclos + 1):
        # Compositor
        workflow.add_node(f"compositor_c{ciclo}", node_compositor)
        
        # Revisor jurídico
        workflow.add_node(f"revisor_jur_c{ciclo}", node_revisor_juridico)
        
        # Decisor jurídico
        workflow.add_node(
            f"decisor_jur_c{ciclo}",
            lambda state: decisor_juridico(state, ciclo)
        )
        
        # Ajustador jurídico
        workflow.add_node(f"ajustador_jur_c{ciclo}", node_ajustador_juridico)
        
        # Revisor linguístico
        workflow.add_node(f"revisor_ling_c{ciclo}", node_revisor_linguistico)
        
        # Decisor linguístico
        workflow.add_node(
            f"decisor_ling_c{ciclo}",
            lambda state: decisor_linguistico(state, ciclo)
        )
        
        # Ajustador linguístico
        workflow.add_node(f"ajustador_ling_c{ciclo}", node_ajustador_linguistico)
    
    # Definir fluxo para cada ciclo
    for ciclo in range(1, num_ciclos + 1):
        if ciclo == 1:
            # Primeiro ciclo começa no compositor
            workflow.add_edge(START, f"compositor_c{ciclo}")
        else:
            # Ciclos subsequentes vêm do ciclo anterior
            workflow.add_edge(
                f"decisor_ling_c{ciclo-1}",
                f"compositor_c{ciclo}"
            )
        
        # Fluxo dentro do ciclo
        # Compositor → Revisor Jurídico
        workflow.add_edge(f"compositor_c{ciclo}", f"revisor_jur_c{ciclo}")
        
        # Revisor Jurídico → Decisor Jurídico
        workflow.add_edge(f"revisor_jur_c{ciclo}", f"decisor_jur_c{ciclo}")
        
        # Decisor Jurídico: loop ou prosseguir
        def router_juridico(state: MusicaState):
            """Roteador para loop jurídico."""
            ciclo_atual = state['ciclo_atual']
            status = state['status_juridico']
            tentativas = state['tentativas_juridico']
            
            # Se aprovado ou esgotou tentativas → prosseguir
            if status == 'aprovado' or tentativas >= MAX_TENTATIVAS_REVISAO:
                return f"revisor_ling_c{ciclo_atual}"
            
            # Se falha crítica → prosseguir mesmo assim
            if status == 'falha':
                logger.warning(
                    "juridico_falha_critica",
                    ciclo=ciclo_atual,
                    msg="Prosseguindo com letra atual"
                )
                return f"revisor_ling_c{ciclo_atual}"
            
            # Reprovado e ainda tem tentativas → ajustar
            return f"ajustador_jur_c{ciclo_atual}"
        
        workflow.add_conditional_edges(
            f"decisor_jur_c{ciclo}",
            router_juridico
        )
        
        # Ajustador Jurídico → Incrementar contador e voltar ao Revisor
        def incrementar_juridico(state: MusicaState):
            state['tentativas_juridico'] += 1
            return state
        
        workflow.add_node(
            f"inc_jur_c{ciclo}",
            incrementar_juridico
        )
        
        workflow.add_edge(f"ajustador_jur_c{ciclo}", f"inc_jur_c{ciclo}")
        workflow.add_edge(f"inc_jur_c{ciclo}", f"revisor_jur_c{ciclo}")
        
        # Revisor Linguístico → Decisor Linguístico
        workflow.add_edge(f"revisor_ling_c{ciclo}", f"decisor_ling_c{ciclo}")
        
        # Decisor Linguístico: loop ou prosseguir
        def router_linguistico(state: MusicaState):
            """Roteador para loop linguístico."""
            ciclo_atual = state['ciclo_atual']
            status = state['status_linguistico']
            tentativas = state['tentativas_linguistico']
            
            # Se aprovado ou esgotou tentativas
            if status == 'aprovado' or tentativas >= MAX_TENTATIVAS_REVISAO:
                # Último ciclo → finalizar
                if ciclo_atual >= num_ciclos:
                    return END
                # Ainda tem ciclos → próximo ciclo
                return f"compositor_c{ciclo_atual + 1}"
            
            # Falha crítica
            if status == 'falha':
                logger.warning(
                    "linguistico_falha_critica",
                    ciclo=ciclo_atual
                )
                if ciclo_atual >= num_ciclos:
                    return END
                return f"compositor_c{ciclo_atual + 1}"
            
            # Reprovado e ainda tem tentativas → ajustar
            return f"ajustador_ling_c{ciclo_atual}"
        
        workflow.add_conditional_edges(
            f"decisor_ling_c{ciclo}",
            router_linguistico
        )
        
        # Ajustador Linguístico → Incrementar e voltar
        def incrementar_linguistico(state: MusicaState):
            state['tentativas_linguistico'] += 1
            return state
        
        workflow.add_node(
            f"inc_ling_c{ciclo}",
            incrementar_linguistico
        )
        
        workflow.add_edge(f"ajustador_ling_c{ciclo}", f"inc_ling_c{ciclo}")
        workflow.add_edge(f"inc_ling_c{ciclo}", f"revisor_ling_c{ciclo}")
    
    return workflow


def decisor_juridico(state: MusicaState, ciclo: int) -> MusicaState:
    """
    Nó decisor para loop jurídico.
    Apenas prepara estado, routing é feito pelo router.
    """
    # O routing real é feito pela função condicional
    # Este nó apenas garante que o estado está pronto
    return state


def decisor_linguistico(state: MusicaState, ciclo: int) -> MusicaState:
    """
    Nó decisor para loop linguístico.
    """
    return state


def compilar_workflow(
    num_ciclos: int = 3,
    checkpointer_path: str = "data/checkpoints/checkpoints.db"
) -> StateGraph:
    """
    Compila workflow com checkpointer.
    
    Args:
        num_ciclos: Número de ciclos
        checkpointer_path: Caminho para banco SQLite
        
    Returns:
        Workflow compilado pronto para uso
    """
    workflow = criar_workflow(num_ciclos)
    
    # Configurar checkpointer
    checkpointer = SqliteSaver.from_conn_string(checkpointer_path)
    
    # Compilar
    app = workflow.compile(checkpointer=checkpointer)
    
    logger.info(
        "workflow_compiled",
        num_ciclos=num_ciclos,
        checkpointer=checkpointer_path
    )
    
    return app