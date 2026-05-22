"""Catálogos de tarifas para los selectores de la app de costeo.

Conforme Luis vaya enviando tarifas, se agregan a estas listas.
Salvo que se indique, los montos están en PESOS (MXN) y SIN IVA.
"""

OTRO = "Otro (capturar monto)"

# --- Flete terrestre / local (MXN, sin IVA) ---
# Fuente: tarifas Luis, 2026-05-22.
FLETE_TERRESTRE = [
    {"proveedor": "Henco", "tipo": "Sencillo", "tarifa": 24250.0},
    {"proveedor": "Henco", "tipo": "Full", "tarifa": 37500.0},
    {"proveedor": "RTC", "tipo": "Full", "tarifa": 37000.0},
    {"proveedor": "GISAP", "tipo": "Sencillo", "tarifa": 24800.0},
]

# --- Maniobras y honorarios (van JUNTOS; tarifa fija por agente aduanal, MXN) ---
# Fuente: tarifas Luis, 2026-05-22. Se asumen montos SIN IVA (confirmar con Luis).
MANIOBRAS_HONORARIOS = [
    {"proveedor": "WISE", "tarifa": 20640.0},
    {"proveedor": "WOODWARD", "tarifa": 18192.50},
]

# Nota: flete marítimo y almacenajes son variables -> captura manual (sin catálogo).


def _opciones(catalogo, etiqueta):
    """Construye (labels, mapa label->tarifa) para un catálogo, con 'Otro' al final."""
    mapa = {}
    for t in catalogo:
        label = etiqueta(t)
        mapa[label] = t["tarifa"]
    return list(mapa.keys()) + [OTRO], mapa


def flete_terrestre_opciones():
    return _opciones(
        FLETE_TERRESTRE,
        lambda t: f"{t['proveedor']} - {t['tipo']} (${t['tarifa']:,.0f})",
    )


def maniobras_honorarios_opciones():
    return _opciones(
        MANIOBRAS_HONORARIOS,
        lambda t: f"{t['proveedor']} (${t['tarifa']:,.2f})",
    )
