"""
Parser para dados da B3.

Processa diferentes formatos de dados retornados pela B3:
- JSON de APIs
- CSV de arquivos públicos
- HTML de páginas web
"""

import csv
import io
import logging
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from veredas.collectors.b3.models import (
    NegociacaoB3,
    PrecoSecundario,
    TipoTitulo,
)

logger = logging.getLogger(__name__)


class B3DataParser:
    """
    Parser para dados de mercado da B3.

    Normaliza dados de diferentes formatos para estruturas padrão.
    """

    # Mapeamento de tipos de título
    TIPO_TITULO_MAP = {
        "CDB": TipoTitulo.CDB,
        "LCI": TipoTitulo.LCI,
        "LCA": TipoTitulo.LCA,
        "LC": TipoTitulo.LC,
        "LETRA DE CAMBIO": TipoTitulo.LC,
        "DEBENTURE": TipoTitulo.DEBENTURE,
        "DEB": TipoTitulo.DEBENTURE,
        "CRI": TipoTitulo.CRI,
        "CRA": TipoTitulo.CRA,
    }

    def parse_json_response(
        self,
        data: dict[str, Any],
        data_ref: date,
    ) -> list[PrecoSecundario]:
        """
        Parse de resposta JSON da API.

        Args:
            data: Dados JSON
            data_ref: Data de referência

        Returns:
            Lista de PrecoSecundario
        """
        precos = []

        # Estrutura pode variar
        items = data.get("data") or data.get("items") or data.get("titulos") or []

        if isinstance(data, list):
            items = data

        for item in items:
            try:
                preco = self._parse_item_json(item, data_ref)
                if preco:
                    precos.append(preco)
            except Exception as e:
                logger.debug(f"Erro ao parsear item JSON: {e}")
                continue

        return precos

    def _parse_item_json(
        self,
        item: dict[str, Any],
        data_ref: date,
    ) -> Optional[PrecoSecundario]:
        """Parse de um item JSON."""
        try:
            # Código do título
            codigo = (
                item.get("codigo")
                or item.get("codigoTitulo")
                or item.get("isin")
                or ""
            )

            if not codigo:
                return None

            # Emissor
            cnpj = self._normalizar_cnpj(
                item.get("cnpjEmissor") or item.get("emissorCnpj") or ""
            )
            nome = (
                item.get("nomeEmissor")
                or item.get("emissorNome")
                or item.get("emissor")
                or ""
            )

            # Tipo
            tipo_str = item.get("tipoTitulo") or item.get("tipo") or "CDB"
            tipo = self._parse_tipo_titulo(tipo_str)

            # Preços
            pu_abertura = self._parse_decimal(item.get("puAbertura") or item.get("precoAbertura"))
            pu_fechamento = self._parse_decimal(item.get("puFechamento") or item.get("precoFechamento"))
            pu_minimo = self._parse_decimal(item.get("puMinimo") or item.get("precoMinimo"))
            pu_maximo = self._parse_decimal(item.get("puMaximo") or item.get("precoMaximo"))
            pu_medio = self._parse_decimal(item.get("puMedio") or item.get("precoMedio"))

            # Se não tiver todos os preços, usa o disponível
            if pu_fechamento is None:
                pu_fechamento = pu_medio or pu_abertura or Decimal("0")
            if pu_abertura is None:
                pu_abertura = pu_fechamento
            if pu_minimo is None:
                pu_minimo = min(pu_abertura, pu_fechamento)
            if pu_maximo is None:
                pu_maximo = max(pu_abertura, pu_fechamento)
            if pu_medio is None:
                pu_medio = (pu_abertura + pu_fechamento) / 2

            # Volume
            qtd_negocios = int(item.get("quantidadeNegocios") or item.get("qtdNegocios") or 0)
            qtd_titulos = int(item.get("quantidadeTitulos") or item.get("qtdTitulos") or 0)
            valor_fin = self._parse_decimal(item.get("valorFinanceiro") or item.get("volume"))

            # Taxas
            taxa_min = self._parse_decimal(item.get("taxaMinima"))
            taxa_max = self._parse_decimal(item.get("taxaMaxima"))
            taxa_media = self._parse_decimal(item.get("taxaMedia"))

            # Variação
            variacao = self._parse_decimal(item.get("variacaoDia") or item.get("variacao"))

            return PrecoSecundario(
                codigo_titulo=codigo,
                emissor_cnpj=cnpj or "00.000.000/0000-00",
                emissor_nome=nome,
                tipo_titulo=tipo,
                data_referencia=data_ref,
                pu_abertura=pu_abertura,
                pu_fechamento=pu_fechamento,
                pu_minimo=pu_minimo,
                pu_maximo=pu_maximo,
                pu_medio=pu_medio,
                quantidade_negocios=qtd_negocios,
                quantidade_titulos=qtd_titulos,
                valor_financeiro=valor_fin or Decimal("0"),
                taxa_minima=taxa_min or Decimal("0"),
                taxa_maxima=taxa_max or Decimal("0"),
                taxa_media=taxa_media or Decimal("0"),
                variacao_dia=variacao,
            )

        except Exception as e:
            logger.debug(f"Erro ao parsear item: {e}")
            return None

    def parse_csv_response(
        self,
        content: str,
        data_ref: date,
    ) -> list[PrecoSecundario]:
        """
        Parse de arquivo CSV.

        Args:
            content: Conteúdo CSV
            data_ref: Data de referência

        Returns:
            Lista de PrecoSecundario
        """
        precos = []

        try:
            # Detecta delimitador
            delimiter = ";" if ";" in content[:1000] else ","

            reader = csv.DictReader(
                io.StringIO(content),
                delimiter=delimiter,
            )

            for row in reader:
                try:
                    preco = self._parse_row_csv(row, data_ref)
                    if preco:
                        precos.append(preco)
                except Exception as e:
                    logger.debug(f"Erro ao parsear linha CSV: {e}")
                    continue

        except Exception as e:
            logger.error(f"Erro ao parsear CSV: {e}")

        return precos

    def _parse_row_csv(
        self,
        row: dict[str, str],
        data_ref: date,
    ) -> Optional[PrecoSecundario]:
        """Parse de uma linha CSV."""
        try:
            # Normaliza keys (remove espaços, lowercase)
            row_norm = {k.strip().lower().replace(" ", "_"): v for k, v in row.items()}

            codigo = (
                row_norm.get("codigo")
                or row_norm.get("codigo_titulo")
                or row_norm.get("isin")
                or ""
            )

            if not codigo:
                return None

            cnpj = self._normalizar_cnpj(
                row_norm.get("cnpj_emissor") or row_norm.get("cnpj") or ""
            )
            nome = row_norm.get("nome_emissor") or row_norm.get("emissor") or ""

            tipo_str = row_norm.get("tipo_titulo") or row_norm.get("tipo") or "CDB"
            tipo = self._parse_tipo_titulo(tipo_str)

            # Preços
            pu_abertura = self._parse_decimal(row_norm.get("pu_abertura"))
            pu_fechamento = self._parse_decimal(row_norm.get("pu_fechamento"))
            pu_minimo = self._parse_decimal(row_norm.get("pu_minimo"))
            pu_maximo = self._parse_decimal(row_norm.get("pu_maximo"))
            pu_medio = self._parse_decimal(row_norm.get("pu_medio"))

            # Valores default
            if pu_fechamento is None:
                return None

            pu_abertura = pu_abertura or pu_fechamento
            pu_minimo = pu_minimo or min(pu_abertura, pu_fechamento)
            pu_maximo = pu_maximo or max(pu_abertura, pu_fechamento)
            pu_medio = pu_medio or (pu_abertura + pu_fechamento) / 2

            # Volume
            qtd_negocios = int(row_norm.get("qtd_negocios") or row_norm.get("negocios") or 0)
            qtd_titulos = int(row_norm.get("qtd_titulos") or row_norm.get("quantidade") or 0)
            valor_fin = self._parse_decimal(row_norm.get("valor_financeiro") or row_norm.get("volume"))

            # Taxas
            taxa_min = self._parse_decimal(row_norm.get("taxa_minima"))
            taxa_max = self._parse_decimal(row_norm.get("taxa_maxima"))
            taxa_media = self._parse_decimal(row_norm.get("taxa_media"))

            return PrecoSecundario(
                codigo_titulo=codigo,
                emissor_cnpj=cnpj or "00.000.000/0000-00",
                emissor_nome=nome,
                tipo_titulo=tipo,
                data_referencia=data_ref,
                pu_abertura=pu_abertura,
                pu_fechamento=pu_fechamento,
                pu_minimo=pu_minimo,
                pu_maximo=pu_maximo,
                pu_medio=pu_medio,
                quantidade_negocios=qtd_negocios,
                quantidade_titulos=qtd_titulos,
                valor_financeiro=valor_fin or Decimal("0"),
                taxa_minima=taxa_min or Decimal("0"),
                taxa_maxima=taxa_max or Decimal("0"),
                taxa_media=taxa_media or Decimal("0"),
            )

        except Exception as e:
            logger.debug(f"Erro ao parsear row: {e}")
            return None

    def parse_html_page(
        self,
        html: str,
        data_ref: date,
    ) -> list[PrecoSecundario]:
        """
        Parse de página HTML (fallback).

        Args:
            html: Conteúdo HTML
            data_ref: Data de referência

        Returns:
            Lista de PrecoSecundario
        """
        precos = []

        try:
            # Tenta extrair dados de tabelas
            # Padrão comum: <table class="...">
            import re
            import json

            # Primeiro, tenta JSON embutido
            json_patterns = [
                r'var\s+dados\s*=\s*(\[.*?\]);',
                r'window\.pageData\s*=\s*({.*?});',
                r'"titulos"\s*:\s*(\[.*?\])',
            ]

            for pattern in json_patterns:
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(1))
                        items = data if isinstance(data, list) else []
                        for item in items:
                            preco = self._parse_item_json(item, data_ref)
                            if preco:
                                precos.append(preco)
                        if precos:
                            return precos
                    except json.JSONDecodeError:
                        continue

            # Fallback: parse de tabela HTML
            # Procura por tags <tr> com dados
            tr_pattern = r'<tr[^>]*>(.*?)</tr>'
            td_pattern = r'<td[^>]*>(.*?)</td>'

            rows = re.findall(tr_pattern, html, re.DOTALL | re.IGNORECASE)

            for row in rows:
                cells = re.findall(td_pattern, row, re.DOTALL | re.IGNORECASE)
                if len(cells) >= 5:  # Mínimo de colunas esperadas
                    # Limpa HTML das células
                    cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
                    # Tenta parsear como dados de título
                    # (estrutura específica dependeria do layout da página)

        except Exception as e:
            logger.error(f"Erro ao parsear HTML: {e}")

        return precos

    def parse_negociacoes(
        self,
        data: list[dict[str, Any]],
    ) -> list[NegociacaoB3]:
        """
        Parse de lista de negociações.

        Args:
            data: Lista de dicts com dados de negociação

        Returns:
            Lista de NegociacaoB3
        """
        negociacoes = []

        for item in data:
            try:
                codigo = item.get("codigoTitulo") or item.get("codigo") or ""
                if not codigo:
                    continue

                data_neg_str = item.get("dataNegociacao") or item.get("data")
                data_neg = self._parse_data(data_neg_str) or date.today()

                pu = self._parse_decimal(item.get("precoUnitario") or item.get("pu"))
                if pu is None:
                    continue

                quantidade = int(item.get("quantidade") or item.get("qtd") or 0)
                valor = self._parse_decimal(item.get("valorFinanceiro") or item.get("valor"))
                taxa = self._parse_decimal(item.get("taxaNegociada") or item.get("taxa"))

                negociacoes.append(
                    NegociacaoB3(
                        codigo_titulo=codigo,
                        data_negociacao=data_neg,
                        preco_unitario=pu,
                        quantidade=quantidade,
                        valor_financeiro=valor or (pu * quantidade),
                        taxa_negociada=taxa or Decimal("0"),
                    )
                )

            except Exception as e:
                logger.debug(f"Erro ao parsear negociação: {e}")
                continue

        return negociacoes

    def _parse_decimal(self, value: Any) -> Optional[Decimal]:
        """Parse de valor decimal."""
        if value is None:
            return None

        try:
            if isinstance(value, (int, float)):
                return Decimal(str(value))

            if isinstance(value, Decimal):
                return value

            if isinstance(value, str):
                # Remove caracteres não numéricos
                cleaned = value.strip().replace(" ", "")
                cleaned = cleaned.replace("R$", "").replace("%", "")

                # Formato BR: 1.234,56
                if "," in cleaned and "." in cleaned:
                    cleaned = cleaned.replace(".", "").replace(",", ".")
                elif "," in cleaned:
                    cleaned = cleaned.replace(",", ".")

                return Decimal(cleaned)

        except (InvalidOperation, ValueError):
            return None

        return None

    def _parse_data(self, value: Any) -> Optional[date]:
        """Parse de data."""
        if value is None:
            return None

        if isinstance(value, date):
            return value

        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, str):
            formatos = [
                "%Y-%m-%d",
                "%d/%m/%Y",
                "%d-%m-%Y",
                "%Y%m%d",
            ]

            for fmt in formatos:
                try:
                    return datetime.strptime(value.strip(), fmt).date()
                except ValueError:
                    continue

        return None

    def _parse_tipo_titulo(self, value: str) -> TipoTitulo:
        """Parse de tipo de título."""
        if not value:
            return TipoTitulo.CDB

        value_upper = value.upper().strip()

        # Busca direta
        if value_upper in self.TIPO_TITULO_MAP:
            return self.TIPO_TITULO_MAP[value_upper]

        # Busca parcial
        for key, tipo in self.TIPO_TITULO_MAP.items():
            if key in value_upper:
                return tipo

        return TipoTitulo.OUTROS

    def _normalizar_cnpj(self, cnpj: str) -> str:
        """Normaliza CNPJ para formato padrão."""
        if not cnpj:
            return ""

        # Remove caracteres não numéricos
        digits = re.sub(r"\D", "", cnpj)

        if len(digits) != 14:
            return cnpj  # Retorna original se inválido

        # Formata
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
