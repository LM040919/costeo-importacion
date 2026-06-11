"""App interna de costeo de importación (landed cost).

Ejecutar con:
    .venv/bin/streamlit run app.py
"""

import pandas as pd
import streamlit as st
from streamlit_cookies_controller import CookieController

import admin
import auth
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
_INICIAL = {"orden": "", "proveedor": "", "no_pedimento": "",
            "tipo_cambio": 0.0, "impuestos": 0.0, "iva_aduana": 0.0,
            "factura_proveedor_usd": 0.0, "flete_maritimo_usd": 0.0}
for _campo, _val in _INICIAL.items():
    st.session_state.setdefault(_campo, _val)


def mxn(x: float) -> str:
    return f"${x:,.2f}"


# ----------------------------------------------------------------------------
# Sesión: cookie persistente para no perder el login al recargar.
#   - LECTURA: st.context.cookies (nativo y síncrono al recargar) + respaldo.
#   - ESCRITURA: CookieController, en CADA run con token estable y max_age fijo
#     (sin 'expires' que cambie cada run, para no provocar reruns en bucle).
# ----------------------------------------------------------------------------
cookie_ctrl = CookieController(key="costeo_cookie_ctrl")
_COOKIE_MAXAGE = auth.COOKIE_DIAS * 86400


def _leer_cookie():
    try:
        tok = st.context.cookies.get(auth.COOKIE_NAME)
    except Exception:  # noqa: BLE001
        tok = None
    if not tok:
        try:
            tok = cookie_ctrl.get(auth.COOKIE_NAME)
        except Exception:  # noqa: BLE001
            tok = None
    return tok


def _borrar_cookie():
    st.session_state.pop("_session_token", None)
    try:
        cookie_ctrl.remove(auth.COOKIE_NAME)
    except Exception:  # noqa: BLE001
        pass


# Restaurar sesión desde la cookie si no hay sesión activa
if not auth.current_user() and not st.session_state.get("_no_restore"):
    tok = _leer_cookie()
    if tok and auth.restore_from_token(tok):
        st.session_state["_session_token"] = tok

# Login
if not auth.current_user():
    if auth.login_gate():
        st.session_state["_session_token"] = auth.make_token(auth.current_user()["username"])
        st.session_state.pop("_no_restore", None)
        st.rerun()
    st.stop()

# Ya con sesión: (re)escribir la cookie en cada run para mantenerla viva.
_tok = st.session_state.get("_session_token") or _leer_cookie()
if _tok:
    st.session_state["_session_token"] = _tok
    try:
        cookie_ctrl.set(auth.COOKIE_NAME, _tok, max_age=_COOKIE_MAXAGE, same_site="lax")
    except Exception:  # noqa: BLE001
        pass


# ----------------------------------------------------------------------------
# Navegación (menú lateral)
# ----------------------------------------------------------------------------
INICIO, CALCULAR, TARIFAS, USUARIOS, MI_CUENTA = (
    "Inicio", "Calcular costeo", "Tarifas", "Usuarios", "Mi cuenta")


def opciones_nav():
    opc = [INICIO, CALCULAR]
    if auth.is_gerente():
        opc += [TARIFAS, USUARIOS]
    opc += [MI_CUENTA]
    return opc


def ir(destino):
    """Callback de las tarjetas de Inicio: mueve el menú a otra sección."""
    st.session_state["nav"] = destino


def sidebar_menu():
    u = auth.current_user()
    opc = opciones_nav()
    if st.session_state.get("nav") not in opc:
        st.session_state["nav"] = INICIO
    with st.sidebar:
        st.markdown(f"**{u['name']}**")
        st.caption(u["username"])
        st.caption("Gerente" if auth.is_gerente() else "Usuario")
        st.divider()
        for label in opc:
            st.button(label, width="stretch", key=f"nav_{label}", on_click=ir, args=(label,))
        st.divider()
        if st.button("Cerrar sesión", width="stretch", key="logout"):
            _borrar_cookie()
            auth.logout()
            st.session_state["_no_restore"] = True
            st.rerun()
    return st.session_state["nav"]


# ----------------------------------------------------------------------------
# Vista: Inicio (menú de tarjetas)
# ----------------------------------------------------------------------------
def render_inicio():
    u = auth.current_user()
    st.title(f"📦 Hola, {u['name'].split()[0]}")
    st.caption("¿Qué quieres hacer?")

    acciones = [("🧮", CALCULAR, "Sube el pedimento y la factura del flete, y obtén el costo total del embarque.")]
    if auth.is_gerente():
        acciones += [
            ("🚚", TARIFAS, "Administra el catálogo de tarifas de fletes y agentes aduanales."),
            ("👥", USUARIOS, "Da de alta, edita o desactiva usuarios y sus roles."),
        ]
    acciones += [("🔑", MI_CUENTA, "Cambia tu contraseña.")]

    cols = st.columns(2)
    for i, (icono, titulo, desc) in enumerate(acciones):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f"### {icono} {titulo}")
                st.caption(desc)
                st.button("Abrir", key=f"card_{titulo}", width="stretch", on_click=ir, args=(titulo,))


