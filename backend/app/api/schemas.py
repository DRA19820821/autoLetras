"""Schemas Pydantic para API."""
from datetime import datetime
from typing import Dict, List, Literal, Optional, Any, TypedDict
from pydantic import BaseModel, Field

# --- Configuração da Execução ---

class ModeloConfig(BaseModel):
    primario: str
    fallback: str

class ConfigCiclo(BaseModel):
    compositor: ModeloConfig
    revisor_juridico: ModeloConfig
    ajustador_juridico: ModeloConfig
    revisor_linguistico: ModeloConfig
    ajustador_linguistico: ModeloConfig

class ConfigExecucao(BaseModel):
    estilo: str = Field(..., description="Descrição do estilo musical")
    id_estilo: str = Field(..., min_length=2, max_length=3, description="ID do estilo (2-3 letras)")
    radical: str = Field(..., description="Radical para nome dos arquivos")
    num_ciclos: int = Field(3, ge=1, le=3, description="Número de ciclos (1-3)")
    ciclo_1: ConfigCiclo
    ciclo_2: Optional[ConfigCiclo] = None
    ciclo_3: Optional[ConfigCiclo] = None

class IniciarExecucaoRequest(BaseModel):
    arquivos: List[str]
    config: ConfigExecucao

# --- Validação e Status ---

class ArquivoValidacao(BaseModel):
    arquivo: str
    valido: bool
    tema: Optional[str] = None
    topico: Optional[str] = None
    avisos: List[str] = []
    erro: Optional[str] = None

class StatusArquivo(BaseModel):
    arquivo: str
    status: Literal["aguardando", "processando", "concluido", "falha"]
    ciclo_atual: Optional[int] = None
    etapa_atual: Optional[str] = None
    progresso_percentual: int = 0
    output_gerado: Optional[str] = None
    erro: Optional[str] = None

class ExecucaoStatus(BaseModel):
    execucao_id: str
    status: Literal["inicializando", "processando", "concluido", "cancelado", "erro"]
    timestamp_inicio: datetime
    timestamp_fim: Optional[datetime] = None
    duracao_segundos: Optional[int] = None
    arquivos: List[StatusArquivo]
    total_arquivos: int
    arquivos_concluidos: int
    arquivos_em_processo: int
    arquivos_falhados: int
    custo_total: float = 0.0

# --- Saída Estruturada para LLMs (Function Calling) ---

class LetraMusical(BaseModel):
    """Schema para a letra da música gerada pelo compositor."""
    letra: str = Field(description="O texto completo da letra da música, incluindo um título criativo e as menções à 'Academia do Raciocínio'.")

class ResultadoRevisao(BaseModel):
    """Schema para o resultado da revisão (jurídica ou linguística)."""
    status: Literal["aprovado", "reprovado"] = Field(description="O status da revisão. 'aprovado' se a letra está correta, 'reprovado' se necessita de ajustes.")
    problemas: List[str] = Field(description="Uma lista detalhada dos problemas encontrados. Se 'status' for 'aprovado', esta lista deve estar vazia.")

class LetraAjustada(BaseModel):
    """Schema para a letra ajustada após uma revisão."""
    letra: str = Field(description="A versão completa e corrigida da letra da música, aplicando as correções necessárias.")

# --- Estado do Workflow (TypedDict para LangGraph) ---

class MusicaState(TypedDict, total=False):
    """
    Estado do workflow de composição musical.
    TypedDict usado pelo LangGraph para gerenciar o estado.
    """
    # Metadados do arquivo
    arquivo: str
    tema: str
    topico: str
    conteudo: str
    estilo: str
    
    # Controle de fluxo
    ciclo_atual: int
    etapa_atual: str
    
    # Letras
    letra_atual: str
    letra_anterior: Optional[str]
    
    # Status de revisão
    status_juridico: str
    status_linguistico: str
    
    # Problemas identificados
    problemas_juridicos: List[str]
    problemas_linguisticos: List[str]
    
    # Tentativas de ajuste
    tentativas_juridico: int
    tentativas_linguistico: int
    
    # Configuração dos modelos
    config: Dict[str, Any]
    
    # Métricas e custos
    metricas: Dict[str, Any]
    
    #llms
    llms_usados: Dict[str, List[Dict[str, str]]] 