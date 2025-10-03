#!/usr/bin/env python3
"""
Script para testar múltiplos ciclos.
Execute: python test_multiple_cycles.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))

from dotenv import load_dotenv
load_dotenv()

from app.agents.graph import criar_workflow
from app.retry.throttler import init_throttler
from app.utils.logger import setup_logging, get_logger

async def test_multi_cycle():
    """Testa workflow com 3 ciclos."""
    
    setup_logging(
        Path("data/logs/test"),
        "test_multi_cycle",
        formato="legivel",
        nivel="INFO"
    )
    
    logger = get_logger()
    
    init_throttler({
        "openai": 5,
        "anthropic": 5,
        "google": 8,
        "deepseek": 3
    })
    
    logger.info("test_starting", num_ciclos=3)
    
    # Criar workflow com 3 ciclos
    workflow_graph = criar_workflow(num_ciclos=3)
    app = workflow_graph.compile()
    
    logger.info("workflow_compiled")
    
    # Estado inicial
    initial_state = {
        "arquivo": "teste_3_ciclos.html",
        "tema": "Direito Constitucional",
        "topico": "Teste Múltiplos Ciclos",
        "conteudo": "Teste de múltiplos ciclos. Os direitos fundamentais são a base do ordenamento.",
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
                "compositor": {"primario": "gpt-4-turbo", "fallback": "claude-sonnet-4"},
                "revisor_juridico": {"primario": "gpt-4-turbo", "fallback": "claude-sonnet-4"},
                "ajustador_juridico": {"primario": "claude-sonnet-4", "fallback": "gpt-4-turbo"},
                "revisor_linguistico": {"primario": "gemini-pro", "fallback": "gpt-4-turbo"},
                "ajustador_linguistico": {"primario": "gemini-pro", "fallback": "gpt-4-turbo"}
            },
            "ciclo_2": {
                "compositor": {"primario": "claude-sonnet-4", "fallback": "gpt-4-turbo"},
                "revisor_juridico": {"primario": "claude-opus-4", "fallback": "gpt-4-turbo"},
                "ajustador_juridico": {"primario": "claude-sonnet-4", "fallback": "gpt-4-turbo"},
                "revisor_linguistico": {"primario": "gemini-pro", "fallback": "gpt-4-turbo"},
                "ajustador_linguistico": {"primario": "gemini-pro", "fallback": "gpt-4-turbo"}
            },
            "ciclo_3": {
                "compositor": {"primario": "claude-opus-4", "fallback": "gpt-4-turbo"},
                "revisor_juridico": {"primario": "claude-opus-4", "fallback": "gpt-4-turbo"},
                "ajustador_juridico": {"primario": "claude-sonnet-4", "fallback": "gpt-4-turbo"},
                "revisor_linguistico": {"primario": "gemini-2.5-pro", "fallback": "gpt-4-turbo"},
                "ajustador_linguistico": {"primario": "gemini-2.5-flash", "fallback": "gpt-4-turbo"}
            }
        },
        "metricas": {}
    }
    
    logger.info("starting_workflow_execution", num_ciclos=3)
    
    try:
        ciclos_detectados = []
        resultado = None
        
        # Stream para monitorar ciclos e capturar estado final
        print("\n🔄 Monitorando execução dos ciclos...\n")
        async for state in app.astream(initial_state, config={"recursion_limit": 100}):
            if isinstance(state, dict):
                for key, value in state.items():
                    # Guardar último estado
                    resultado = value
                    
                    if isinstance(value, dict) and 'ciclo_atual' in value:
                        ciclo = value['ciclo_atual']
                        if ciclo not in ciclos_detectados:
                            ciclos_detectados.append(ciclo)
                            print(f"✅ Ciclo {ciclo} detectado")
                            print(f"   Status jurídico: {value.get('status_juridico', 'N/A')}")
                            print(f"   Status linguístico: {value.get('status_linguistico', 'N/A')}")
                            print()
        
        # Se não capturou nada, usar estado inicial
        if resultado is None:
            resultado = initial_state
        
        logger.info("workflow_completed")
        
        # Resultados
        print("\n" + "=" * 60)
        print("RESULTADO DO TESTE - 3 CICLOS")
        print("=" * 60)
        print(f"\nCiclos executados: {ciclos_detectados}")
        print(f"Ciclos esperados: [1, 2, 3]")
        print(f"\nLetra final ({len(resultado.get('letra_atual', ''))} caracteres):")
        print("\n" + resultado.get('letra_atual', '')[:300] + "...")
        print("\n" + "=" * 60)
        print(f"Status Final Jurídico: {resultado.get('status_juridico')}")
        print(f"Status Final Linguístico: {resultado.get('status_linguistico')}")
        print("=" * 60)
        
        # Verificar sucesso
        if len(ciclos_detectados) >= 3:
            print("\n✅ SUCESSO! Todos os 3 ciclos foram executados!")
            return True
        else:
            print(f"\n❌ FALHA! Apenas {len(ciclos_detectados)} ciclos executados")
            return False
        
    except Exception as e:
        logger.error("workflow_failed", erro=str(e))
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Função principal."""
    print("\n🧪 TESTE DE MÚLTIPLOS CICLOS")
    print("=" * 60)
    print("Este teste executa 3 ciclos completos")
    print("=" * 60)
    print()
    
    try:
        success = asyncio.run(test_multi_cycle())
        
        if success:
            print("\n✅ Teste concluído com sucesso!")
            print("\nAgora você pode testar via interface web:")
            print("1. Inicie o servidor: python start.py")
            print("2. Faça upload de arquivos")
            print("3. Configure para 2 ou 3 ciclos")
            print("4. Verifique que múltiplos arquivos JSON são gerados (_c1, _c2, _c3)")
        else:
            print("\n❌ Teste falhou - verifique os logs")
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