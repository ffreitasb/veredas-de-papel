"""Funções auxiliares de exportação — separadas para manter main.py enxuto."""

import csv
import json
from pathlib import Path


def exportar_anomalias(anomalias: list, format: str, dest: Path) -> None:
    if format == "csv":
        with dest.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(
                [
                    "ID",
                    "Tipo",
                    "Severidade",
                    "Instituição",
                    "CNPJ",
                    "Valor Detectado",
                    "Valor Esperado",
                    "Desvio",
                    "Descrição",
                    "Detectado Em",
                    "Resolvido",
                    "Resolvido Em",
                ]
            )
            for a in anomalias:
                writer.writerow(
                    [
                        a.id,
                        a.tipo.value,
                        a.severidade.value,
                        a.instituicao.nome if a.instituicao else "",
                        a.instituicao.cnpj if a.instituicao else "",
                        str(a.valor_detectado).replace(".", ","),
                        str(a.valor_esperado).replace(".", ",") if a.valor_esperado else "",
                        str(a.desvio).replace(".", ",") if a.desvio else "",
                        a.descricao,
                        a.detectado_em.strftime("%d/%m/%Y %H:%M") if a.detectado_em else "",
                        "Sim" if a.resolvido else "Não",
                        a.resolvido_em.strftime("%d/%m/%Y %H:%M") if a.resolvido_em else "",
                    ]
                )
    else:
        rows = [
            {
                "id": a.id,
                "tipo": a.tipo.value,
                "severidade": a.severidade.value,
                "instituicao": a.instituicao.nome if a.instituicao else None,
                "cnpj": a.instituicao.cnpj if a.instituicao else None,
                "valor_detectado": float(a.valor_detectado)
                if a.valor_detectado is not None
                else None,
                "valor_esperado": float(a.valor_esperado) if a.valor_esperado is not None else None,
                "desvio": float(a.desvio) if a.desvio is not None else None,
                "descricao": a.descricao,
                "detectado_em": a.detectado_em.isoformat() if a.detectado_em else None,
                "resolvido": a.resolvido,
                "resolvido_em": a.resolvido_em.isoformat() if a.resolvido_em else None,
            }
            for a in anomalias
        ]
        dest.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def exportar_taxas(taxas: list, format: str, dest: Path) -> None:
    if format == "csv":
        with dest.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(
                [
                    "Data Coleta",
                    "Instituição",
                    "CNPJ",
                    "Indexador",
                    "Percentual (%)",
                    "Taxa Adicional (%)",
                    "Prazo (dias)",
                    "Liquidez Diária",
                    "Fonte",
                    "Mercado",
                    "Risk Score",
                ]
            )
            for t in taxas:
                writer.writerow(
                    [
                        t.data_coleta.strftime("%d/%m/%Y"),
                        t.instituicao.nome if t.instituicao else "",
                        t.instituicao.cnpj if t.instituicao else "",
                        t.indexador.value,
                        str(t.percentual).replace(".", ","),
                        str(t.taxa_adicional).replace(".", ",") if t.taxa_adicional else "",
                        t.prazo_dias,
                        "Sim" if t.liquidez_diaria else "Não",
                        t.fonte,
                        t.mercado or "",
                        str(t.risk_score).replace(".", ",") if t.risk_score else "",
                    ]
                )
    else:
        rows = [
            {
                "id": t.id,
                "data_coleta": t.data_coleta.isoformat(),
                "instituicao": t.instituicao.nome if t.instituicao else None,
                "cnpj": t.instituicao.cnpj if t.instituicao else None,
                "indexador": t.indexador.value,
                "percentual": float(t.percentual),
                "taxa_adicional": float(t.taxa_adicional) if t.taxa_adicional else None,
                "prazo_dias": t.prazo_dias,
                "liquidez_diaria": t.liquidez_diaria,
                "fonte": t.fonte,
                "mercado": t.mercado,
                "risk_score": float(t.risk_score) if t.risk_score else None,
            }
            for t in taxas
        ]
        dest.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
