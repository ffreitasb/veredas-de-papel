"""
Download e extração do arquivo de Renda Fixa Privada do Boletim Diário B3.

URL confirmada (sem JS):
    https://www.b3.com.br/pesquisapregao/download?filelist=RF{DDMMYY}.ex_,

O arquivo retornado é um ZIP aninhado:
    RF{DDMMYY}.ex_          ← ZIP externo (~70KB)
      └── RF{DDMMYY}.ex_   ← executável SFX Windows
            └── RF{DDMMYY}.txt  ← CSV com delimitador ";"
"""

import io
import zipfile
from datetime import date

# SELECTOR: padrão de URL confirmado por inspeção de rede em 23/04/2026
_BASE_URL = "https://www.b3.com.br/pesquisapregao/download?filelist=RF{ddmmyy}.ex_,"


def build_url(pregao: date) -> str:
    """Constrói a URL de download para um pregão específico."""
    ddmmyy = pregao.strftime("%d%m%y")
    return _BASE_URL.format(ddmmyy=ddmmyy)


def extract_txt(raw: bytes) -> str:
    """
    Extrai o conteúdo do TXT a partir do ZIP aninhado retornado pela B3.

    O arquivo tem estrutura: ZIP externo → SFX Windows → ZIP interno → TXT.
    Localiza o ZIP interno pelo magic number PK dentro do SFX.

    Retorna string vazia se o arquivo for um ZIP vazio (pregão fechado).
    """
    if len(raw) < 30:
        return ""

    try:
        # Camada 1: ZIP externo
        with zipfile.ZipFile(io.BytesIO(raw)) as outer:
            names = outer.namelist()
            if not names:
                return ""
            sfx_bytes = outer.read(names[0])
    except zipfile.BadZipFile:
        return ""

    if len(sfx_bytes) < 30:
        return ""

    # Camada 2: ZIP interno embutido no executável SFX
    # Procura a última ocorrência do magic number PK (início de ZIP)
    pk_pos = sfx_bytes.rfind(b"PK\x03\x04")
    if pk_pos == -1:
        return ""

    try:
        with zipfile.ZipFile(io.BytesIO(sfx_bytes[pk_pos:])) as inner:
            inner_names = inner.namelist()
            if not inner_names:
                return ""
            # B3 usa encoding latin-1 nos arquivos TXT históricos
            return inner.read(inner_names[0]).decode("latin-1", errors="replace")
    except zipfile.BadZipFile:
        return ""
