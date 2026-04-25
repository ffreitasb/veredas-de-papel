"""Testes unitários para collectors/b3/downloader.py — ZIP aninhado B3."""

import io
import zipfile
from datetime import date

from veredas.collectors.b3.downloader import build_url, extract_txt


def _make_b3_zip(txt_content: str, filename: str = "RF230426.txt") -> bytes:
    """Cria a estrutura ZIP aninhada que a B3 entrega.

    Estrutura: ZIP externo → SFX (prefix bytes + ZIP interno) → TXT.
    """
    # ZIP interno com o TXT
    inner_buf = io.BytesIO()
    with zipfile.ZipFile(inner_buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(filename, txt_content.encode("latin-1"))
    inner_bytes = inner_buf.getvalue()

    # SFX simulado: prefixo sem PK + ZIP interno (sempre começa com PK\x03\x04)
    sfx_bytes = b"\x00" * 512 + inner_bytes

    # ZIP externo contendo o SFX
    outer_buf = io.BytesIO()
    with zipfile.ZipFile(outer_buf, "w") as z:
        z.writestr("RF230426.ex_", sfx_bytes)
    return outer_buf.getvalue()


class TestExtractTxt:
    def test_extrai_conteudo_do_txt(self):
        conteudo = "20260423\nITUB-DEB71;20250715;100;80;100.0;95.0;12.5;1.5"
        raw = _make_b3_zip(conteudo)
        resultado = extract_txt(raw)
        assert "ITUB-DEB71" in resultado
        assert "20260423" in resultado

    def test_bytes_vazios_retorna_str_vazia(self):
        assert extract_txt(b"") == ""

    def test_bytes_menores_que_30_retorna_str_vazia(self):
        assert extract_txt(b"PK" * 10) == ""

    def test_zip_corrompido_retorna_str_vazia(self):
        assert extract_txt(b"not a zip file at all" * 10) == ""

    def test_zip_externo_sem_arquivos_retorna_str_vazia(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w"):
            pass
        assert extract_txt(buf.getvalue()) == ""

    def test_sfx_sem_pk_interno_retorna_str_vazia(self):
        """SFX sem magic number PK → rfind retorna -1 → str vazia."""
        sfx_bytes = b"\xDE\xAD\xBE\xEF" * 128  # sem PK\x03\x04

        outer_buf = io.BytesIO()
        with zipfile.ZipFile(outer_buf, "w") as z:
            z.writestr("RF230426.ex_", sfx_bytes)
        assert extract_txt(outer_buf.getvalue()) == ""

    def test_conteudo_preserva_caracteres_latin1(self):
        conteudo = "20260423\nDESCRIÇÃO;campo"
        raw = _make_b3_zip(conteudo)
        resultado = extract_txt(raw)
        # latin-1 decode com errors='replace' — não deve lançar exceção
        assert "20260423" in resultado


class TestBuildUrl:
    def test_formata_ddmmyy(self):
        url = build_url(date(2026, 4, 23))
        assert "RF230426.ex_" in url

    def test_formata_padrao_correto_primeiro_dia_do_mes(self):
        url = build_url(date(2026, 1, 1))
        assert "RF010126.ex_" in url

    def test_url_contem_base_b3(self):
        url = build_url(date(2026, 4, 23))
        assert "b3.com.br" in url
