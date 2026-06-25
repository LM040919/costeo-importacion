"""Acceso a la base de datos (PostgreSQL).

Conexión por secrets de Streamlit:

    [postgres]
    dsn = "postgresql://usuario:password@host:5432/basededatos"

En Coolify, usa la cadena de conexión INTERNA del recurso PostgreSQL (la que
apunta al hostname del servicio dentro de la red de Docker), para que la app
hable con la base sin salir a internet.

Si no hay [postgres] en los secrets (o no conecta), enabled() devuelve False y
la app sigue funcionando con los datos de respaldo (usuarios en secrets,
catálogo hardcodeado). Así la transición no rompe nada.

Tablas: costeo_usuarios, costeo_tarifas (ver schema.sql).
"""

import streamlit as st


@st.cache_resource(show_spinner=False)
def _dsn():
    """Devuelve el DSN si está configurado Y la conexión funciona; si no, None."""
    try:
        dsn = st.secrets["postgres"]["dsn"]
    except Exception:  # noqa: BLE001 — sin secrets [postgres]
        return None
    if not dsn:
        return None
    try:
        import psycopg2

        conn = psycopg2.connect(dsn, connect_timeout=5)
        conn.close()
        return dsn
    except Exception as e:  # noqa: BLE001
        st.warning(f"No se pudo conectar a la base de datos: {e}")
        return None


def enabled() -> bool:
    return _dsn() is not None


def _run(sql, params=None, fetch=True):
    """Ejecuta SQL (autocommit). Devuelve lista de dicts si fetch, si no []."""
    dsn = _dsn()
    if dsn is None:
        return []
    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(dsn, connect_timeout=5)
    try:
        conn.autocommit = True
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            if fetch and cur.description:
                return [dict(r) for r in cur.fetchall()]
            return []
    finally:
        conn.close()


# ------------------------------------------------------------------
# Usuarios
# ------------------------------------------------------------------
def list_usuarios(incluir_inactivos: bool = False):
    sql = "SELECT * FROM costeo_usuarios"
    if not incluir_inactivos:
        sql += " WHERE activo = TRUE"
    sql += " ORDER BY role, name"
    return _run(sql)


def get_usuario(username: str):
    rows = _run(
        "SELECT * FROM costeo_usuarios WHERE username = %s LIMIT 1",
        ((username or "").strip().lower(),),
    )
    return rows[0] if rows else None


def upsert_usuario(username: str, name: str, role: str, password: str = None, activo: bool = True):
    """Crea o actualiza un usuario. Si password es None, no toca la contraseña."""
    u = (username or "").strip().lower()
    if password is not None:
        _run(
            """
            INSERT INTO costeo_usuarios (username, name, role, password, activo)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (username) DO UPDATE
              SET name = EXCLUDED.name, role = EXCLUDED.role,
                  password = EXCLUDED.password, activo = EXCLUDED.activo
            """,
            (u, name, role, password, activo), fetch=False,
        )
    else:
        # No cambiar la contraseña; el usuario debe existir (es una edición).
        _run(
            "UPDATE costeo_usuarios SET name = %s, role = %s, activo = %s WHERE username = %s",
            (name, role, activo, u), fetch=False,
        )


def set_password(username: str, password: str):
    _run(
        "UPDATE costeo_usuarios SET password = %s WHERE username = %s",
        (password, (username or "").strip().lower()), fetch=False,
    )


def delete_usuario(username: str):
    _run("DELETE FROM costeo_usuarios WHERE username = %s",
         ((username or "").strip().lower(),), fetch=False)


# ------------------------------------------------------------------
# Tarifas
# ------------------------------------------------------------------
def list_tarifas(categoria: str = None, incluir_inactivas: bool = False):
    sql = "SELECT * FROM costeo_tarifas"
    cond, params = [], []
    if categoria:
        cond.append("categoria = %s")
        params.append(categoria)
    if not incluir_inactivas:
        cond.append("activo = TRUE")
    if cond:
        sql += " WHERE " + " AND ".join(cond)
    sql += " ORDER BY proveedor, tipo"
    return _run(sql, tuple(params))


def insert_tarifa(categoria: str, proveedor: str, tipo, tarifa: float, activo: bool = True):
    _run(
        """INSERT INTO costeo_tarifas (categoria, proveedor, tipo, tarifa, activo)
           VALUES (%s, %s, %s, %s, %s)""",
        (categoria, proveedor, (tipo or None), tarifa, activo), fetch=False,
    )


def update_tarifa(id_: int, **campos):
    permitidas = {"categoria", "proveedor", "tipo", "tarifa", "activo"}
    cols = [c for c in campos if c in permitidas]
    if not cols:
        return
    set_sql = ", ".join(f"{c} = %s" for c in cols)
    _run(f"UPDATE costeo_tarifas SET {set_sql} WHERE id = %s",
         tuple(campos[c] for c in cols) + (id_,), fetch=False)


def delete_tarifa(id_: int):
    _run("DELETE FROM costeo_tarifas WHERE id = %s", (id_,), fetch=False)
