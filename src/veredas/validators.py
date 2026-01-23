"""
Validadores de entrada para o veredas de papel.

Implementa validacao de formatos brasileiros:
- CNPJ
- CPF (futuro)
"""

import re
from typing import Optional

from fastapi import HTTPException


def _calcular_digito_cnpj(cnpj_parcial: str, pesos: list[int]) -> int:
    """Calcula um digito verificador do CNPJ."""
    soma = sum(int(d) * p for d, p in zip(cnpj_parcial, pesos))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def validar_cnpj(cnpj: str) -> bool:
    """
    Valida CNPJ brasileiro.

    Args:
        cnpj: CNPJ com ou sem formatacao.

    Returns:
        True se CNPJ e valido, False caso contrario.
    """
    # Remover formatacao
    cnpj_limpo = re.sub(r"\D", "", cnpj)

    # Verificar tamanho
    if len(cnpj_limpo) != 14:
        return False

    # Verificar se todos os digitos sao iguais (invalido)
    if len(set(cnpj_limpo)) == 1:
        return False

    # Calcular primeiro digito verificador
    pesos_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    digito_1 = _calcular_digito_cnpj(cnpj_limpo[:12], pesos_1)

    # Calcular segundo digito verificador
    pesos_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    digito_2 = _calcular_digito_cnpj(cnpj_limpo[:13], pesos_2)

    # Verificar digitos
    return cnpj_limpo[-2:] == f"{digito_1}{digito_2}"


def normalizar_cnpj(cnpj: str) -> str:
    """
    Normaliza CNPJ removendo formatacao.

    Args:
        cnpj: CNPJ com ou sem formatacao.

    Returns:
        CNPJ apenas com digitos (14 caracteres).
    """
    return re.sub(r"\D", "", cnpj)


def formatar_cnpj(cnpj: str) -> str:
    """
    Formata CNPJ no padrao XX.XXX.XXX/XXXX-XX.

    Args:
        cnpj: CNPJ apenas com digitos.

    Returns:
        CNPJ formatado.
    """
    cnpj_limpo = normalizar_cnpj(cnpj)
    if len(cnpj_limpo) != 14:
        return cnpj  # Retorna original se invalido

    return f"{cnpj_limpo[:2]}.{cnpj_limpo[2:5]}.{cnpj_limpo[5:8]}/{cnpj_limpo[8:12]}-{cnpj_limpo[12:]}"


def parse_cnpj(
    cnpj: Optional[str],
    required: bool = False,
    validate: bool = True,
) -> Optional[str]:
    """
    Valida e normaliza CNPJ para uso em APIs.

    Args:
        cnpj: CNPJ informado pelo usuario.
        required: Se True, levanta erro quando vazio.
        validate: Se True, valida digitos verificadores.

    Returns:
        CNPJ normalizado (apenas digitos) ou None.

    Raises:
        HTTPException: Se CNPJ invalido ou ausente quando required.
    """
    if not cnpj or not cnpj.strip():
        if required:
            raise HTTPException(
                status_code=400,
                detail="CNPJ e obrigatorio.",
            )
        return None

    cnpj_normalizado = normalizar_cnpj(cnpj)

    # Verificar tamanho
    if len(cnpj_normalizado) != 14:
        raise HTTPException(
            status_code=400,
            detail=f"CNPJ invalido: deve ter 14 digitos. Recebido: {len(cnpj_normalizado)} digitos.",
        )

    # Validar digitos verificadores
    if validate and not validar_cnpj(cnpj_normalizado):
        raise HTTPException(
            status_code=400,
            detail=f"CNPJ invalido: digitos verificadores incorretos.",
        )

    return cnpj_normalizado
