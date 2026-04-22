"""
Feature engineering para detectores de ML.

Extrai features de séries temporais de taxas para uso em
modelos de detecção de anomalias baseados em Machine Learning.
"""

import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from veredas.storage.models import TaxaCDB

logger = logging.getLogger(__name__)


def _safe_get(s: pd.Series, idx: datetime) -> float | None:
    """Lê valor de uma Series por índice sem lançar exceção."""
    try:
        val = s.get(idx)
        return float(val) if pd.notna(val) else None
    except Exception:
        return None


@dataclass
class TaxaFeatures:
    """Features extraídas de uma taxa para ML."""

    # Identificação
    taxa_id: int | None
    if_id: int
    data: datetime

    # Valor bruto
    percentual: float

    # Features temporais
    dia_semana: int  # 0-6
    dia_mes: int  # 1-31
    semana_ano: int  # 1-52
    mes: int  # 1-12
    fim_de_mes: bool  # últimos 3 dias

    # Features estatísticas (rolling)
    rolling_mean_7d: float | None
    rolling_std_7d: float | None
    rolling_mean_14d: float | None
    rolling_std_14d: float | None
    rolling_mean_30d: float | None
    rolling_std_30d: float | None

    # Features de variação
    diff_1d: float | None  # Variação do dia anterior
    diff_7d: float | None  # Variação de 7 dias
    diff_30d: float | None  # Variação de 30 dias
    pct_change_7d: float | None  # Variação percentual 7d

    # Features de posição relativa
    z_score_7d: float | None  # Z-score local (7d)
    z_score_30d: float | None  # Z-score local (30d)
    percentile_30d: float | None  # Percentil no período

    # Features de contexto de mercado
    diff_from_market_mean: float | None  # Diferença da média do mercado
    market_z_score: float | None  # Z-score em relação ao mercado

    def to_array(self) -> np.ndarray:
        """Converte features para array numpy para ML."""
        return np.array([
            self.percentual,
            self.dia_semana,
            self.dia_mes,
            self.semana_ano,
            self.mes,
            float(self.fim_de_mes),
            self.rolling_mean_7d or 0,
            self.rolling_std_7d or 0,
            self.rolling_mean_14d or 0,
            self.rolling_std_14d or 0,
            self.rolling_mean_30d or 0,
            self.rolling_std_30d or 0,
            self.diff_1d or 0,
            self.diff_7d or 0,
            self.diff_30d or 0,
            self.pct_change_7d or 0,
            self.z_score_7d or 0,
            self.z_score_30d or 0,
            self.percentile_30d or 50,
            self.diff_from_market_mean or 0,
            self.market_z_score or 0,
        ])

    @staticmethod
    def feature_names() -> list[str]:
        """Retorna nomes das features para interpretabilidade."""
        return [
            "percentual",
            "dia_semana",
            "dia_mes",
            "semana_ano",
            "mes",
            "fim_de_mes",
            "rolling_mean_7d",
            "rolling_std_7d",
            "rolling_mean_14d",
            "rolling_std_14d",
            "rolling_mean_30d",
            "rolling_std_30d",
            "diff_1d",
            "diff_7d",
            "diff_30d",
            "pct_change_7d",
            "z_score_7d",
            "z_score_30d",
            "percentile_30d",
            "diff_from_market_mean",
            "market_z_score",
        ]