# ----------------------------------------------------------------------------
# Vista: Calcular costeo (el calculador)
# ----------------------------------------------------------------------------
def render_calcular():
    st.title("🧮 Calcular costeo")
    st.caption(
        "Sube el pedimento para auto-rellenar los datos fiscales, luego elige o captura "
        "los costos de logística. El costo total se recalcula al instante."
    )

    # 1) Pedimento (PDF)
    with st.expander("📄 Pedimento (PDF) — auto-rellenado", expanded=False):
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
                    for campo in CAMPOS_PEDIMENTO_REQ:
                        val = datos.get(campo)
                        st.session_state[campo] = val if val is not None else _INICIAL[campo]
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
                    pd.DataFrame({
                        "Campo": ["Tipo de cambio", "Impuestos sin IVA", "IVA", "Factura proveedor (USD)"],
                        "Valor extraído": [datos.get("tipo_cambio"), datos.get("impuestos"),
                                           datos.get("iva_aduana"), datos.get("factura_proveedor_usd")],
                    }),
                    hide_index=True, width="stretch",
                )

    # 1b) Factura del flete marítimo (CFDI)
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

    # 2) Parámetros
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
        mh_sel = st.selectbox("Maniobras y honorarios", mh_labels, index=None, placeholder="Selecciona…",
                              help="Tarifa fija del agente aduanal (maniobras + honorarios juntos).")
        if mh_sel == OTRO:
            maniobras = st.number_input("Monto maniobras y honorarios (MXN, sin IVA)", value=0.0, step=100.0)
        elif mh_sel:
            maniobras = mh_mapa[mh_sel]
            st.caption(f"Tarifa: ${maniobras:,.2f} (sin IVA)")
        else:
            maniobras = 0.0
        honorarios = 0.0
        otros_demoras = st.number_input("Demoras (si aplica)", value=0.0, step=100.0)
        almacenajes = st.number_input("Almacenaje (si aplica)", value=0.0, step=100.0)
        falsos = st.number_input("Pos. en falso", value=0.0, step=100.0)
        ft_labels, ft_mapa = flete_terrestre_opciones()
        ft_sel = st.selectbox("Flete local / terrestre", ft_labels, index=None, placeholder="Selecciona…",
                              help="Elige proveedor y tipo; el monto se llena solo. Usa 'Otro' para un caso fuera del catálogo.")
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
        tipo_cambio=tipo_cambio, impuestos=impuestos, iva_aduana=iva_aduana,
        maniobras=maniobras, honorarios=honorarios, otros_demoras=otros_demoras,
        almacenajes=almacenajes, flete_local=flete_local, falsos=falsos,
        flete_maritimo_usd=flete_maritimo_usd, factura_proveedor_usd=factura_proveedor_usd,
        cargos_transferencia_usd=cargos_transferencia_usd,
        no_pedimento=no_pedimento, orden=orden, proveedor=proveedor,
    )
    r = calcular(inp)

    # 3) Resultados
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
    m1.metric("TOTAL DE EMBARQUE", mxn(r.total_embarque),
              help="Factura del proveedor (en pesos) + todos los gastos de importación sin IVA. "
                   "Es el costo real sobre el que defines precio de venta y margen.")
    m2.metric("Factura proveedor (MXN)", mxn(r.factura_proveedor_mxn),
              help="La factura del proveedor (USD) convertida a pesos con el tipo de cambio del pedimento.")
    m3.metric("% gasto vs factura", f"{r.pct_gasto_vs_factura:.2%}",
              help="Cuánto le suman los gastos de importación a la mercancía, en porcentaje.")

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
        "El Excel descargado tiene un resumen, el desglose de gastos y el detalle de "
        "extracción, con fórmulas para que puedas seguir editando. Nota: el IVA es "
        "recuperable, por eso no se carga al costo; solo los gastos netos se prorratean."
    )


# ----------------------------------------------------------------------------
# Router
# ----------------------------------------------------------------------------
sel = sidebar_menu()
if sel == CALCULAR:
    render_calcular()
elif sel == TARIFAS and auth.is_gerente():
    admin.render_tarifas_page()
elif sel == USUARIOS and auth.is_gerente():
    admin.render_usuarios_page()
elif sel == MI_CUENTA:
    admin.render_mi_cuenta_page()
else:
    render_inicio()
