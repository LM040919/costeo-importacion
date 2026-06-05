"""App interna de costeo de importación (landed cost).

Ejecutar con:
    .venv/bin/streamlit run app.py
"""

import pandas as pd
import streamlit as st

import descarga
import flete
import pedimento
from costeo import CosteoInputs, calcular
from tarifas import OTRO, flete_terrestre_opciones, maniobras_honorarios_opciones

st.set_page_config(page_title="Costeo de importación", page_icon="📦", layout="wide")

# Campos que se auto-rellenan desde documentos (manejados vía session_state).
# REQ: siempre presentes en el pedimento; se sobreescriben al subir uno nuevo.
# OPC: a veces no aparecen (ej. la orden); solo se llenan si el documento las trae.
CAMPOS_PEDIMENTO_REQ = ("proveedor", "no_pedimento", "tipo_cambio", "impuestos", "iva_aduana", "factura_proveedor_usd")
CAMPOS_PEDIMENTO_OPC = ("orden",)
CAMPOS_PEDIMENTO = CAMPOS_PEDIMENTO_REQ + CAMPOS_PEDIMENTO_OPC
# El formulario arranca en blanco; se llena al subir documentos o capturando a mano.
_INICIAL = {"orden": "", "proveedor": "", "no_pedimento": "",
            "tipo_cambio": 0.0, "impuestos": 0.0, "iva_aduana": 0.0,
            "factura_proveedor_usd": 0.0, "flete_maritimo_usd": 0.0}
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
        "**impuestos** (DTA+PRV), el **IVA** (IVA+IVA/PRV) y la "
        "**factura del proveedor** (USD). Los gastos de logística se capturan abajo."
    )
    pdf = st.file_uploader("Arrastra el pedimento aquí", type="pdf", key="up_ped")
    if pdf is not None:
        file_id = (pdf.name, pdf.size)
        if st.session_state.get("_ped_file") != file_id:
            try:
                datos = pedimento.extraer(pdf)
                st.session_state["_ped_file"] = file_id
                st.session_state["_ped_datos"] = datos
                # Los campos siempre presentes se reinician al cargar otro pedimento.
                for campo in CAMPOS_PEDIMENTO_REQ:
                    val = datos.get(campo)
                    st.session_state[campo] = val if val is not None else _INICIAL[campo]
                # Los opcionales (orden) solo se llenan si el pedimento las trae, para
                # no borrar lo que ya capturó otra fuente (p. ej. la factura del flete).
                for campo in CAMPOS_PEDIMENTO_OPC:
                    val = datos.get(campo)
                    if val is not None:
                        st.session_state[campo] = val
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
                        "Campo": ["Tipo de cambio", "Impuestos sin IVA",
                                  "IVA", "Factura proveedor (USD)"],
                        "Valor extraído": [datos.get("tipo_cambio"), datos.get("impuestos"),
                                           datos.get("iva_aduana"), datos.get("factura_proveedor_usd")],
                    }
                ),
                hide_index=True, width="stretch",
            )

# ----------------------------------------------------------------------------
# 1b) Factura del flete marítimo (PDF/CFDI) — auto-rellenado
# ----------------------------------------------------------------------------
with st.expander("🚢 Factura del flete marítimo (PDF) — auto-rellenado", expanded=False):
    st.write(
        "Sube la factura (CFDI) del forwarder y se rellena solo el campo "
        "**Flete marítimo (USD)**. Si la factura trae la orden interna "
        "(P.O. Reference), también se autocompleta."
    )
    pdf_flete = st.file_uploader("Arrastra la factura aquí", type="pdf", key="up_flete")
    if pdf_flete is not None:
        file_id = (pdf_flete.name, pdf_flete.size)
        if st.session_state.get("_flete_file") != file_id:
            try:
                datos_f = flete.extraer(pdf_flete)
                st.session_state["_flete_file"] = file_id
                st.session_state["_flete_datos"] = datos_f
                sub = datos_f.get("flete_subtotal")
                if sub is not None and datos_f.get("moneda") == "USD":
                    st.session_state["flete_maritimo_usd"] = sub
                if datos_f.get("orden"):
                    st.session_state["orden"] = datos_f["orden"]
            except Exception as e:  # noqa: BLE001
                st.error(f"No se pudo leer la factura: {e}")
        datos_f = st.session_state.get("_flete_datos", {})
        if datos_f:
            sub = datos_f.get("flete_subtotal")
            moneda = datos_f.get("moneda")
            if sub is not None:
                st.success(
                    f"Factura leída ({datos_f.get('_paginas')} páginas). "
                    f"Flete marítimo: ${sub:,.2f} {moneda or ''}."
                )
            else:
                st.warning("No pude detectar el subtotal en la factura.")
            if moneda and moneda != "USD":
                st.warning(
                    f"La factura está en {moneda}; el campo 'Flete marítimo' es USD. "
                    "No auto-rellené para evitar errores; captura manualmente."
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
    iva_aduana = st.number_input("IVA (MXN)", step=100.0, key="iva_aduana")

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
    otros_demoras = st.number_input("Demoras (si aplica)", value=0.0, step=100.0)
    almacenajes = st.number_input("Almacenaje (si aplica)", value=0.0, step=100.0)
    falsos = st.number_input("Pos. en falso", value=0.0, step=100.0)
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

with c3:
    st.markdown("**Mercancía y flete marítimo (USD)**")
    factura_proveedor_usd = st.number_input("Factura del proveedor", step=100.0, key="factura_proveedor_usd")
    flete_maritimo_usd = st.number_input("Flete marítimo", step=10.0, key="flete_maritimo_usd")
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

nombre_base = inp.orden or (inp.no_pedimento or "sin_referencia").replace(" ", "_")
st.download_button(
    label="📥 Descargar costeo en Excel",
    data=descarga.generar_xlsx(
        inp, r,
        detalle_pedimento=st.session_state.get("_ped_datos", {}),
        mh_label=mh_sel if mh_sel and mh_sel != OTRO else None,
        ft_label=ft_sel if ft_sel and ft_sel != OTRO else None,
    ),
    file_name=f"COSTEO ESTIMADO __ {nombre_base}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    width="stretch",
)
st.caption(
    "El Excel descargado replica la plantilla de Marisa (mismos campos y "
    "totales), con fórmulas para que puedas seguir editando, e incluye al "
    "final un bloque con el detalle de las extracciones del pedimento y las "
    "tarifas elegidas del catálogo. Nota: el IVA es recuperable, por eso no "
    "se carga al costo; solo los gastos netos se prorratean."
)
