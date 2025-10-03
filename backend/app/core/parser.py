"""Parser e validador de arquivos HTML."""
import re
from pathlib import Path
from typing import Tuple
from bs4 import BeautifulSoup
from pydantic import BaseModel


class ValidationError(Exception):
    """Erro de validação de HTML."""
    def __init__(self, arquivo: str, erro: str, **kwargs):
        self.arquivo = arquivo
        self.erro = erro
        self.detalhes = kwargs
        super().__init__(f"{arquivo}: {erro}")


class MetadadosHTML(BaseModel):
    """Metadados extraídos de HTML."""
    tema: str
    topico: str
    conteudo: str
    arquivo: str
    avisos: list[str] = []


def extrair_metadados(html_path: Path) -> MetadadosHTML:
    """
    Extrai tema, tópico e conteúdo de um arquivo HTML.
    
    Args:
        html_path: Caminho para arquivo HTML
        
    Returns:
        MetadadosHTML com dados extraídos
        
    Raises:
        ValidationError: Se HTML for inválido
    """
    avisos = []
    
    # Ler arquivo
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except Exception as e:
        raise ValidationError(
            html_path.name,
            "Erro ao ler arquivo",
            erro_original=str(e)
        )
    
    # Parse HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Validar estrutura - section
    section = soup.find('section', id='fundamentacao')
    if not section:
        # Fallback: procurar qualquer section com conteúdo
        sections = soup.find_all('section')
        if sections:
            section = max(sections, key=lambda s: len(s.get_text()))
            avisos.append("section#fundamentacao não encontrada, usando section com mais conteúdo")
        else:
            raise ValidationError(
                html_path.name,
                "Nenhuma section encontrada no HTML"
            )
    
    # Extrair conteúdo
    conteudo = section.get_text(separator='\n', strip=True)
    
    if len(conteudo) < 100:
        avisos.append(f"Conteúdo curto ({len(conteudo)} caracteres)")
    
    if len(conteudo) > 50000:
        avisos.append("Conteúdo muito longo, será truncado se necessário")
        conteudo = truncar_inteligente(conteudo, max_chars=45000)
    
    # Parsear title
    title_elem = soup.find('title')
    if title_elem:
        tema, topico = parsear_title(title_elem.get_text())
    else:
        avisos.append("Title não encontrado, usando nome do arquivo")
        tema = "Não especificado"
        topico = html_path.stem
    
    return MetadadosHTML(
        tema=tema,
        topico=topico,
        conteudo=conteudo,
        arquivo=html_path.name,
        avisos=avisos
    )


def parsear_title(title_text: str) -> Tuple[str, str]:
    """
    Extrai tema e tópico do title.
    
    Formato esperado: "[TEMA] - [TÓPICO] - Guia Completo..."
    
    Args:
        title_text: Texto do title
        
    Returns:
        Tupla (tema, topico)
    """
    title_text = title_text.strip()
    
    # Regex flexível
    match = re.match(r'\[?(.+?)\]?\s*-\s*\[?(.+?)\]?\s*-\s*', title_text)
    
    if match:
        tema, topico = match.groups()
        return tema.strip(), topico.strip()
    
    # Fallback: split simples
    parts = [p.strip() for p in title_text.split('-')]
    if len(parts) >= 2:
        return parts[0], parts[1]
    
    # Último fallback
    return title_text, title_text


def sanitizar_topico(topico: str, max_len: int = 12) -> str:
    """
    Sanitiza tópico para usar em nome de arquivo.
    
    "Direitos e Garantias Fundamentais" → "DirGarFun"
    
    Args:
        topico: Texto do tópico
        max_len: Comprimento máximo
        
    Returns:
        Tópico sanitizado
    """
    stopwords = {'e',')','(', 'a', 'o', 'de', 'da', 'do', 'dos', 'das', 'para', 'por', 'em', 'no', 'na'}
    
    palavras = [
        p[:3].capitalize() 
        for p in topico.split() 
        if p.lower() not in stopwords and len(p) > 2
    ]
    
    return ''.join(palavras)[:max_len]


def gerar_nome_saida(
    html_path: Path,
    topico: str,
    radical: str,
    id_estilo: str
) -> str:
    """
    Gera nome do arquivo JSON de saída.
    
    Args:
        html_path: Caminho do HTML original
        topico: Tópico extraído
        radical: Radical definido pelo usuário
        id_estilo: Identificador do estilo
        
    Returns:
        Nome do arquivo (ex: "dConst01_DirGarFun_fk.json")
    """
    # Extrair número do nome original
    match = re.search(r'(\d+)', html_path.stem)
    numero = match.group(1) if match else '01'
    
    # Sanitizar tópico
    topico_sanitizado = sanitizar_topico(topico)
    
    # Montar nome
    return f"{radical}{numero}_{topico_sanitizado}_{id_estilo}.json"


def truncar_inteligente(conteudo: str, max_chars: int) -> str:
    """
    Trunca conteúdo preservando parágrafos completos.
    
    Args:
        conteudo: Texto a truncar
        max_chars: Número máximo de caracteres
        
    Returns:
        Texto truncado
    """
    if len(conteudo) <= max_chars:
        return conteudo
    
    # Tentar cortar em parágrafo
    paragrafos = conteudo.split('\n\n')
    truncado = []
    tamanho_atual = 0
    
    for paragrafo in paragrafos:
        if tamanho_atual + len(paragrafo) + 2 <= max_chars:
            truncado.append(paragrafo)
            tamanho_atual += len(paragrafo) + 2
        else:
            break
    
    if truncado:
        return '\n\n'.join(truncado)
    
    # Se nenhum parágrafo cabe, cortar no caractere
    return conteudo[:max_chars].rsplit(' ', 1)[0] + "..."


def estimar_tokens(texto: str) -> int:
    """
    Estimativa rápida de tokens (aproximadamente 4 chars = 1 token).
    
    Args:
        texto: Texto a estimar
        
    Returns:
        Número estimado de tokens
    """
    return len(texto) // 4