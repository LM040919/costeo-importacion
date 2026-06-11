"""Acceso a la base de datos (Supabase / PostgREST).

Toda la configuración viene de los secrets de Streamlit:

    [supabase]
    url = "https://<proyecto>.supabase.co"
    key = "<service_role key>"   # server-side; nunca se expone al navegador

Si no hay sección [supabase] en los secrets, `enabled()` devuelve False y la
app sigue funcionando con los datos de respaldo (usuarios en secrets, catálogo
hardcodeado). Así la transición a base de datos no rompe nada en vivo.

Las tablas (costeo_usuarios, costeo_tarifas) tienen RLS activado sin policies,
por lo que solo la service_role key puede leer/escribir.
"""

import streamlit as st


@st.cache_resource(show_spinner=False)
def _client():
    """Crea el cliente de Supabase desde secrets, o None si no está configurado."""
    try:
        cfg = st.secrets["supabase"]
        url, key = cfg["url"], cfg["key"]
    except Exception:  # noqa: BLE001 — sin secrets [supabase]
        return None
    if not url or not key:
        return None
    try:
        from supabase import create_client

        return create_client(url, key)
    except Exception as e:  # noqa: BLE001
        st.warning(f"No se pudo conectar a la base de datos: {e}")
        return None


def enabled() -> bool:
    return _client() is not None


# ------------------------------------------------------------------
# Usuarios
# ------------------------------------------------------------------
def list_usuarios(incluir_inactivos: bool = False):
    cli = _client()
    if cli is None:
        return []
    q = cli.table("costeo_usuarios").select("*").order("role").order("name")
    if not incluir_inactivos:
        q = q.eq("activo", True)
    return q.execute().data or []


def get_usuario(username: str):
    cli = _client()
    if cli is None:
        return None
    rows = (
        cli.table("costeo_usuarios")
        .select("*")
        .eq("username", (username or "").strip().lower())
        .limit(1)
        .execute()
        .data
    )
    return rows[0] if rows else None


def upsert_usuario(username: str, name: str, role: str, password: str = None, activo: bool = True):
    """Crea o actualiza un usuario. Si password es None, no toca la contraseña."""
    cli = _client()
    if cli is None:
        return
    fila = {
        "username": (username or "").strip().lower(),
        "name": name,
        "role": role,
        "activo": activo,
    }
    if password is not None:
        fila["password"] = password
    cli.table("costeo_usuarios").upsert(fila).execute()


def set_password(username: str, password: str):
    cli = _client()
    if cli is None:
        return
    cli.table("costeo_usuarios").update({"password": password}).eq(
        "username", (username or "").strip().lower()
    ).execute()


def delete_usuario(username: str):
    cli = _client()
    if cli is None:
        return
    cli.table("costeo_usuarios").delete().eq(
        "username", (username or "").strip().lower()
    ).execute()


# ------------------------------------------------------------------
# Tarifas
# ------------------------------------------------------------------
def list_tarifas(categoria: str = None, incluir_inactivas: bool = False):
    cli = _client()
    if cli is None:
        return []
    q = cli.table("costeo_tarifas").select("*").order("proveedor").order("tipo")
    if categoria:
        q = q.eq("categoria", categoria)
    if not incluir_inactivas:
        q = q.eq("activo", True)
    return q.execute().data or []


def insert_tarifa(categoria: str, proveedor: str, tipo, tarifa: float, activo: bool = True):
    cli = _client()
    if cli is None:
        return
    cli.table("costeo_tarifas").insert(
        {
            "categoria": categoria,
            "proveedor": proveedor,
            "tipo": (tipo or None),
            "tarifa": tarifa,
            "activo": activo,
        }
    ).execute()


def update_tarifa(id_: int, **campos):
    cli = _client()
    if cli is None:
        return
    cli.table("costeo_tarifas").update(campos).eq("id", id_).execute()


def delete_tarifa(id_: int):
    cli = _client()
    if cli is None:
        return
    cli.table("costeo_tarifas").delete().eq("id", id_).execute()
