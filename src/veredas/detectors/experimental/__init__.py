"""
Detectores experimentais — não adequados para produção sem validação cuidadosa.

Cada módulo neste pacote documenta explicitamente por que está aqui e qual
é a alternativa recomendada no domínio de taxas de CDB.
"""
from veredas.detectors.experimental.stl import STLDecompositionDetector

__all__ = ["STLDecompositionDetector"]
