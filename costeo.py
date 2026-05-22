"""Motor de cálculo de costeo de importación (landed cost).

Reproduce exactamente las fórmulas de la plantilla Excel "COSTEO ESTIMADO".
Es Python puro (sin dependencias) para poder probarlo y reutilizarlo desde
la app Streamlit o desde cualquier otro lado.

Mapeo de celdas del Excel original (hoja "COSTEO REAL "):
    E2  T.C. (tipo de cambio)            -> tipo_cambio
    E13 IMPUESTOS (sin IVA)              -> impuestos            [del pedimento]
    D14 IVA de aduana                    -> iva_aduana           [del pedimento]
    E15 MANIOBRAS EN ADUANA              -> maniobras
    E17 HONORARIOS                       -> honorarios
    E19 OTROS (DEMORAS)                  -> otros_demoras
    E21 ALMACENAJES                      -> almacenajes
    F23 FLETE MARITIMO (USD)             -> flete_maritimo_usd
    E25 FLETE LOCAL (MXN)                -> flete_local
    E27 FALSOS                           -> falsos
    E36 FAC. PROVEEDOR (USD)             -> factura_proveedor_usd
    E37 CARGOS POR SERV. DE TRANSFERENCIA (USD) -> cargos_transferencia_usd

IVA: las maniobras, honorarios, otros y almacenajes generan 16% de IVA.
El flete local también, pero en el Excel se le resta un ajuste fijo (celda
D26 = E25*0.16 - 925.44); lo dejamos como parámetro 'ajuste_iva_flete_local'.
El flete marítimo no lleva IVA en la plantilla.

Regla financiera clave: el IVA es recuperable, por eso NO se carga al costo.
Solo los gastos netos (sin IVA) se prorratean sobre la mercancía.
"""

from dataclasses import dataclass, field

TASA_IVA = 0.16


@dataclass
class CosteoInputs:
    # Tipo de cambio (MXN por USD) — del pedimento
    tipo_cambio: float

    # --- Gastos que vienen del pedimento (en MXN) ---
    impuestos: float = 0.0          # contribuciones distintas al IVA (DTA, IGI, PRV...)
    iva_aduana: float = 0.0         # IVA pagado en aduana

    # --- Gastos de logística / agente aduanal (en MXN) ---
    maniobras: float = 0.0
    honorarios: float = 0.0
    otros_demoras: float = 0.0
    almacenajes: float = 0.0
    flete_local: float = 0.0
    falsos: float = 0.0

    # --- Flete marítimo (en USD) ---
    flete_maritimo_usd: float = 0.0

    # --- Mercancía / cargos (en USD) ---
    factura_proveedor_usd: float = 0.0
    cargos_transferencia_usd: float = 0.0

    # Ajuste fijo que la plantilla resta al IVA del flete local (celda D26)
    ajuste_iva_flete_local: float = 0.0

    # --- Datos descriptivos (no entran al cálculo) ---
    no_pedimento: str = ""
    orden: str = ""
    proveedor: str = ""
    elaboro: str = ""
    fecha: str = ""


@dataclass
class CosteoResultado:
    # Conversiones a MXN
    flete_maritimo_mxn: float
    factura_proveedor_mxn: float
    cargos_transferencia_mxn: float

    # IVA por concepto
    iva_maniobras: float
    iva_honorarios: float
    iva_otros: float
    iva_almacenajes: float
    iva_flete_local: float

    # Subtotales de la cuenta de gastos
    total_gastos_sin_iva: float    # E29
    total_gastos_iva: float        # D29
    total_cuenta_gastos: float     # E31

    # Costo del embarque
    prorrateo_gastos: float        # D38
    total_embarque: float          # D41
    pct_gasto_vs_factura: float    # C43

    advertencias: list = field(default_factory=list)


