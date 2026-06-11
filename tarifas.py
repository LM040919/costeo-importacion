"""Catálogos de tarifas para los selectores de la app de costeo.

Si hay base de datos configurada (Supabase), las tarifas se leen de ahí y las
gerentes pueden editarlas desde la UI. Si NO hay base de datos, se usan las
listas hardcodeadas de abajo como respaldo (para no romper la app en vivo).

Salvo que se indique, los montos están en PESOS (MXN) y SIN IVA.
"""

import db

OTRO = "Otro (capturar monto)"

# --- Respaldo (cuando no hay base de datos) ---
# Fuente: tarifas Luis. Henco actualizado 2026-06-05.
FLETE_TERRESTRE = [
    {"proveedor": "Henco", "tipo": "Sencillo", "tarifa": 26500.0},
    {"proveedor": "Henco", "tipo": "Full", "tarifa": 42000.0},
    {"proveedor": "RTC", "tipo": "Full", "tarifa": 37000.0},
    {"proveedor": "GISAP", "tipo": "Sencillo", "tarifa": 24800.0},
]
MANIOBRAS_HONORARIOS = [
    {"proveedor": "WISE", "tarifa": 20640.0},
    {"proveedor": "WOODWARD", "tarifa": 18192.50},
]


def _flete_terrestre():
    if db.enabled():
        return [
            {"proveedor": t["proveedor"], "tipo": t.get("tipo"), "tarifa": float(t["tarifa"])}
            for t in db.list_tarifas("flete_terrestre")
        ]
    return FLETE_TERRESTRE


def _maniobras_honorarios():
    if db.enabled():
        return [
            {"proveedor": t["proveedor"], "tarifa": float(t["tarifa"])}
            for t in db.list_tarifas("maniobras_honorarios")
        ]
    return MANIOBRAS_HONORARIOS


def _opciones(catalogo, etiqueta):
    """Construye (labels, mapa label->tarifa) para un catálogo, con 'Otro' al final."""
    mapa = {}
    for t in catalogo:
        mapa[etiqueta(t)] = t["tarifa"]
    return list(mapa.keys()) + [OTRO], mapa


def flete_terrestre_opciones():
    return _opciones(
        _flete_terrestre(),
        lambda t: f"{t['proveedor']} - {t['tipo']} (${t['tarifa']:,.0f})",
    )


def maniobras_honorarios_opciones():
    return _opciones(
        _maniobras_honorarios(),
        lambda t: f"{t['proveedor']} (${t['tarifa']:,.2f})",
    )
