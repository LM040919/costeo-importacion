"""Consulta de ingresos (entradas de almacén en estado 'Done') en BigQuery.

Cadena de datos (proyecto marvelsa-odoo):
    orden CM (purchases.purchases.vendor_reference, formato 'CM###-## || desc')
      -> PO  (purchases.purchases.name)
      -> entrada de almacén (warehouse.transfers.source_documents = PO)
         filtrando operation_type_code='incoming' y picking_status='Done'
      -> ingreso = warehouse.transfers.reference (ej. MV1/IN/13806)

Credenciales (en este orden):
    1. st.secrets["gcp_service_account"]  -> cuenta de servicio (producción/Cloud).
    2. Credenciales por defecto (ADC / gcloud)  -> desarrollo local.
Si no hay ninguna, enabled() devuelve False y la app sigue funcionando sin BQ.
"""

import re

import streamlit as st

PROJECT = "marvelsa-odoo"

# Patrón de orden CM###-## (con sufijo opcional -#). Mismo que en flete.py.
_RE_ORDEN = re.compile(r"CM\d{2,4}-\d{2}(?:-\d{1,2})?")

_QUERY = r"""
WITH pos AS (
  SELECT DISTINCT
    REGEXP_EXTRACT(p.vendor_reference, r'(CM\d{2,4}-\d{2}(?:-\d{1,2})?)') AS orden,
    p.name AS po
  FROM `marvelsa-odoo.purchases.purchases` p
  WHERE REGEXP_EXTRACT(p.vendor_reference, r'(CM\d{2,4}-\d{2}(?:-\d{1,2})?)') IN UNNEST(@ordenes)
)
SELECT DISTINCT pos.orden, pos.po, t.reference AS ingreso
FROM pos
JOIN `marvelsa-odoo.warehouse.transfers` t ON t.source_documents = pos.po
WHERE t.operation_type_code = 'incoming' AND t.picking_status = 'Done'
ORDER BY pos.orden, ingreso
"""


@st.cache_resource(show_spinner=False)
def _client():
    try:
        from google.cloud import bigquery
        from google.oauth2 import service_account
    except Exception:  # noqa: BLE001 — librería no instalada
        return None
    try:
        if "gcp_service_account" in st.secrets:
            info = dict(st.secrets["gcp_service_account"])
            creds = service_account.Credentials.from_service_account_info(info)
            return bigquery.Client(project=PROJECT, credentials=creds)
        return bigquery.Client(project=PROJECT)  # ADC (gcloud) en local
    except Exception:  # noqa: BLE001 — sin credenciales válidas
        return None


def enabled() -> bool:
    return _client() is not None


def parse_ordenes(texto: str):
    """Extrae las órdenes CM de un texto (campo 'Órdenes' separado por comas)."""
    vistas, out = set(), []
    for m in _RE_ORDEN.findall(texto or ""):
        if m not in vistas:
            vistas.add(m)
            out.append(m)
    return out


@st.cache_data(ttl=300, show_spinner=False)
def ingresos_done(ordenes: tuple):
    """Devuelve [{orden, po, ingreso}] de entradas 'Done' para esas órdenes."""
    cli = _client()
    if cli is None or not ordenes:
        return []
    from google.cloud import bigquery

    job = cli.query(
        _QUERY,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ArrayQueryParameter("ordenes", "STRING", list(ordenes))]
        ),
    )
    return [dict(r) for r in job.result()]


if __name__ == "__main__":
    import sys

    ords = tuple(sys.argv[1:]) or ("CM209-25", "CM409-25-1")
    print("Órdenes:", ords)
    for row in ingresos_done(ords):
        print(f"  {row['orden']:14} {row['po']:10} -> {row['ingreso']}")