def calcular(inp: CosteoInputs) -> CosteoResultado:
    tc = inp.tipo_cambio

    # Conversiones USD -> MXN
    flete_maritimo_mxn = inp.flete_maritimo_usd * tc          # E23 = F23 * E2
    factura_proveedor_mxn = inp.factura_proveedor_usd * tc    # D36 = E36 * E2
    cargos_transferencia_mxn = inp.cargos_transferencia_usd * tc  # D37 = E37 * E34

    # IVA por concepto (16%)
    iva_maniobras = inp.maniobras * TASA_IVA                  # D16
    iva_honorarios = inp.honorarios * TASA_IVA               # D18
    iva_otros = inp.otros_demoras * TASA_IVA                 # D20
    iva_almacenajes = inp.almacenajes * TASA_IVA             # D22
    iva_flete_local = inp.flete_local * TASA_IVA - inp.ajuste_iva_flete_local  # D26

    # Cuenta de gastos (columna "VALOR SIN IVA" -> E29)
    total_gastos_sin_iva = (
        inp.impuestos
        + inp.maniobras
        + inp.honorarios
        + inp.otros_demoras
        + inp.almacenajes
        + flete_maritimo_mxn
        + inp.flete_local
        + inp.falsos
    )

    # Cuenta de gastos (columna "IVA" -> D29)
    total_gastos_iva = (
        inp.iva_aduana
        + iva_maniobras
        + iva_honorarios
        + iva_otros
        + iva_almacenajes
        + iva_flete_local
    )

    total_cuenta_gastos = total_gastos_iva + total_gastos_sin_iva   # E31

    # Costo del embarque (solo se prorratean los gastos SIN IVA)
    prorrateo_gastos = total_gastos_sin_iva + cargos_transferencia_mxn   # D38
    total_embarque = factura_proveedor_mxn + cargos_transferencia_mxn + prorrateo_gastos  # D41
    pct_gasto_vs_factura = (
        prorrateo_gastos / factura_proveedor_mxn if factura_proveedor_mxn else 0.0
    )  # C43

    advertencias = []
    if cargos_transferencia_mxn:
        advertencias.append(
            "Los 'cargos por transferencia' se suman dos veces en la plantilla "
            "original (en el prorrateo y aparte en el total). Confirmar si es correcto."
        )

    return CosteoResultado(
        flete_maritimo_mxn=flete_maritimo_mxn,
        factura_proveedor_mxn=factura_proveedor_mxn,
        cargos_transferencia_mxn=cargos_transferencia_mxn,
        iva_maniobras=iva_maniobras,
        iva_honorarios=iva_honorarios,
        iva_otros=iva_otros,
        iva_almacenajes=iva_almacenajes,
        iva_flete_local=iva_flete_local,
        total_gastos_sin_iva=total_gastos_sin_iva,
        total_gastos_iva=total_gastos_iva,
        total_cuenta_gastos=total_cuenta_gastos,
        prorrateo_gastos=prorrateo_gastos,
        total_embarque=total_embarque,
        pct_gasto_vs_factura=pct_gasto_vs_factura,
        advertencias=advertencias,
    )


if __name__ == "__main__":
    # Verificación contra el caso real CM357-25-4
    caso = CosteoInputs(
        tipo_cambio=17.252,
        impuestos=6699.0,
        iva_aduana=128455.0,
        maniobras=15471.0,
        honorarios=0.0,
        otros_demoras=0.0,
        almacenajes=0.0,
        flete_local=25000.0,
        falsos=0.0,
        flete_maritimo_usd=2808.75,
        factura_proveedor_usd=43713.0,
        cargos_transferencia_usd=0.0,
        ajuste_iva_flete_local=925.44,
        no_pedimento="26 16 3977 6004925",
        orden="CM357-25-4",
        proveedor="SHAAN XI BSBSUCCEED IMPORT AND EXPORT CO.,LTD",
    )
    r = calcular(caso)

    esperado = {
        "total_gastos_sin_iva": 95626.555,
        "total_gastos_iva": 134004.92,
        "total_cuenta_gastos": 229631.475,
        "factura_proveedor_mxn": 754136.676,
        "prorrateo_gastos": 95626.555,
        "total_embarque": 849763.231,
        "pct_gasto_vs_factura": 0.1268026845,
    }

    print(f"{'Concepto':<28}{'Calculado':>18}{'Esperado (Excel)':>20}{'OK':>5}")
    print("-" * 71)
    todo_ok = True
    for k, exp in esperado.items():
        got = getattr(r, k)
        ok = abs(got - exp) < 0.005
        todo_ok = todo_ok and ok
        print(f"{k:<28}{got:>18,.4f}{exp:>20,.4f}{('si' if ok else 'NO'):>5}")
    print("-" * 71)
    print("RESULTADO:", "TODO COINCIDE" if todo_ok else "HAY DIFERENCIAS")