class FeatureExtractor:
    """
    Extrai features de séries temporais de taxas.

    Prepara dados para modelos de ML como Isolation Forest e DBSCAN.
    """

    def __init__(
        self,
        rolling_windows: tuple[int, ...] = (7, 14, 30),
        include_market_context: bool = True,
    ):
        """
        Inicializa o extrator de features.

        Args:
            rolling_windows: Janelas para cálculo de estatísticas móveis.
            include_market_context: Se deve incluir features de contexto de mercado.
        """
        self.rolling_windows = rolling_windows
        self.include_market_context = include_market_context

    def extract(
        self,
        taxas: Sequence[TaxaCDB],
        market_mean: float | None = None,
        market_std: float | None = None,
    ) -> list[TaxaFeatures]:
        """
        Extrai features de uma sequência de taxas.

        Args:
            taxas: Sequência de TaxaCDB.
            market_mean: Média do mercado (opcional).
            market_std: Desvio padrão do mercado (opcional).

        Returns:
            Lista de TaxaFeatures extraídas.
        """
        if not taxas:
            return []

        # Agrupa por IF
        grouped = self._group_by_if(taxas)

        all_features: list[TaxaFeatures] = []

        for if_id, if_taxas in grouped.items():
            if_features = self._extract_if_features(
                if_id, if_taxas, market_mean, market_std
            )
            all_features.extend(if_features)

        return all_features

    def extract_to_dataframe(
        self,
        taxas: Sequence[TaxaCDB],
        market_mean: float | None = None,
        market_std: float | None = None,
    ) -> pd.DataFrame:
        """
        Extrai features e retorna como DataFrame.

        Args:
            taxas: Sequência de TaxaCDB.
            market_mean: Média do mercado (opcional).
            market_std: Desvio padrão do mercado (opcional).

        Returns:
            DataFrame com features extraídas.
        """
        features = self.extract(taxas, market_mean, market_std)

        if not features:
            return pd.DataFrame()

        records = []
        for f in features:
            record = {
                "taxa_id": f.taxa_id,
                "if_id": f.if_id,
                "data": f.data,
            }
            record.update(dict(zip(TaxaFeatures.feature_names(), f.to_array(), strict=False)))
            records.append(record)

        return pd.DataFrame(records)

    def extract_to_matrix(
        self,
        taxas: Sequence[TaxaCDB],
        market_mean: float | None = None,
        market_std: float | None = None,
    ) -> tuple[np.ndarray, list[tuple[int | None, int, datetime]]]:
        """
        Extrai features como matriz numpy para ML.

        Args:
            taxas: Sequência de TaxaCDB.
            market_mean: Média do mercado (opcional).
            market_std: Desvio padrão do mercado (opcional).

        Returns:
            Tupla (matriz de features, lista de identificadores).
        """
        features = self.extract(taxas, market_mean, market_std)

        if not features:
            return np.array([]), []

        matrix = np.array([f.to_array() for f in features])
        ids = [(f.taxa_id, f.if_id, f.data) for f in features]

        return matrix, ids

    def _group_by_if(self, taxas: Sequence[TaxaCDB]) -> dict[int, list[TaxaCDB]]:
        """Agrupa taxas por instituição financeira."""
        # CODE-002: Padronizado com defaultdict (consistente com statistical.py)
        grouped: dict[int, list[TaxaCDB]] = defaultdict(list)
        for taxa in taxas:
            grouped[taxa.if_id].append(taxa)
        return grouped

    def _extract_if_features(
        self,
        if_id: int,
        taxas: list[TaxaCDB],
        market_mean: float | None,
        market_std: float | None,
    ) -> list[TaxaFeatures]:
        """Extrai features para taxas de uma IF específica."""
        if not taxas:
            return []

        # Ordenar por data
        taxas = sorted(taxas, key=lambda t: t.data_coleta)

        # Criar série temporal
        dates = [t.data_coleta for t in taxas]
        values = [float(t.percentual) for t in taxas]
        series = pd.Series(values, index=pd.DatetimeIndex(dates))

        # Calcular estatísticas rolling
        rolling_stats = {}
        for window in self.rolling_windows:
            rolling_stats[f"mean_{window}d"] = series.rolling(
                window=window, min_periods=max(1, window // 2)
            ).mean()
            rolling_stats[f"std_{window}d"] = series.rolling(
                window=window, min_periods=max(1, window // 2)
            ).std()

        # Calcular variações
        diff_1d = series.diff(1)
        diff_7d = series.diff(7) if len(series) > 7 else pd.Series([None] * len(series))
        diff_30d = series.diff(30) if len(series) > 30 else pd.Series([None] * len(series))
        pct_change_7d = series.pct_change(7) if len(series) > 7 else pd.Series([None] * len(series))

        # Percentil rolling calculado uma vez para toda a série (evita O(N²))
        rolling_percentile = series.rolling(window=30, min_periods=1).rank(pct=True) * 100

        features: list[TaxaFeatures] = []

        for i, taxa in enumerate(taxas):
            date = taxa.data_coleta
            value = float(taxa.percentual)

            # Features temporais
            dia_semana = date.weekday()
            dia_mes = date.day
            semana_ano = date.isocalendar()[1]
            mes = date.month

            # Verifica se é fim de mês (últimos 3 dias)
            next_month = date.replace(day=28) + timedelta(days=4)
            ultimo_dia = next_month - timedelta(days=next_month.day)
            fim_de_mes = date.day >= ultimo_dia.day - 2

            rolling_mean_7d = _safe_get(rolling_stats.get("mean_7d", pd.Series()), date)
            rolling_std_7d = _safe_get(rolling_stats.get("std_7d", pd.Series()), date)
            rolling_mean_14d = _safe_get(rolling_stats.get("mean_14d", pd.Series()), date)
            rolling_std_14d = _safe_get(rolling_stats.get("std_14d", pd.Series()), date)
            rolling_mean_30d = _safe_get(rolling_stats.get("mean_30d", pd.Series()), date)
            rolling_std_30d = _safe_get(rolling_stats.get("std_30d", pd.Series()), date)

            # Variações
            d1 = _safe_get(diff_1d, date)
            d7 = _safe_get(diff_7d, date)
            d30 = _safe_get(diff_30d, date)
            pct7 = _safe_get(pct_change_7d, date)

            # Z-scores locais
            z_7d = None
            if rolling_mean_7d is not None and rolling_std_7d and rolling_std_7d > 0:
                z_7d = (value - rolling_mean_7d) / rolling_std_7d

            z_30d = None
            if rolling_mean_30d is not None and rolling_std_30d and rolling_std_30d > 0:
                z_30d = (value - rolling_mean_30d) / rolling_std_30d

            # Percentil no período (pré-computado)
            percentile_30d = _safe_get(rolling_percentile, date) if i >= 1 else None

            # Contexto de mercado
            diff_market = None
            market_z = None
            if self.include_market_context and market_mean is not None:
                diff_market = value - market_mean
                if market_std and market_std > 0:
                    market_z = diff_market / market_std

            features.append(
                TaxaFeatures(
                    taxa_id=taxa.id,
                    if_id=if_id,
                    data=date,
                    percentual=value,
                    dia_semana=dia_semana,
                    dia_mes=dia_mes,
                    semana_ano=semana_ano,
                    mes=mes,
                    fim_de_mes=fim_de_mes,
                    rolling_mean_7d=rolling_mean_7d,
                    rolling_std_7d=rolling_std_7d,
                    rolling_mean_14d=rolling_mean_14d,
                    rolling_std_14d=rolling_std_14d,
                    rolling_mean_30d=rolling_mean_30d,
                    rolling_std_30d=rolling_std_30d,
                    diff_1d=d1,
                    diff_7d=d7,
                    diff_30d=d30,
                    pct_change_7d=pct7,
                    z_score_7d=z_7d,
                    z_score_30d=z_30d,
                    percentile_30d=percentile_30d,
                    diff_from_market_mean=diff_market,
                    market_z_score=market_z,
                )
            )

        return features


def calculate_market_stats(taxas: Sequence[TaxaCDB]) -> tuple[float, float]:
    """
    Calcula estatísticas de mercado para um conjunto de taxas.

    Args:
        taxas: Sequência de TaxaCDB.

    Returns:
        Tupla (média, desvio_padrão) do mercado.
    """
    if not taxas:
        return 0.0, 0.0

    values = [float(t.percentual) for t in taxas]
    return float(np.mean(values)), float(np.std(values))
