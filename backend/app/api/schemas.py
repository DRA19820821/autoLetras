"""Schemas Pydantic para API."""
from datetime import datetime
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class ModeloConfig(BaseModel):
    """Configuração de modelo primário e fallback."""
    primario: str
    fallback: str


class ConfigCiclo(BaseModel):
    """Configuração de modelos para um ciclo."""
    compositor: ModeloConfig
    revisor_juridico: ModeloConfig
    ajustador_juridico: ModeloConfig
    revisor_linguistico: ModeloConfig
    ajustador_linguistico: ModeloConfig


class ConfigExecucao(BaseModel):
    """Configuração completa de uma execução."""
    estilo: str = Field(..., description="Descrição do estilo musical")
    id_estilo: str = Field(..., min_length=2, max_length=3, description="ID do estilo (2-3 letras)")
    radical: str = Field(..., description="Radical para nome dos arquivos")
    num_ciclos: int = Field(3, ge=1, le=3, description="Número de ciclos (1-3)")
    ciclo_1: ConfigCiclo
    ciclo_2: Optional[ConfigCiclo] = None
    ciclo_3: Optional[ConfigCiclo] = None


class ArquivoValidacao(BaseModel):
    """Resultado de validação de um arquivo."""
    arquivo: str
    valido: bool
    tema: Optional[str] = None
    topico: Optional[str] = None
    avisos: List[str] = []
    erro: Optional[str] = None


class IniciarExecucaoRequest(BaseModel):
    """Request para iniciar processamento."""
    arquivos: List[str] = Field(..., description="Lista de nomes de arquivos HTML")
    config: ConfigExecucao


class StatusArquivo(BaseModel):
    """Status de processamento de um arquivo."""
    arquivo: str
    status: Literal["aguardando", "processando", "concluido", "falha"]
    ciclo_atual: Optional[int] = None
    etapa_atual: Optional[str] = None
    progresso_percentual: int = 0
    output_gerado: Optional[str] = None
    erro: Optional[str] = None


class ExecucaoStatus(BaseModel):
    """Status completo de uma execução."""
    execucao_id: str
    status: Literal["inicializando", "processando", "concluido", "cancelado", "erro"]
    timestamp_inicio: datetime
    timestamp_fim: Optional[datetime] = None
    duracao_segundos: Optional[int] = None
    
    arquivos: List[StatusArquivo]
    
    # Estatísticas
    total_arquivos: int
    arquivos_concluidos: int
    arquivos_em_processo: int
    arquivos_falhados: int
    
    # Métricas
    custo_total: float = 0.0
    total_chamadas: int = 0
    chamadas_com_retry: int = 0
    chamadas_com_fallback: int = 0


class LogEntry(BaseModel):
    """Entrada de log."""
    timestamp: datetime
    nivel: str
    arquivo: Optional[str] = None
    ciclo: Optional[int] = None
    etapa: Optional[str] = None
    mensagem: str
    detalhes: Optional[Dict] = None


class MetricasProvedor(BaseModel):
    """Métricas de uso de um provedor."""
    total_chamadas: int
    primeira_tentativa_ok: int
    com_retry: int
    com_fallback: int
    custo_total: float
    taxa_sucesso: float


class SummaryResponse(BaseModel):
    """Resumo final de uma execução."""
    execucao_id: str
    timestamp_inicio: datetime
    timestamp_fim: datetime
    duracao_total: str
    
    resultados: Dict[str, int]  # {"sucesso_completo": 8, ...}
    
    custos: Dict[str, float]
    tokens: Dict[str, int]
    
    estatisticas_retry: Dict[str, int]
    metricas_por_provedor: Dict[str, MetricasProvedor]
    
    avisos: List[str]
    detalhes_arquivos: List[Dict]


class ProvedorStatus(BaseModel):
    """Status de disponibilidade de um provedor."""
    provedor: str
    disponivel: bool
    mensagem: Optional[str] = None