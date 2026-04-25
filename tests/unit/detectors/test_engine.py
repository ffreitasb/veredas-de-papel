"""Testes unitários para DetectionEngine._deduplicate — votação ponderada (ENG-01)."""

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
        a = _anomalia(Severidade.MEDIUM, "detector_a")
        result = engine._deduplicate([a])
        assert len(result) == 1
        assert result[0].severidade == Severidade.MEDIUM

    def test_dois_detectores_elevam_um_nivel(self):
        """MEDIUM + 2 detectores → HIGH."""
        engine = _engine()
        anomalias = [
            _anomalia(Severidade.MEDIUM, "detector_a"),
            _anomalia(Severidade.LOW, "detector_b"),
        ]
        result = engine._deduplicate(anomalias)
        assert len(result) == 1
        assert result[0].severidade == Severidade.HIGH

    def test_tres_detectores_elevam_dois_niveis(self):
        """MEDIUM + 3 detectores → CRITICAL."""
        engine = _engine()
        anomalias = [
            _anomalia(Severidade.MEDIUM, "detector_a"),
            _anomalia(Severidade.LOW, "detector_b"),
            _anomalia(Severidade.LOW, "detector_c"),
        ]
        result = engine._deduplicate(anomalias)
        assert len(result) == 1
        assert result[0].severidade == Severidade.CRITICAL

    def test_elevacao_nao_ultrapassa_critical(self):
        """HIGH + 3 detectores → CRITICAL (capped, não estoura)."""
        engine = _engine()
        anomalias = [
            _anomalia(Severidade.HIGH, "detector_a"),
            _anomalia(Severidade.MEDIUM, "detector_b"),
            _anomalia(Severidade.LOW, "detector_c"),
        ]
        result = engine._deduplicate(anomalias)
        assert result[0].severidade == Severidade.CRITICAL

    def test_winner_e_o_mais_severo_do_grupo(self):
        """A anomalia base deve ser a de maior severidade original."""
        engine = _engine()
        anomalias = [
            _anomalia(Severidade.LOW, "detector_a"),
            _anomalia(Severidade.HIGH, "detector_b"),
        ]
        result = engine._deduplicate(anomalias)
        # winner foi HIGH; com 2 detectores sobe para CRITICAL
        assert result[0].severidade == Severidade.CRITICAL
        assert result[0].detector == "detector_b"

    def test_detectores_registrados_em_detalhes(self):
        """Lista de detectores que votaram deve estar em detalhes['detectores']."""
        engine = _engine()
        anomalias = [
            _anomalia(Severidade.MEDIUM, "spread_detector"),
            _anomalia(Severidade.LOW, "rolling_zscore"),
        ]
        result = engine._deduplicate(anomalias)
        assert "detectores" in result[0].detalhes
        assert set(result[0].detalhes["detectores"]) == {"spread_detector", "rolling_zscore"}

    def test_votos_registrados_quando_multiplos(self):
        engine = _engine()
        anomalias = [
            _anomalia(Severidade.MEDIUM, "a"),
            _anomalia(Severidade.LOW, "b"),
            _anomalia(Severidade.LOW, "c"),
        ]
        result = engine._deduplicate(anomalias)
        assert result[0].detalhes["votos"] == 3

    def test_detector_duplicado_nao_conta_dobrado(self):
        """O mesmo detector aparecendo duas vezes conta como 1 voto."""
        engine = _engine()
        anomalias = [
            _anomalia(Severidade.MEDIUM, "detector_a"),
            _anomalia(Severidade.LOW, "detector_a"),
        ]
        result = engine._deduplicate(anomalias)
        # Apenas 1 detector único — sem elevação
        assert result[0].severidade == Severidade.MEDIUM
        assert "votos" not in result[0].detalhes

    def test_grupos_diferentes_nao_interferem(self):
        """Anomalias de IFs diferentes permanecem separadas."""
        engine = _engine()
        anomalias = [
            _anomalia(Severidade.MEDIUM, "detector_a", if_id=1, taxa_id=10),
            _anomalia(Severidade.MEDIUM, "detector_b", if_id=2, taxa_id=20),
        ]
        result = engine._deduplicate(anomalias)
        assert len(result) == 2
        # Cada grupo tem só 1 detector — sem elevação
        for r in result:
            assert r.severidade == Severidade.MEDIUM

    def test_mesma_taxa_datas_diferentes_nao_agrupa(self):
        """Mesma taxa em dias diferentes gera duas anomalias distintas."""
        engine = _engine()
        anomalias = [
            _anomalia(Severidade.MEDIUM, "detector_a", data=datetime(2024, 6, 1)),
            _anomalia(Severidade.MEDIUM, "detector_b", data=datetime(2024, 6, 2)),
        ]
        result = engine._deduplicate(anomalias)
        assert len(result) == 2
