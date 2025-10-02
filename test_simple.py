#!/usr/bin/env python3
"""
Teste simples do workflow SEM checkpointer.
Execute: python test_simple.py

Isso testa o workflow básico sem SQLite.
"""
import asyncio
import sys
from pathlib import Path

# Adicionar backend ao path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from dotenv import load_dotenv
load_dotenv()

from app.agents.graph import criar_workflow
from app.retry.throttler import init_throttler
from app.utils.logger import setup_logging, get_logger

async def test_workflow():
    """Testa workflow básico."""
    
    # Setup logging
    setup_logging(
        Path("data/logs/test"),
        "test",
        formato="legivel",
        nivel="INFO"
    )
    
    logger = get_logger()
    
    # Inicializar throttler
    init_throttler({
        "openai": 5,
        "anthropic": 5,
        "google": 8,
        "deepseek": 3
    })
    
    logger.info("test_starting")
    
    # Criar workflow SEM checkpointer
    workflow_graph = criar_workflow(num_ciclos=1)
    
    # Compilar SEM checkpointer
    logger.info("compiling_workflow")
    app = workflow_graph.compile()
    
    logger.info("workflow_compiled")
    
    # Estado inicial simples
    initial_state = {
        "arquivo": "teste.html",
        "tema": "Direito Constitucional",
        "topico": "Teste Simples",
        "conteudo": "Este é um teste simples do sistema. Direitos fundamentais são essenciais.",
        "estilo": "funk brasileiro",
        "ciclo_atual": 1,
        "etapa_atual": "compositor",
        "letra_atual": "",
        "letra_anterior": None,
        "problemas_juridicos": [],
        "problemas_linguisticos": [],
        "tentativas_juridico": 0,
        "tentativas_linguistico": 0,
        "status_juridico": "pendente",
        "status_linguistico": "pendente",
        "config": {
            "ciclo_1": {
                "compositor": {
                    "primario": "gpt-4-turbo",
                    "fallback": "claude-sonnet-4"
                },
                "revisor_juridico": {
                    "primario": "gpt-4-turbo",
                    "fallback": "claude-sonnet-4"
                },
                "ajustador_juridico": {
                    "primario": "claude-sonnet-4",
                    "fallback": "gpt-4-turbo"
                },
                "revisor_linguistico": {
                    "primario": "gemini-pro",
                    "fallback": "gpt-4-turbo"
                },
                "ajustador_linguistico": {
                    "primario": "gemini-pro",
                    "fallback": "gpt-4-turbo"
                }
            }
        },
        "metricas": {}
    }
    
    logger.info("starting_workflow_execution")
    
    try:
        # Executar workflow com recursion_limit aumentado
        resultado = await app.ainvoke(
            initial_state,
            config={"recursion_limit": 100}  # Aumentar limite de recursão
        )
        
        logger.info("workflow_completed")
        
        # Mostrar resultado
        print("\n" + "=" * 60)
        print("RESULTADO DO TESTE")
        print("=" * 60)
        print(f"\nLetra gerada ({len(resultado['letra_atual'])} caracteres):")
        print("\n" + resultado['letra_atual'][:500] + "...")
        print("\n" + "=" * 60)
        print(f"Status Jurídico: {resultado['status_juridico']}")
        print(f"Status Linguístico: {resultado['status_linguistico']}")
        print(f"Tentativas Jurídicas: {resultado['tentativas_juridico']}")
        print(f"Tentativas Linguísticas: {resultado['tentativas_linguistico']}")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error("workflow_failed", erro=str(e))
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Função principal."""
    print("\n🧪 TESTE SIMPLES DO WORKFLOW")
    print("=" * 60)
    print("Este teste executa 1 ciclo SEM checkpointer")
    print("=" * 60)
    print()
    
    try:
        success = asyncio.run(test_workflow())
        
        if success:
            print("\n✅ Teste concluído com sucesso!")
        else:
            print("\n❌ Teste falhou")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Teste interrompido")
    except Exception as e:
        print(f"\n❌ Erro no teste: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()