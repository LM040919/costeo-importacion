"""Autenticación simple (usuario + contraseña) y roles.

Los usuarios viven en los *secrets* de Streamlit (no en el repo). Cada usuario
guarda un hash PBKDF2-SHA256 de su contraseña — nunca la contraseña en claro.

Estructura esperada en secrets (.streamlit/secrets.toml o dashboard de Cloud):

    [[auth.users]]
    username = "isis.garcia@marvelsa.com"
    name = "Isis García López"
    role = "gerente"            # "gerente" o "usuario"
    password = "<salt_hex>:<hash_hex>"

Roles:
    - gerente: podrá administrar catálogo y usuarios (CRUD) — se habilita por fases.
    - usuario: solo usa el calculador y descarga el Excel.
"""

import hashlib
import hmac

import streamlit as st

_ITERATIONS = 200_000
_ALGO = "sha256"


def _hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(_ALGO, password.encode("utf-8"), salt, _ITERATIONS)


def make_password(password: str) -> str:
    """Genera el valor 'salt_hex:hash_hex' para guardar en secrets."""
    import os

    salt = os.urandom(16)
    return f"{salt.hex()}:{_hash(password, salt).hex()}"


def verify(password: str, stored: str) -> bool:
    try:
        salt_hex, hash_hex = stored.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(_hash(password, salt), expected)


def _users():
    try:
        return list(st.secrets["auth"]["users"])
    except Exception:  # noqa: BLE001 — sin secrets configurados
        return []


def _find(username: str):
    objetivo = (username or "").strip().lower()
    for entry in _users():
        if str(entry.get("username", "")).strip().lower() == objetivo:
            return entry
    return None


def current_user():
    return st.session_state.get("_auth_user")


def is_gerente() -> bool:
    u = current_user()
    return bool(u) and u.get("role") == "gerente"


def login_gate() -> bool:
    """Si no hay sesión, renderiza el login y devuelve False. Si hay, True."""
    if current_user():
        return True

    st.title("📦 Costeo de importación")
    st.caption("Inicia sesión para continuar.")

    if not _users():
        st.error(
            "No hay usuarios configurados. Falta el bloque [auth] en los secrets "
            "de la app (Manage app → Settings → Secrets en Streamlit Cloud)."
        )
        return False

    with st.form("login"):
        username = st.text_input("Usuario (correo)")
        password = st.text_input("Contraseña", type="password")
        ok = st.form_submit_button("Entrar")

    if ok:
        entry = _find(username)
        if entry and verify(password, str(entry.get("password", ""))):
            st.session_state["_auth_user"] = {
                "username": entry["username"],
                "name": entry.get("name", entry["username"]),
                "role": entry.get("role", "usuario"),
            }
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")
    return False


def sidebar_session():
    """Muestra quién está logueado, su rol y el botón de cerrar sesión."""
    u = current_user()
    if not u:
        return
    with st.sidebar:
        st.markdown(f"**{u['name']}**")
        st.caption(u["username"])
        rol = "Gerente" if u["role"] == "gerente" else "Usuario"
        st.caption(f"Rol: {rol}")
        if is_gerente():
            st.info(
                "Acceso de gerente. La administración de tarifas y usuarios "
                "se habilita en la siguiente fase."
            )
        if st.button("Cerrar sesión", width="stretch"):
            del st.session_state["_auth_user"]
            st.rerun()
