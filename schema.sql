-- Esquema de la app de costeo de importación (PostgreSQL).
--
-- Cómo aplicarlo:
--   Conéctate a la base (psql, o el SQL editor del recurso) y corre este
--   archivo. Es idempotente: se puede correr varias veces sin romper nada.
--
-- La app se conecta directo por psycopg2 con el DSN de los secrets; no hay
-- nada hardcodeado del proyecto. No se usa RLS porque no hay capa pública
-- (PostgREST/anon): solo la app, del lado servidor, accede con su DSN.

-- ============================================================
-- Usuarios
-- ============================================================
create table if not exists costeo_usuarios (
    username    text primary key,
    name        text not null,
    role        text not null default 'usuario' check (role in ('gerente', 'usuario')),
    password    text not null,                 -- formato 'salt_hex:hash_hex' (PBKDF2-SHA256)
    activo      boolean not null default true,
    created_at  timestamptz not null default now()
);

-- ============================================================
-- Catálogo de tarifas (flete terrestre, maniobras+honorarios, ...)
-- ============================================================
create table if not exists costeo_tarifas (
    id          bigint generated always as identity primary key,
    categoria   text not null check (categoria in ('flete_terrestre', 'maniobras_honorarios')),
    proveedor   text not null,
    tipo        text,                          -- 'Sencillo'/'Full' para flete; NULL para maniobras
    tarifa      numeric not null,
    activo      boolean not null default true,
    created_at  timestamptz not null default now()
);

-- Evita duplicados (categoria + proveedor + tipo).
create unique index if not exists costeo_tarifas_uq
    on costeo_tarifas (categoria, proveedor, coalesce(tipo, ''));

-- Nota: este archivo solo crea las TABLAS. El catálogo inicial de tarifas y los
-- usuarios los siembra la app al arrancar (app._bootstrap_db), SOLO si la tabla
-- está vacía, para respetar ediciones/borrados que hagan las gerentes.
