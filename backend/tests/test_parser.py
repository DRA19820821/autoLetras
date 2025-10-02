"""Testes para o módulo parser."""
import pytest
from pathlib import Path
import tempfile
from app.core.parser import (
    extrair_metadados,
    parsear_title,
    sanitizar_topico,
    gerar_nome_saida,
    truncar_inteligente,
    estimar_tokens,
    ValidationError,
)


def criar_html_temporario(title: str, conteudo: str = "Conteúdo de teste") -> Path:
    """Helper para criar HTML temporário."""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title}</title>
    </head>
    <body>
        <section id="fundamentacao">
            {conteudo}
        </section>
    </body>
    </html>
    """
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
        f.write(html)
        return Path(f.name)


class TestParsearTitle:
    """Testes para parsear_title."""
    
    def test_formato_padrao(self):
        """Testa parsing de title no formato padrão."""
        title = "Direito Administrativo - Atos Administrativos - Guia Completo"
        tema, topico = parsear_title(title)
        
        assert tema == "Direito Administrativo"
        assert topico == "Atos Administrativos"
    
    def test_formato_com_colchetes(self):
        """Testa parsing com colchetes."""
        title = "[Direito Civil] - [Contratos] - Guia Completo"
        tema, topico = parsear_title(title)
        
        assert tema == "Direito Civil"
        assert topico == "Contratos"
    
    def test_formato_simples(self):
        """Testa parsing de formato simplificado."""
        title = "Tema - Tópico"
        tema, topico = parsear_title(title)
        
        assert tema == "Tema"
        assert topico == "Tópico"
    
    def test_sem_separador(self):
        """Testa title sem separador."""
        title = "TitleSemSeparador"
        tema, topico = parsear_title(title)
        
        assert tema == title
        assert topico == title


class TestSanitizarTopico:
    """Testes para sanitizar_topico."""
    
    def test_topico_simples(self):
        """Testa sanitização de tópico simples."""
        result = sanitizar_topico("Direitos e Garantias Fundamentais")
        
        assert "Dir" in result
        assert "Gar" in result
        assert "Fun" in result
        assert "e" not in result  # stopword removida
    
    def test_topico_com_artigos(self):
        """Testa remoção de artigos."""
        result = sanitizar_topico("A Lei de Licitações")
        
        assert "A" not in result or len(result) <= 1  # "A" pode estar no início
        assert "Lei" in result
        assert "Lic" in result
    
    def test_limite_caracteres(self):
        """Testa limite de 12 caracteres."""
        result = sanitizar_topico("Palavra Muito Longa Para O Nome Do Arquivo")
        
        assert len(result) <= 12
    
    def test_topico_curto(self):
        """Testa tópico muito curto."""
        result = sanitizar_topico("Lei")
        
        assert len(result) > 0
        assert "Lei" in result


class TestGerarNomeSaida:
    """Testes para gerar_nome_saida."""
    
    def test_nome_basico(self):
        """Testa geração de nome básico."""
        html_path = Path("dConst01_IntroducaoDA.html")
        nome = gerar_nome_saida(html_path, "Introdução ao Direito", "dConst", "fk")
        
        assert nome.startswith("dConst01_")
        assert nome.endswith("_fk.json")
        assert "Int" in nome
    
    def test_sem_numero_no_nome(self):
        """Testa arquivo sem número."""
        html_path = Path("arquivo_sem_numero.html")
        nome = gerar_nome_saida(html_path, "Tópico Teste", "rad", "st")
        
        assert "rad01_" in nome  # Deve usar 01 como padrão


class TestTruncarInteligente:
    """Testes para truncar_inteligente."""
    
    def test_texto_curto(self):
        """Testa texto que não precisa truncar."""
        texto = "Texto curto"
        result = truncar_inteligente(texto, max_chars=100)
        
        assert result == texto
    
    def test_truncar_em_paragrafo(self):
        """Testa truncamento preservando parágrafo."""
        texto = "Parágrafo 1.\n\nParágrafo 2.\n\nParágrafo 3."
        result = truncar_inteligente(texto, max_chars=20)
        
        assert len(result) <= 20
        assert "Parágrafo 1" in result
    
    def test_truncar_palavra(self):
        """Testa truncamento por palavra."""
        texto = "Palavra " * 50  # Sem parágrafos
        result = truncar_inteligente(texto, max_chars=30)
        
        assert len(result) <= 35  # Permite margem para ...
        assert result.endswith("...")


class TestEstimarTokens:
    """Testes para estimar_tokens."""
    
    def test_estimativa_basica(self):
        """Testa estimativa de tokens."""
        texto = "a" * 100
        tokens = estimar_tokens(texto)
        
        assert tokens == 25  # 100/4


class TestExtrairMetadados:
    """Testes de integração para extrair_metadados."""
    
    def test_html_valido(self):
        """Testa extração de HTML válido."""
        html_path = criar_html_temporario(
            "Direito Civil - Contratos - Guia Completo",
            "Este é um conteúdo válido com mais de 100 caracteres para passar na validação. " * 3
        )
        
        try:
            metadados = extrair_metadados(html_path)
            
            assert metadados.tema == "Direito Civil"
            assert metadados.topico == "Contratos"
            assert len(metadados.conteudo) > 100
            assert metadados.arquivo == html_path.name
            assert len(metadados.avisos) == 0
        finally:
            html_path.unlink()
    
    def test_html_sem_section(self):
        """Testa HTML sem section#fundamentacao."""
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Teste - Teste</title></head>
        <body>
            <section>Conteúdo em section genérica.</section>
        </body>
        </html>
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html)
            html_path = Path(f.name)
        
        try:
            metadados = extrair_metadados(html_path)
            
            # Deve ter aviso mas não falhar
            assert len(metadados.avisos) > 0
            assert any("fundamentacao" in a.lower() for a in metadados.avisos)
        finally:
            html_path.unlink()
    
    def test_html_invalido(self):
        """Testa HTML totalmente inválido."""
        html = """
        <!DOCTYPE html>
        <html><head><title>Teste</title></head><body></body></html>
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html)
            html_path = Path(f.name)
        
        try:
            with pytest.raises(ValidationError) as exc_info:
                extrair_metadados(html_path)
            
            assert "section" in str(exc_info.value).lower()
        finally:
            html_path.unlink()
    
    def test_conteudo_muito_longo(self):
        """Testa truncamento de conteúdo longo."""
        html_path = criar_html_temporario(
            "Teste - Teste",
            "Texto longo. " * 10000  # >50k caracteres
        )
        
        try:
            metadados = extrair_metadados(html_path)
            
            assert len(metadados.conteudo) <= 50000
            assert any("longo" in a.lower() for a in metadados.avisos)
        finally:
            html_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])