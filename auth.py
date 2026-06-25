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
import time

import streamlit as st

import db

_ITERATIONS = 200_000
_ALGO = "sha256"

# Cookie de sesión persistente (para no perder la sesión al recargar).
COOKIE_NAME = "costeo_session"
COOKIE_DIAS = 7


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
    """Usuarios desde la base de datos si está configurada; si no, desde secrets."""
    if db.enabled():
        return db.list_usuarios()
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


# ------------------------------------------------------------------
# Token de sesión (firmado) para la cookie persistente
# ------------------------------------------------------------------
def _signing_key() -> bytes:
    """Clave para firmar el token de sesión, derivada de un secreto estable
    del servidor (el DSN de Postgres). Así el token no se puede falsificar con
    una constante pública, y se mantiene consistente entre recargas."""
    base = None
    for ruta in (("postgres", "dsn"), ("auth", "cookie_secret")):
        try:
            base = st.secrets[ruta[0]][ruta[1]]
            if base:
                break
        except Exception:  # noqa: BLE001
            base = None
    if not base:
        base = "costeo-dev-signing-key"
    return hashlib.sha256(b"sig:" + str(base).encode()).digest()


def make_token(username: str) -> str:
    exp = int(time.time()) + COOKIE_DIAS * 86400
    msg = f"{username}|{exp}"
    sig = hmac.new(_signing_key(), msg.encode(), hashlib.sha256).hexdigest()
    return f"{msg}|{sig}"


def _parse_token(token: str):
    try:
        username, exp, sig = token.split("|")
        if int(exp) < time.time():
            return None
        good = hmac.new(_signing_key(), f"{username}|{exp}".encode(), hashlib.sha256).hexdigest()
        return username if hmac.compare_digest(good, sig) else None
    except Exception:  # noqa: BLE001
        return None


def restore_from_token(token: str) -> bool:
    """Restaura la sesión desde un token de cookie válido. Devuelve True si pudo."""
    username = _parse_token(token or "")
    if not username:
        return False
    entry = _find(username)
    if not entry:
        return False
    st.session_state["_auth_user"] = {
        "username": entry["username"],
        "name": entry.get("name", entry["username"]),
        "role": entry.get("role", "usuario"),
    }
    return True


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
            "(o conectar la base de datos) en Manage app → Settings → Secrets."
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
            return True  # el caller guarda la cookie y recarga
        st.error("Usuario o contraseña incorrectos.")
    return False


def logout():
    st.session_state.pop("_auth_user", None)


def cambiar_password(username: str, actual: str, nueva: str) -> tuple[bool, str]:
    """Cambia la contraseña del usuario tras verificar la actual.

    Requiere base de datos (los secrets son de solo lectura en runtime).
    Devuelve (ok, mensaje).
    """
    if not db.enabled():
        return False, "El cambio de contraseña requiere base de datos (Fase 2)."
    entry = db.get_usuario(username)
    if not entry or not verify(actual, str(entry.get("password", ""))):
        return False, "La contraseña actual no es correcta."
    if len(nueva) < 6:
        return False, "La nueva contraseña debe tener al menos 6 caracteres."
    db.set_password(username, make_password(nueva))
    return True, "Contraseña actualizada."
