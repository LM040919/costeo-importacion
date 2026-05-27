"""App interna de costeo de importación (landed cost).

Ejecutar con:
    .venv/bin/streamlit run app.py
"""

import pandas as pd
import streamlit as st

import pedimento
from costeo import CosteoInputs, calcular
from tarifas import OTRO, flete_terrestre_opciones, maniobras_honorarios_opciones

st.set_page_config(page_title="Costeo de importación", page_icon="📦", layout="wide")

# Campos que se auto-rellenan desde el pedimento (manejados vía session_state).
CAMPOS_PEDIMENTO = ("orden", "proveedor", "no_pedimento", "tipo_cambio", "impuestos", "iva_aduana", "factura_proveedor_usd")
# El formulario arranca en blanco; se llena al subir el pedimento o capturando a mano.
_INICIAL = {"orden": "", "proveedor": "", "no_pedimento": "",
            "tipo_cambio": 0.0, "impuestos": 0.0, "iva_aduana": 0.0, "factura_proveedor_usd": 0.0}
for _campo, _val in _INICIAL.items():
    st.session_state.setdefault(_campo, _val)


def mxn(x: float) -> str:
    return f"${x:,.2f}"


st.title("📦 Costeo de importación")
st.caption(
    "Sube el pedimento para auto-rellenar los datos fiscales, luego elige o captura "
    "los costos de logística. El costo total se recalcula al instante."
)

# ----------------------------------------------------------------------------
# 1) Pedimento (PDF) — extracción y auto-rellenado
# ----------------------------------------------------------------------------
with st.expander("📄 Pedimento (PDF) — auto-rellenado", expanded=True):
    st.write(
        "Al subir el pedimento se rellenan solos el **tipo de cambio**, los "
        "**impuestos** (DTA+PRV), el **IVA de aduana** (IVA+IVA/PRV) y la "
        "**factura del proveedor** (USD). Los gastos de logística se capturan abajo."
    )
    pdf = st.file_uploader("Arrastra el pedimento aquí", type="pdf")
    if pdf is not None:
        file_id = (pdf.name, pdf.size)
        if st.session_state.get("_ped_file") != file_id:
            try:
                datos = pedimento.extraer(pdf)
                st.session_state["_ped_file"] = file_id
                st.session_state["_ped_datos"] = datos
                for campo in CAMPOS_PEDIMENTO:
                    val = datos.get(campo)
                    st.session_state[campo] = val if val is not None else _INICIAL[campo]
                st.rerun()
            except Exception as e:  # noqa: BLE001
                st.error(f"No se pudo leer el pedimento: {e}")
        datos = st.session_state.get("_ped_datos", {})
        if datos:
            st.success(
                f"Datos extraídos del pedimento {datos.get('no_pedimento')} "
                f"({datos.get('_paginas')} páginas). Revísalos abajo y ajusta si hace falta."
            )
            st.dataframe(
                pd.DataFrame(
                    {
                        "Campo": ["Tipo de cambio", "Impuestos (DTA+PRV)",
                                  "IVA aduana (IVA+IVA/PRV)", "Factura proveedor (USD)"],
                        "Valor extraído": [datos.get("tipo_cambio"), datos.get("impuestos"),
                                           datos.get("iva_aduana"), datos.get("factura_proveedor_usd")],
                    }
                ),
                hide_index=True, width="stretch",
            )

# ----------------------------------------------------------------------------
# 2) Captura de parámetros
# ----------------------------------------------------------------------------
st.subheader("Parámetros del embarque")
c1, c2, c3 = st.columns(3)

with c1:
    st.markdown("**Datos del pedimento**")
    orden = st.text_input("Orden", key="orden")
    no_pedimento = st.text_input("No. pedimento", key="no_pedimento")
    proveedor = st.text_input("Proveedor", key="proveedor")
    tipo_cambio = st.number_input("Tipo de cambio (MXN/USD)", step=0.001, format="%.4f", key="tipo_cambio")
    impuestos = st.number_input("Impuestos sin IVA (MXN)", step=100.0, key="impuestos")
    iva_aduana = st.number_input("IVA de aduana (MXN)", step=100.0, key="iva_aduana")

with c2:
    st.markdown("**Gastos de agente aduanal / logística (MXN)**")
    mh_labels, mh_mapa = maniobras_honorarios_opciones()
    mh_sel = st.selectbox(
        "Maniobras y honorarios", mh_labels, index=None, placeholder="Selecciona…",
        help="Tarifa fija del agente aduanal (maniobras + honorarios juntos).",
    )
    if mh_sel == OTRO:
        maniobras = st.number_input("Monto maniobras y honorarios (MXN, sin IVA)", value=0.0, step=100.0)
    elif mh_sel:
        maniobras = mh_mapa[mh_sel]
        st.caption(f"Tarifa: ${maniobras:,.2f} (sin IVA)")
    else:
        maniobras = 0.0
    honorarios = 0.0  # van incluidos en la tarifa de maniobras y honorarios
    otros_demoras = st.number_input("Otros (demoras)", value=0.0, step=100.0)
    almacenajes = st.number_input("Almacenajes (si aplica)", value=0.0, step=100.0)
    falsos = st.number_input("Falsos", value=0.0, step=100.0)
    ft_labels, ft_mapa = flete_terrestre_opciones()
    ft_sel = st.selectbox(
        "Flete local / terrestre", ft_labels, index=None, placeholder="Selecciona…",
        help="Elige proveedor y tipo; el monto se llena solo. Usa 'Otro' para un caso fuera del catálogo.",
    )
    if ft_sel == OTRO:
        flete_local = st.number_input("Monto flete local (MXN, sin IVA)", value=0.0, step=100.0)
    elif ft_sel:
        flete_local = ft_mapa[ft_sel]
        st.caption(f"Tarifa: ${flete_local:,.2f} (sin IVA)")
    else:
        flete_local = 0.0
    ajuste_iva_flete_local = st.number_input(
        "Ajuste IVA flete local", value=0.0, step=10.0,
        help="Monto fijo que la plantilla resta al IVA del flete local (celda D26 del Excel).",
    )

