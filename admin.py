"""UI de administración (solo gerentes) y 'Mi cuenta' (todos).

CRUD de tarifas y usuarios contra la base de datos. Si no hay base de datos
configurada, se muestra un aviso y nada se puede editar todavía.
"""

import pandas as pd
import streamlit as st

import auth
import db

CATEGORIAS = {
    "flete_terrestre": "Flete terrestre",
    "maniobras_honorarios": "Maniobras y honorarios",
}


def _flash(msg):
    """Guarda un mensaje para mostrarlo tras el st.rerun()."""
    st.session_state["_admin_flash"] = msg


def _mostrar_flash():
    msg = st.session_state.pop("_admin_flash", None)
    if msg:
        st.success(msg)


# ==================================================================
# Mi cuenta (cualquier usuario logueado): cambiar contraseña
# ==================================================================
def render_mi_cuenta_page():
    u = auth.current_user()
    if not u:
        return
    st.subheader("🔑 Mi cuenta")
    st.caption(f"{u['name']} · {u['username']} · "
               f"{'Gerente' if u['role'] == 'gerente' else 'Usuario'}")
    st.divider()
    st.markdown("**Cambiar contraseña**")
    if not db.enabled():
        st.info("El cambio de contraseña se habilita al conectar la base de datos.")
        return
    with st.form("cambiar_pw", clear_on_submit=True):
        actual = st.text_input("Contraseña actual", type="password")
        nueva = st.text_input("Nueva contraseña", type="password")
        confirma = st.text_input("Confirmar nueva", type="password")
        ok = st.form_submit_button("Cambiar contraseña")
    if ok:
        if nueva != confirma:
            st.error("La nueva contraseña y su confirmación no coinciden.")
        else:
            exito, msg = auth.cambiar_password(u["username"], actual, nueva)
            (st.success if exito else st.error)(msg)


# ==================================================================
# Administración (solo gerentes) — páginas de tarifas y usuarios
# ==================================================================
def _sin_db():
    st.info(
        "Esta sección requiere la base de datos (Supabase). Mientras no esté "
        "conectada, el catálogo y los usuarios vienen de la configuración del código."
    )


def render_tarifas_page():
    if not auth.is_gerente():
        return
    st.subheader("🚚 Tarifas")
    if not db.enabled():
        _sin_db()
        return
    _mostrar_flash()
    _admin_tarifas()


def render_usuarios_page():
    if not auth.is_gerente():
        return
    st.subheader("👥 Usuarios")
    if not db.enabled():
        _sin_db()
        return
    _mostrar_flash()
    _admin_usuarios()


