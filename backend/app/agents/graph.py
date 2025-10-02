"""Definição do grafo LangGraph para processamento de letras - CORRIGIDO."""
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from typing import Literal

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
        StateGraph configurado (não compilado)
    """
    workflow = StateGraph(MusicaState)
    
    # Adicionar nós para cada ciclo
    for ciclo in range(1, num_ciclos + 1):
        # Compositor
        workflow.add_node(f"compositor_c{ciclo}", node_compositor)
        
        # Revisor jurídico
        workflow.add_node(f"revisor_jur_c{ciclo}", node_revisor_juridico)
        
        # Ajustador jurídico
        workflow.add_node(f"ajustador_jur_c{ciclo}", node_ajustador_juridico)
        
        # Revisor linguístico
        workflow.add_node(f"revisor_ling_c{ciclo}", node_revisor_linguistico)
        
        # Ajustador linguístico
        workflow.add_node(f"ajustador_ling_c{ciclo}", node_ajustador_linguistico)
    
    # Definir fluxo para cada ciclo
    for ciclo in range(1, num_ciclos + 1):
        if ciclo == 1:
            # Primeiro ciclo começa no compositor
            workflow.add_edge(START, f"compositor_c{ciclo}")
        else:
            # Ciclos subsequentes vêm do ajuste linguístico do ciclo anterior
            # (que só é alcançado se ainda houver ciclos)
            pass
        
        # Fluxo dentro do ciclo
        # Compositor → Revisor Jurídico
        workflow.add_edge(f"compositor_c{ciclo}", f"revisor_jur_c{ciclo}")
        
        # Revisor Jurídico → Decisão (aprovar ou ajustar)
        def criar_router_juridico(ciclo_atual: int):
            """Cria roteador para loop jurídico de um ciclo específico."""
            def router(state: MusicaState) -> Literal[str]:
                """Roteador para loop jurídico."""
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
            
            return router
        
        workflow.add_conditional_edges(
            f"revisor_jur_c{ciclo}",
            criar_router_juridico(ciclo),
            [f"ajustador_jur_c{ciclo}", f"revisor_ling_c{ciclo}"]
        )
        
        # Ajustador Jurídico → Incrementar contador e voltar ao Revisor
        def criar_incrementador_juridico(ciclo_atual: int):
            """Cria função para incrementar tentativas jurídicas."""
            async def incrementar(state: MusicaState) -> MusicaState:
                state['tentativas_juridico'] += 1
                state['ciclo_atual'] = ciclo_atual
                return state
            return incrementar
        
        workflow.add_node(
            f"inc_jur_c{ciclo}",
            criar_incrementador_juridico(ciclo)
        )
        
        workflow.add_edge(f"ajustador_jur_c{ciclo}", f"inc_jur_c{ciclo}")
        workflow.add_edge(f"inc_jur_c{ciclo}", f"revisor_jur_c{ciclo}")
        
        # Revisor Linguístico → Decisão (aprovar, ajustar ou próximo ciclo)
        def criar_router_linguistico(ciclo_atual: int, total_ciclos: int):
            """Cria roteador para loop linguístico de um ciclo específico."""
            def router(state: MusicaState) -> Literal[str]:
                """Roteador para loop linguístico."""
                status = state['status_linguistico']
                tentativas = state['tentativas_linguistico']
                
                # Se aprovado ou esgotou tentativas
                if status == 'aprovado' or tentativas >= MAX_TENTATIVAS_REVISAO:
                    # Último ciclo → finalizar
                    if ciclo_atual >= total_ciclos:
                        return END
                    # Ainda tem ciclos → próximo ciclo
                    return f"compositor_c{ciclo_atual + 1}"
                
                # Falha crítica
                if status == 'falha':
                    logger.warning(
                        "linguistico_falha_critica",
                        ciclo=ciclo_atual
                    )
                    if ciclo_atual >= total_ciclos:
                        return END
                    return f"compositor_c{ciclo_atual + 1}"
                
                # Reprovado e ainda tem tentativas → ajustar
                return f"ajustador_ling_c{ciclo_atual}"
            
            return router
        
        # Opções possíveis de roteamento
        opcoes_routing = [f"ajustador_ling_c{ciclo}"]
        if ciclo < num_ciclos:
            opcoes_routing.append(f"compositor_c{ciclo + 1}")
        else:
            opcoes_routing.append(END)
        
        workflow.add_conditional_edges(
            f"revisor_ling_c{ciclo}",
            criar_router_linguistico(ciclo, num_ciclos),
            opcoes_routing
        )
        
        # Ajustador Linguístico → Incrementar e voltar
        def criar_incrementador_linguistico(ciclo_atual: int):
            """Cria função para incrementar tentativas linguísticas."""
            async def incrementar(state: MusicaState) -> MusicaState:
                state['tentativas_linguistico'] += 1
                state['ciclo_atual'] = ciclo_atual
                return state
            return incrementar
        
        workflow.add_node(
            f"inc_ling_c{ciclo}",
            criar_incrementador_linguistico(ciclo)
        )
        
        workflow.add_edge(f"ajustador_ling_c{ciclo}", f"inc_ling_c{ciclo}")
        workflow.add_edge(f"inc_ling_c{ciclo}", f"revisor_ling_c{ciclo}")
    
    return workflow


def compilar_workflow(
    num_ciclos: int = 3,
    checkpointer_path: str = "data/checkpoints/checkpoints.db"
):
    """
    Compila workflow com checkpointer.
    
    Args:
        num_ciclos: Número de ciclos
        checkpointer_path: Caminho para banco SQLite
        
    Returns:
        Workflow compilado pronto para uso
    """
    workflow = criar_workflow(num_ciclos)
    
    # Configurar checkpointer com conexão síncrona
    # IMPORTANTE: SqliteSaver.from_conn_string retorna um context manager
    # que precisa ser usado corretamente
    try:
        # Criar checkpointer de forma síncrona
        from sqlite3 import connect
        
        # Garantir que o diretório existe
        import os
        os.makedirs(os.path.dirname(checkpointer_path), exist_ok=True)
        
        # Criar conexão
        conn = connect(checkpointer_path)
        checkpointer = SqliteSaver(conn)
        
        # Compilar
        app = workflow.compile(checkpointer=checkpointer)
        
        logger.info(
            "workflow_compiled",
            num_ciclos=num_ciclos,
            checkpointer=checkpointer_path
        )
        
        return app
        
    except Exception as e:
        logger.error("workflow_compilation_failed", erro=str(e))
        # Se falhar, compilar sem checkpointer
        logger.warning("compiling_without_checkpointer")
        app = workflow.compile()
        return app