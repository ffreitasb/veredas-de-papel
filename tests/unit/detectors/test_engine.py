"""Testes unitários para DetectionEngine._deduplicate — votação ponderada (ENG-01).

A votação eleva severidade apenas quando detectores de *categorias distintas*
concordam (rules, statistical, ml). Detectores da mesma categoria não são
evidência independente.
"""

from datetime import datetime
from decimal import Decimal

from veredas.detectors.base import AnomaliaDetectada
from veredas.detectors.engine import DetectionEngine, EngineConfig
from veredas.storage.models import Severidade, TipoAnomalia


def _anomalia(
    severidade: Severidade,
    detector: str,
    if_id: int = 1,
    taxa_id: int = 10,
    data: datetime | None = None,
) -> AnomaliaDetectada:
    return AnomaliaDetectada(
        tipo=TipoAnomalia.SPREAD_ALTO,
        severidade=severidade,
        valor_detectado=Decimal("130"),
        descricao="teste",
        if_id=if_id,
        taxa_id=taxa_id,
        detector=detector,
        detectado_em=data or datetime(2024, 6, 1),
    )


def _engine() -> DetectionEngine:
    return DetectionEngine(EngineConfig(deduplicate=True))


class TestDeduplicateVotacao:
    def test_um_detector_mantem_severidade_original(self):
        engine = _engine()
        a = _anomalia(Severidade.MEDIUM, "spread_detector")
        result = engine._deduplicate([a])
        assert len(result) == 1
        assert result[0].severidade == Severidade.MEDIUM

    def test_duas_categorias_distintas_elevam_um_nivel(self):
        """rules + statistical → +1 nível (MEDIUM → HIGH)."""
        engine = _engine()
        anomalias = [
            _anomalia(Severidade.MEDIUM, "spread_detector"),         # rules
            _anomalia(Severidade.LOW, "rolling_zscore_detector"),    # statistical
        ]
        result = engine._deduplicate(anomalias)
        assert len(result) == 1
        assert result[0].severidade == Severidade.HIGH

    def test_tres_categorias_distintas_elevam_dois_niveis(self):
        """rules + statistical + ml → +2 níveis (MEDIUM → CRITICAL)."""
        engine = _engine()
        anomalias = [
            _anomalia(Severidade.MEDIUM, "spread_detector"),          # rules
            _anomalia(Severidade.LOW, "rolling_zscore_detector"),     # statistical
            _anomalia(Severidade.LOW, "isolation_forest_detector"),   # ml
        ]
        result = engine._deduplicate(anomalias)
        assert len(result) == 1
        assert result[0].severidade == Severidade.CRITICAL

    def test_elevacao_nao_ultrapassa_critical(self):
        """HIGH + 3 categorias → CRITICAL (capped, não estoura)."""
        engine = _engine()
        anomalias = [
            _anomalia(Severidade.HIGH, "spread_detector"),            # rules
            _anomalia(Severidade.MEDIUM, "rolling_zscore_detector"),  # statistical
            _anomalia(Severidade.LOW, "isolation_forest_detector"),   # ml
        ]
        result = engine._deduplicate(anomalias)
        assert result[0].severidade == Severidade.CRITICAL

    def test_winner_e_o_mais_severo_do_grupo(self):
        """A anomalia base deve ser a de maior severidade original."""
        engine = _engine()
        anomalias = [
            _anomalia(Severidade.LOW, "rolling_zscore_detector"),    # statistical
            _anomalia(Severidade.HIGH, "spread_detector"),           # rules
        ]
        result = engine._deduplicate(anomalias)
        # winner foi HIGH; 2 categorias → +1 → CRITICAL
        assert result[0].severidade == Severidade.CRITICAL
        assert result[0].detector == "spread_detector"

    def test_mesma_categoria_nao_eleva(self):
        """Dois detectores ML concordando NÃO eleva severidade."""
        engine = _engine()
        anomalias = [
            _anomalia(Severidade.MEDIUM, "isolation_forest_detector"),  # ml
            _anomalia(Severidade.LOW, "dbscan_outlier_detector"),       # ml
        ]
        result = engine._deduplicate(anomalias)
        assert len(result) == 1
        assert result[0].severidade == Severidade.MEDIUM  # sem elevação

    def test_detectores_registrados_em_detalhes(self):
        """Lista de detectores que votaram deve estar em detalhes['detectores']."""
        engine = _engine()
        anomalias = [
            _anomalia(Severidade.MEDIUM, "spread_detector"),
            _anomalia(Severidade.LOW, "rolling_zscore_detector"),
        ]
        result = engine._deduplicate(anomalias)
        assert "detectores" in result[0].detalhes
        assert set(result[0].detalhes["detectores"]) == {
            "spread_detector",
            "rolling_zscore_detector",
        }

    def test_votos_registra_numero_de_categorias(self):
        """detalhes['votos'] conta categorias distintas, não detectores."""
        engine = _engine()
        anomalias = [
            _anomalia(Severidade.MEDIUM, "spread_detector"),          # rules
            _anomalia(Severidade.LOW, "rolling_zscore_detector"),     # statistical
            _anomalia(Severidade.LOW, "isolation_forest_detector"),   # ml
        ]
        result = engine._deduplicate(anomalias)
        assert result[0].detalhes["votos"] == 3

    def test_detector_duplicado_nao_conta_dobrado(self):
        """O mesmo detector aparecendo duas vezes conta como 1 voto."""
        engine = _engine()
        anomalias = [
            _anomalia(Severidade.MEDIUM, "spread_detector"),
            _anomalia(Severidade.LOW, "spread_detector"),
        ]
        result = engine._deduplicate(anomalias)
        # Apenas 1 categoria (rules) — sem elevação
        assert result[0].severidade == Severidade.MEDIUM
        assert "votos" not in result[0].detalhes

    def test_grupos_diferentes_nao_interferem(self):
        """Anomalias de IFs diferentes permanecem separadas."""
        engine = _engine()
        anomalias = [
            _anomalia(Severidade.MEDIUM, "spread_detector", if_id=1, taxa_id=10),
            _anomalia(Severidade.MEDIUM, "spread_detector", if_id=2, taxa_id=20),
        ]
        result = engine._deduplicate(anomalias)
        assert len(result) == 2
        for r in result:
            assert r.severidade == Severidade.MEDIUM

    def test_mesma_taxa_datas_diferentes_nao_agrupa(self):
        """Mesma taxa em dias diferentes gera duas anomalias distintas."""
        engine = _engine()
        anomalias = [
            _anomalia(Severidade.MEDIUM, "spread_detector", data=datetime(2024, 6, 1)),
            _anomalia(Severidade.MEDIUM, "rolling_zscore_detector", data=datetime(2024, 6, 2)),
        ]
        result = engine._deduplicate(anomalias)
        assert len(result) == 2