def _admin_tarifas():
    tarifas = db.list_tarifas(incluir_inactivas=True)
    if tarifas:
        df = pd.DataFrame(tarifas)[["categoria", "proveedor", "tipo", "tarifa", "activo"]]
        df["categoria"] = df["categoria"].map(CATEGORIAS).fillna(df["categoria"])
        st.dataframe(df, hide_index=True, width="stretch",
                     column_config={"tarifa": st.column_config.NumberColumn(format="$%.2f")})
    else:
        st.caption("Aún no hay tarifas. Agrega la primera abajo.")

    st.markdown("**Agregar tarifa**")
    with st.form("add_tarifa", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([2, 2, 1.5, 1.5])
        cat = c1.selectbox("Categoría", list(CATEGORIAS), format_func=lambda k: CATEGORIAS[k])
        prov = c2.text_input("Proveedor")
        tipo = c3.text_input("Tipo (opcional)", help="Ej. Sencillo / Full. Vacío para maniobras.")
        monto = c4.number_input("Tarifa (MXN, sin IVA)", min_value=0.0, step=100.0)
        if st.form_submit_button("Agregar") and prov.strip():
            db.insert_tarifa(cat, prov.strip(), tipo.strip() or None, monto)
            _flash(f"Tarifa agregada: {prov} (${monto:,.2f}).")
            st.rerun()

    if tarifas:
        st.markdown("**Editar o eliminar**")
        etiqueta = {
            t["id"]: f"{CATEGORIAS.get(t['categoria'], t['categoria'])} · {t['proveedor']}"
                     f"{' · ' + t['tipo'] if t.get('tipo') else ''} (${float(t['tarifa']):,.2f})"
            for t in tarifas
        }
        sel = st.selectbox("Tarifa", list(etiqueta), format_func=lambda i: etiqueta[i],
                           index=None, placeholder="Selecciona…", key="edit_tarifa_sel")
        if sel is not None:
            actual = next(t for t in tarifas if t["id"] == sel)
            with st.form("edit_tarifa"):
                c1, c2, c3 = st.columns([2, 1.5, 1.5])
                prov = c1.text_input("Proveedor", value=actual["proveedor"])
                tipo = c2.text_input("Tipo", value=actual.get("tipo") or "")
                monto = c3.number_input("Tarifa", value=float(actual["tarifa"]), min_value=0.0, step=100.0)
                activo = st.checkbox("Activa", value=bool(actual["activo"]))
                cg, cd = st.columns(2)
                guardar = cg.form_submit_button("Guardar cambios", width="stretch")
                eliminar = cd.form_submit_button("Eliminar", width="stretch")
            if guardar:
                db.update_tarifa(sel, proveedor=prov.strip(), tipo=tipo.strip() or None,
                                 tarifa=monto, activo=activo)
                _flash("Tarifa actualizada.")
                st.session_state.pop("edit_tarifa_sel", None)  # cierra el formulario
                st.rerun()
            if eliminar:
                db.delete_tarifa(sel)
                _flash("Tarifa eliminada.")
                st.session_state.pop("edit_tarifa_sel", None)
                st.rerun()


def _admin_usuarios():
    usuarios = db.list_usuarios(incluir_inactivos=True)
    if usuarios:
        df = pd.DataFrame(usuarios)[["username", "name", "role", "activo"]]
        df["role"] = df["role"].map({"gerente": "Gerente", "usuario": "Usuario"}).fillna(df["role"])
        st.dataframe(df, hide_index=True, width="stretch",
                     column_config={"username": "Usuario", "name": "Nombre",
                                    "role": "Rol", "activo": "Activo"})

    st.markdown("**Agregar usuario**")
    with st.form("add_user", clear_on_submit=True):
        c1, c2 = st.columns(2)
        username = c1.text_input("Usuario (correo)")
        name = c2.text_input("Nombre completo")
        c3, c4 = st.columns(2)
        role = c3.selectbox("Rol", ["usuario", "gerente"],
                            format_func=lambda r: "Gerente" if r == "gerente" else "Usuario")
        pw = c4.text_input("Contraseña inicial", type="password")
        if st.form_submit_button("Agregar usuario"):
            if not username.strip() or not name.strip() or len(pw) < 6:
                st.error("Completa correo, nombre y una contraseña de al menos 6 caracteres.")
            else:
                db.upsert_usuario(username, name.strip(), role, auth.make_password(pw))
                _flash(f"Usuario {username.strip().lower()} agregado.")
                st.rerun()

    if usuarios:
        st.markdown("**Editar o eliminar**")
        etiqueta = {u["username"]: f"{u['name']} ({u['username']})" for u in usuarios}
        sel = st.selectbox("Usuario", list(etiqueta), format_func=lambda k: etiqueta[k],
                           index=None, placeholder="Selecciona…", key="edit_user_sel")
        if sel is not None:
            actual = next(u for u in usuarios if u["username"] == sel)
            yo = auth.current_user()["username"]
            with st.form("edit_user"):
                name = st.text_input("Nombre", value=actual["name"])
                c1, c2 = st.columns(2)
                role = c1.selectbox("Rol", ["usuario", "gerente"],
                                    index=0 if actual["role"] == "usuario" else 1,
                                    format_func=lambda r: "Gerente" if r == "gerente" else "Usuario")
                activo = c2.checkbox("Activo", value=bool(actual["activo"]))
                nueva_pw = st.text_input("Restablecer contraseña (opcional)", type="password",
                                         help="Déjalo vacío para no cambiarla.")
                cg, cd = st.columns(2)
                guardar = cg.form_submit_button("Guardar cambios", width="stretch")
                eliminar = cd.form_submit_button("Eliminar usuario", width="stretch")
            if guardar:
                pw_hash = auth.make_password(nueva_pw) if nueva_pw else None
                db.upsert_usuario(sel, name.strip(), role, pw_hash, activo)
                _flash("Usuario actualizado.")
                st.session_state.pop("edit_user_sel", None)  # cierra el formulario
                st.rerun()
            if eliminar:
                if sel == yo:
                    st.error("No puedes eliminar tu propia cuenta mientras la usas.")
                else:
                    db.delete_usuario(sel)
                    _flash("Usuario eliminado.")
                    st.session_state.pop("edit_user_sel", None)
                    st.rerun()
