"""
Analisador de sentimento para textos financeiros.

Analisa textos (notícias, reclamações, etc) para extrair
sentimento relacionado a instituições financeiras.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from veredas import TZ_BRASIL

logger = logging.getLogger(__name__)


class Sentimento(str, Enum):
    """Classificação de sentimento."""

    MUITO_NEGATIVO = "MUITO_NEGATIVO"
    NEGATIVO = "NEGATIVO"
    NEUTRO = "NEUTRO"
    POSITIVO = "POSITIVO"
    MUITO_POSITIVO = "MUITO_POSITIVO"


@dataclass
class AnaliseTexto:
    """Resultado da análise de um texto."""

    texto: str
    sentimento: Sentimento
    score: Decimal  # -1 (negativo) a +1 (positivo)
    confianca: Decimal  # 0 a 1

    # Entidades detectadas
    instituicoes_mencionadas: list[str] = field(default_factory=list)
    temas_detectados: list[str] = field(default_factory=list)

    # Palavras-chave
    palavras_positivas: list[str] = field(default_factory=list)
    palavras_negativas: list[str] = field(default_factory=list)

    # Metadata
    fonte: str = ""
    data_texto: Optional[datetime] = None
    analisado_em: datetime = field(default_factory=lambda: datetime.now(TZ_BRASIL))


@dataclass
class SentimentoAgregado:
    """Sentimento agregado para uma instituição."""

    instituicao_cnpj: str
    instituicao_nome: str

    # Scores
    score_medio: Decimal  # -1 a +1
    score_ponderado: Decimal  # Considera confiança

    # Contagens
    total_textos: int = 0
    textos_positivos: int = 0
    textos_neutros: int = 0
    textos_negativos: int = 0

    # Tendência
    tendencia: str = "ESTAVEL"  # MELHORANDO, ESTAVEL, PIORANDO

    # Temas mais frequentes
    temas_frequentes: list[str] = field(default_factory=list)

    # Período
    periodo_inicio: datetime = field(default_factory=lambda: datetime.now(TZ_BRASIL))
    periodo_fim: datetime = field(default_factory=lambda: datetime.now(TZ_BRASIL))


class SentimentAnalyzer:
    """
    Analisador de sentimento para textos financeiros.

    Usa uma abordagem baseada em léxico (dicionário de palavras)
    para análise rápida sem dependência de modelos de ML.

    Para análise mais sofisticada, pode ser integrado com
    transformers (BERT, etc) quando disponível.
    """

    # Palavras positivas (contexto financeiro)
    PALAVRAS_POSITIVAS = {
        # Genéricas
        "bom", "boa", "excelente", "ótimo", "ótima", "maravilhoso", "perfeito",
        "satisfeito", "satisfeita", "recomendo", "recomendado", "confiável",
        "eficiente", "rápido", "rápida", "fácil", "simples", "prático",
        # Financeiras
        "lucro", "crescimento", "rentabilidade", "alta", "valorização",
        "sólido", "sólida", "estável", "seguro", "segura", "capitalizado",
        "liquidez", "aprovado", "aprovada", "liberado", "liberada",
        "investimento", "retorno", "ganho", "positivo", "positiva",
    }

    # Palavras negativas (contexto financeiro)
    PALAVRAS_NEGATIVAS = {
        # Genéricas
        "ruim", "péssimo", "péssima", "horrível", "terrível", "decepcionado",
        "decepcionada", "insatisfeito", "insatisfeita", "não recomendo",
        "problema", "problemas", "erro", "erros", "falha", "falhas",
        "demora", "demorado", "difícil", "complicado", "complicada",
        # Financeiras
        "prejuízo", "perda", "queda", "desvalorização", "crise",
        "inadimplência", "calote", "fraude", "golpe", "bloqueio",
        "bloqueado", "negado", "negada", "recusado", "recusada",
        "multa", "penalidade", "intervenção", "liquidação",
        "falência", "insolvência", "risco", "arriscado",
        # Reclamações
        "reclamação", "processo", "procon", "advogado", "justiça",
        "cobrança", "indevida", "abusivo", "abusiva",
    }

    # Palavras intensificadoras
    INTENSIFICADORES = {
        "muito", "extremamente", "totalmente", "completamente",
        "absolutamente", "demais", "super", "mega", "ultra",
    }

    # Negadores (invertem sentimento)
    NEGADORES = {
        "não", "nunca", "jamais", "nem", "nenhum", "nenhuma",
        "nada", "sem",
    }

    # Temas financeiros
    TEMAS = {
        "atendimento": ["atendimento", "atendente", "suporte", "sac", "chat"],
        "app": ["app", "aplicativo", "mobile", "celular", "smartphone"],
        "cartão": ["cartão", "cartao", "crédito", "débito", "limite"],
        "conta": ["conta", "corrente", "poupança", "saldo", "extrato"],
        "investimento": ["investimento", "cdb", "lci", "lca", "fundo", "ação"],
        "empréstimo": ["empréstimo", "emprestimo", "financiamento", "crédito"],
        "pix": ["pix", "transferência", "ted", "doc"],
        "tarifas": ["tarifa", "taxa", "cobrança", "mensalidade", "anuidade"],
        "segurança": ["segurança", "fraude", "golpe", "clonado", "hackeado"],
    }

    # Nomes de IFs para detecção
    INSTITUICOES = {
        "banco do brasil": "00.000.000/0001-91",
        "bb": "00.000.000/0001-91",
        "bradesco": "60.746.948/0001-12",
        "itau": "60.701.190/0001-04",
        "itaú": "60.701.190/0001-04",
        "santander": "33.657.248/0001-89",
        "caixa": "00.360.305/0001-04",
        "nubank": "18.236.120/0001-58",
        "inter": "00.416.968/0001-01",
        "banco inter": "00.416.968/0001-01",
        "c6": "10.573.521/0001-91",
        "c6 bank": "10.573.521/0001-91",
        "btg": "30.306.294/0001-45",
        "xp": "04.902.979/0001-44",
        "xp investimentos": "04.902.979/0001-44",
        "rico": "04.902.979/0001-44",
        "original": "01.181.521/0001-55",
        "pan": "92.874.270/0001-40",
    }

    def __init__(self, usar_ml: bool = False):
        """
        Inicializa o analisador.

        Args:
            usar_ml: Se True, tenta usar modelos de ML (requer transformers)
        """
        self.usar_ml = usar_ml
        self._modelo_ml = None

        if usar_ml:
            self._carregar_modelo_ml()

    def _carregar_modelo_ml(self) -> None:
        """Tenta carregar modelo de ML."""
        try:
            # Tenta importar transformers (opcional)
            from transformers import pipeline

            # Modelo de sentimento em português
            self._modelo_ml = pipeline(
                "sentiment-analysis",
                model="neuralmind/bert-base-portuguese-cased",
                truncation=True,
                max_length=512,
            )
            logger.info("Modelo ML de sentimento carregado")

        except ImportError:
            logger.warning("transformers não disponível, usando análise léxica")
            self.usar_ml = False
        except Exception as e:
            logger.warning(f"Erro ao carregar modelo ML: {e}")
            self.usar_ml = False

    def analisar(
        self,
        texto: str,
        fonte: str = "",
        data_texto: Optional[datetime] = None,
    ) -> AnaliseTexto:
        """
        Analisa sentimento de um texto.

        Args:
            texto: Texto a analisar
            fonte: Fonte do texto (ex: "reclame_aqui", "noticia")
            data_texto: Data original do texto

        Returns:
            AnaliseTexto com resultado
        """
        # Normaliza texto
        texto_limpo = self._normalizar_texto(texto)
        palavras = texto_limpo.split()

        # Detecta entidades
        instituicoes = self._detectar_instituicoes(texto_limpo)
        temas = self._detectar_temas(texto_limpo)

        # Calcula score
        if self.usar_ml and self._modelo_ml:
            score, confianca = self._analisar_ml(texto)
        else:
            score, confianca, pos, neg = self._analisar_lexico(palavras)

        # Classifica sentimento
        sentimento = self._classificar_sentimento(score)

        # Palavras positivas e negativas encontradas
        palavras_pos = [p for p in palavras if p in self.PALAVRAS_POSITIVAS]
        palavras_neg = [p for p in palavras if p in self.PALAVRAS_NEGATIVAS]

        return AnaliseTexto(
            texto=texto[:500],  # Trunca para armazenamento
            sentimento=sentimento,
            score=Decimal(str(round(score, 4))),
            confianca=Decimal(str(round(confianca, 4))),
            instituicoes_mencionadas=instituicoes,
            temas_detectados=temas,
            palavras_positivas=palavras_pos[:10],
            palavras_negativas=palavras_neg[:10],
            fonte=fonte,
            data_texto=data_texto,
        )

    def _normalizar_texto(self, texto: str) -> str:
        """Normaliza texto para análise."""
        # Lowercase
        texto = texto.lower()

        # Remove URLs
        texto = re.sub(r"https?://\S+", "", texto)

        # Remove menções e hashtags
        texto = re.sub(r"[@#]\w+", "", texto)

        # Remove caracteres especiais (mantém acentos)
        texto = re.sub(r"[^\w\sáàâãéèêíìîóòôõúùûç]", " ", texto)

        # Remove espaços extras
        texto = " ".join(texto.split())

        return texto

    def _analisar_lexico(
        self,
        palavras: list[str],
    ) -> tuple[float, float, int, int]:
        """
        Análise baseada em léxico (dicionário).

        Returns:
            (score, confianca, contagem_positivas, contagem_negativas)
        """
        positivas = 0
        negativas = 0
        intensidade = 1.0
        negacao_ativa = False

        for i, palavra in enumerate(palavras):
            # Verifica negador
            if palavra in self.NEGADORES:
                negacao_ativa = True
                continue

            # Verifica intensificador
            if palavra in self.INTENSIFICADORES:
                intensidade = 1.5
                continue

            # Conta positivas/negativas
            if palavra in self.PALAVRAS_POSITIVAS:
                if negacao_ativa:
                    negativas += intensidade
                else:
                    positivas += intensidade

            elif palavra in self.PALAVRAS_NEGATIVAS:
                if negacao_ativa:
                    positivas += intensidade
                else:
                    negativas += intensidade

            # Reset
            intensidade = 1.0
            negacao_ativa = False

        # Calcula score (-1 a +1)
        total = positivas + negativas
        if total == 0:
            return 0.0, 0.3, 0, 0  # Neutro com baixa confiança

        score = (positivas - negativas) / total

        # Confiança baseada no número de palavras detectadas
        confianca = min(1.0, total / 10)  # Máximo com 10 palavras

        return score, confianca, int(positivas), int(negativas)

    def _analisar_ml(self, texto: str) -> tuple[float, float]:
        """Análise usando modelo de ML."""
        try:
            resultado = self._modelo_ml(texto[:512])[0]

            label = resultado["label"]
            score_ml = resultado["score"]

            # Converte para escala -1 a +1
            if label in ["POSITIVE", "POS", "positive"]:
                score = score_ml
            elif label in ["NEGATIVE", "NEG", "negative"]:
                score = -score_ml
            else:
                score = 0.0

            return score, score_ml

        except Exception as e:
            logger.warning(f"Erro na análise ML: {e}")
            # Fallback para léxico
            palavras = self._normalizar_texto(texto).split()
            score, confianca, _, _ = self._analisar_lexico(palavras)
            return score, confianca

    def _classificar_sentimento(self, score: float) -> Sentimento:
        """Classifica score em categoria de sentimento."""
        if score <= -0.6:
            return Sentimento.MUITO_NEGATIVO
        elif score <= -0.2:
            return Sentimento.NEGATIVO
        elif score <= 0.2:
            return Sentimento.NEUTRO
        elif score <= 0.6:
            return Sentimento.POSITIVO
        else:
            return Sentimento.MUITO_POSITIVO

    def _detectar_instituicoes(self, texto: str) -> list[str]:
        """Detecta instituições mencionadas no texto."""
        instituicoes = []

        for nome, cnpj in self.INSTITUICOES.items():
            if nome in texto:
                if cnpj not in instituicoes:
                    instituicoes.append(cnpj)

        return instituicoes

    def _detectar_temas(self, texto: str) -> list[str]:
        """Detecta temas mencionados no texto."""
        temas_encontrados = []

        for tema, palavras_chave in self.TEMAS.items():
            for palavra in palavras_chave:
                if palavra in texto:
                    if tema not in temas_encontrados:
                        temas_encontrados.append(tema)
                    break

        return temas_encontrados

    def analisar_lote(
        self,
        textos: list[str],
        fonte: str = "",
    ) -> list[AnaliseTexto]:
        """
        Analisa um lote de textos.

        Args:
            textos: Lista de textos
            fonte: Fonte dos textos

        Returns:
            Lista de AnaliseTexto
        """
        return [self.analisar(t, fonte) for t in textos]

    def agregar_sentimento(
        self,
        analises: list[AnaliseTexto],
        cnpj: str,
        nome: str,
    ) -> SentimentoAgregado:
        """
        Agrega análises para uma instituição.

        Args:
            analises: Lista de análises
            cnpj: CNPJ da instituição
            nome: Nome da instituição

        Returns:
            SentimentoAgregado
        """
        if not analises:
            return SentimentoAgregado(
                instituicao_cnpj=cnpj,
                instituicao_nome=nome,
                score_medio=Decimal("0"),
                score_ponderado=Decimal("0"),
            )

        # Calcula médias
        scores = [float(a.score) for a in analises]
        confiancas = [float(a.confianca) for a in analises]

        score_medio = sum(scores) / len(scores)

        # Score ponderado por confiança
        soma_ponderada = sum(s * c for s, c in zip(scores, confiancas))
        soma_confianca = sum(confiancas)
        score_ponderado = soma_ponderada / soma_confianca if soma_confianca > 0 else 0

        # Contagens
        positivos = sum(1 for a in analises if a.sentimento in [Sentimento.POSITIVO, Sentimento.MUITO_POSITIVO])
        neutros = sum(1 for a in analises if a.sentimento == Sentimento.NEUTRO)
        negativos = sum(1 for a in analises if a.sentimento in [Sentimento.NEGATIVO, Sentimento.MUITO_NEGATIVO])

        # Temas frequentes
        todos_temas = []
        for a in analises:
            todos_temas.extend(a.temas_detectados)

        from collections import Counter
        temas_freq = [t for t, _ in Counter(todos_temas).most_common(5)]

        # Período
        datas = [a.data_texto for a in analises if a.data_texto]
        periodo_inicio = min(datas) if datas else datetime.now(TZ_BRASIL)
        periodo_fim = max(datas) if datas else datetime.now(TZ_BRASIL)

        return SentimentoAgregado(
            instituicao_cnpj=cnpj,
            instituicao_nome=nome,
            score_medio=Decimal(str(round(score_medio, 4))),
            score_ponderado=Decimal(str(round(score_ponderado, 4))),
            total_textos=len(analises),
            textos_positivos=positivos,
            textos_neutros=neutros,
            textos_negativos=negativos,
            temas_frequentes=temas_freq,
            periodo_inicio=periodo_inicio,
            periodo_fim=periodo_fim,
        )