with c3:
    st.markdown("**Mercancía y flete marítimo (USD)**")
    factura_proveedor_usd = st.number_input("Factura del proveedor", step=100.0, key="factura_proveedor_usd")
    flete_maritimo_usd = st.number_input("Flete marítimo", value=0.0, step=10.0)
    cargos_transferencia_usd = st.number_input("Cargos por transferencia", value=0.0, step=10.0)

inp = CosteoInputs(
    tipo_cambio=tipo_cambio,
    impuestos=impuestos,
    iva_aduana=iva_aduana,
    maniobras=maniobras,
    honorarios=honorarios,
    otros_demoras=otros_demoras,
    almacenajes=almacenajes,
    flete_local=flete_local,
    falsos=falsos,
    flete_maritimo_usd=flete_maritimo_usd,
    factura_proveedor_usd=factura_proveedor_usd,
    cargos_transferencia_usd=cargos_transferencia_usd,
    ajuste_iva_flete_local=ajuste_iva_flete_local,
    no_pedimento=no_pedimento,
    orden=orden,
    proveedor=proveedor,
)
r = calcular(inp)

# ----------------------------------------------------------------------------
# 3) Resultados
# ----------------------------------------------------------------------------
st.divider()
st.subheader("Resultado")
st.caption(
    "El **total de embarque** es tu costo real de la mercancía ya en bodega: "
    "factura del proveedor (en pesos) + los gastos de importación sin IVA."
)

for adv in r.advertencias:
    st.warning(adv)

if (factura_proveedor_usd or impuestos) and maniobras == 0 and flete_local == 0 and flete_maritimo_usd == 0:
    st.info(
        "Aún no agregas costos de logística (fletes / maniobras), así que el total "
        "solo incluye la factura y los impuestos del pedimento. Elige las tarifas "
        "arriba para completar el costeo."
    )

m1, m2, m3 = st.columns(3)
m1.metric(
    "TOTAL DE EMBARQUE", mxn(r.total_embarque),
    help="Factura del proveedor (en pesos) + todos los gastos de importación sin IVA. "
         "Es el costo real sobre el que defines precio de venta y margen.",
)
m2.metric(
    "Factura proveedor (MXN)", mxn(r.factura_proveedor_mxn),
    help="La factura del proveedor (USD) convertida a pesos con el tipo de cambio del pedimento.",
)
m3.metric(
    "% gasto vs factura", f"{r.pct_gasto_vs_factura:.2%}",
    help="Cuánto le suman los gastos de importación a la mercancía, en porcentaje. "
         "Sube conforme agregas fletes y maniobras.",
)

col_izq, col_der = st.columns(2)

with col_izq:
    st.markdown("**Cuenta de gastos**")
    st.caption("Desglose de cada gasto de importación; las últimas filas son los totales (sin IVA, IVA y total).")
    gastos = pd.DataFrame(
        {
            "Concepto": [
                "Impuestos (sin IVA)",
                "Maniobras y honorarios",
                "Otros (demoras)",
                "Almacenajes",
                "Flete marítimo",
                "Flete local",
                "Falsos",
                "TOTAL gastos sin IVA",
                "TOTAL IVA",
                "TOTAL cuenta de gastos",
            ],
            "Monto (MXN)": [
                impuestos, maniobras, otros_demoras, almacenajes,
                r.flete_maritimo_mxn, flete_local, falsos,
                r.total_gastos_sin_iva, r.total_gastos_iva, r.total_cuenta_gastos,
            ],
        }
    )
    st.dataframe(
        gastos.style.format({"Monto (MXN)": "{:,.2f}"}),
        hide_index=True, width="stretch",
    )

with col_der:
    st.markdown("**Costo del embarque**")
    embarque = pd.DataFrame(
        {
            "Concepto": [
                "Factura proveedor (MXN)",
                "Cargos por transferencia (MXN)",
                "Prorrateo gastos México",
                "TOTAL DE EMBARQUE",
            ],
            "Monto (MXN)": [
                r.factura_proveedor_mxn, r.cargos_transferencia_mxn,
                r.prorrateo_gastos, r.total_embarque,
            ],
        }
    )
    st.dataframe(
        embarque.style.format({"Monto (MXN)": "{:,.2f}"}),
        hide_index=True, width="stretch",
    )
    st.caption(
        "Nota: el IVA es recuperable, por eso no se carga al costo. Solo los gastos "
        "netos (sin IVA) se prorratean sobre la mercancía."
    )
