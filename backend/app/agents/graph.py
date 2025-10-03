"""Definição do grafo LangGraph para processamento de letras."""
from langgraph.graph import StateGraph, START, END
"""Definição do grafo LangGraph para processamento de letras.

Este módulo define a construção do grafo e sua compilação. O grafo
é composto por nós assíncronos (veja `nodes.py`), portanto quando
executado em modo assíncrono (por exemplo com `graph.ainvoke`) o
checkpointer também precisa oferecer operações assíncronas. O
`SqliteSaver` da langgraph suporta apenas métodos síncronos e não
implementa as interfaces assíncronas utilizadas pelo `ainvoke`. Para
suportar execução assíncrona, este módulo oferece a função
`compilar_workflow_async` que usa o `AsyncSqliteSaver` em conjunto
com `aiosqlite`.

Para compatibilidade com chamadas síncronas, a função
`compilar_workflow` continua presente e utiliza o `SqliteSaver` para
montar o grafo com checkpoint síncrono. Se o grafo for executado
através de métodos assíncronos (`ainvoke` ou `astream`), use
`compilar_workflow_async`.
"""

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import aiosqlite
from typing import Dict
import sqlite3

from backend.app.agents.nodes import MusicaState, node_compositor, node_revisor_juridico, node_ajustador_juridico, node_revisor_linguistico, node_ajustador_linguistico
from backend.app.utils.logger import get_logger

logger = get_logger()

MAX_TENTATIVAS_REVISAO = 6

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
    checkpointer_path: str = "data/checkpoints/checkpoints.db",
) -> "langgraph.pregel.main.PregelGraph":
    """
    Compila o workflow usando um checkpointer SQLite síncrono.

    Esta função mantém compatibilidade com código existente que utiliza
    chamadas síncronas (por exemplo `graph.invoke`). Ela constrói o
    grafo e utiliza o `SqliteSaver` para persistir checkpoints de
    forma síncrona. Se você pretende executar o grafo de forma
    assíncrona (com `ainvoke`), use `compilar_workflow_async` em vez
    desta função.

    Parâmetros:
        num_ciclos: quantidade de ciclos de revisão.
        checkpointer_path: caminho para o arquivo SQLite de
            persistência de checkpoints.

    Retorna:
        Instância compilada do grafo.
    """
    workflow = criar_workflow(num_ciclos)
    try:
        conn = sqlite3.connect(checkpointer_path, check_same_thread=False)
        memory = SqliteSaver(conn)
        app = workflow.compile(checkpointer=memory)
        logger.info(
            "workflow_compiled_successfully",
            num_ciclos=num_ciclos,
            checkpointer=checkpointer_path,
        )
        return app
    except Exception as e:
        logger.error(
            "workflow_compilation_failed", error=str(e), exc_info=True
        )
        logger.warning("compiling_without_checkpointer_as_fallback")
        return workflow.compile()


async def compilar_workflow_async(
    num_ciclos: int = 3,
    checkpointer_path: str = "data/checkpoints/checkpoints.db",
) -> "langgraph.pregel.main.PregelGraph":
    """
    Compila o workflow utilizando um checkpointer SQLite assíncrono.

    Esta função deve ser utilizada quando o grafo será executado por
    métodos assíncronos como `ainvoke` ou `astream`. Ela abre uma
    conexão com o banco de dados via `aiosqlite` e cria um
    `AsyncSqliteSaver`, que implementa as interfaces assíncronas
    necessárias.

    Parâmetros:
        num_ciclos: quantidade de ciclos de revisão.
        checkpointer_path: caminho para o arquivo SQLite de
            persistência de checkpoints.

    Retorna:
        Instância compilada do grafo.
    """
    workflow = criar_workflow(num_ciclos)
    try:
        async with aiosqlite.connect(checkpointer_path) as conn:
            memory = AsyncSqliteSaver(conn)
            app = workflow.compile(checkpointer=memory)
            logger.info(
                "workflow_compiled_successfully",
                num_ciclos=num_ciclos,
                checkpointer=checkpointer_path,
            )
            return app
    except Exception as e:
        logger.error(
            "workflow_compilation_failed", error=str(e), exc_info=True
        )
        logger.warning("compiling_without_checkpointer_as_fallback")
        return workflow.compile()