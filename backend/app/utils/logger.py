"""Sistema de logging estruturado com structlog."""
import sys
import logging
from pathlib import Path
from datetime import datetime
from contextvars import ContextVar
import structlog
from structlog.stdlib import LoggerFactory

# Context vars para rastreamento
arquivo_context: ContextVar[str] = ContextVar("arquivo_context", default="")
ciclo_context: ContextVar[int] = ContextVar("ciclo_context", default=0)
etapa_context: ContextVar[str] = ContextVar("etapa_context", default="")

def add_context_to_event_dict(logger, method_name, event_dict):
    """Adiciona contexto automático aos logs."""
    if arquivo := arquivo_context.get():
        event_dict["arquivo"] = arquivo
    if ciclo := ciclo_context.get():
        event_dict["ciclo"] = ciclo
    if etapa := etapa_context.get():
        event_dict["etapa"] = etapa
    return event_dict

def setup_logging(
    log_dir: Path,
    execucao_id: str,
    formato: str = "legivel",
    nivel: str = "INFO"
):
    """
    Configura sistema de logging.
    
    Args:
        log_dir: Diretório para salvar logs
        execucao_id: ID único da execução
        formato: "legivel" ou "json"
        nivel: Nível de log (DEBUG, INFO, WARNING, ERROR)
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configurar nível
    log_level = getattr(logging, nivel.upper(), logging.INFO)
    
    # Processadores comuns
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        add_context_to_event_dict,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    
    if formato == "json":
        # Logs JSON para arquivo master.jsonl
        file_handler = logging.FileHandler(
            log_dir / "master.jsonl",
            encoding="utf-8"
        )
        file_handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processor=structlog.processors.JSONRenderer()
            )
        )
        
        # Console também JSON
        console_processors = shared_processors + [
            structlog.processors.JSONRenderer()
        ]
    else:
        # Logs legíveis para arquivo master.txt
        file_handler = logging.FileHandler(
            log_dir / "master.txt",
            encoding="utf-8"
        )
        file_handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processor=structlog.dev.ConsoleRenderer()
            )
        )
        
        # Console colorido
        console_processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True)
        ]
    
    # Configurar stdlib logging
    logging.basicConfig(
        format="%(message)s",
        handlers=[
            file_handler,
            logging.StreamHandler(sys.stdout)
        ],
        level=log_level,
    )
    
    # Configurar structlog
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    return structlog.get_logger()

def get_logger():
    """Retorna logger configurado."""
    return structlog.get_logger()

def set_arquivo_context(arquivo: str):
    """Define contexto do arquivo atual."""
    arquivo_context.set(arquivo)

def set_ciclo_context(ciclo: int):
    """Define contexto do ciclo atual."""
    ciclo_context.set(ciclo)

def set_etapa_context(etapa: str):
    """Define contexto da etapa atual."""
    etapa_context.set(etapa)

def clear_context():
    """Limpa todos os contextos."""
    arquivo_context.set("")
    ciclo_context.set(0)
    etapa_context.set("")