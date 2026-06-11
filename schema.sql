-- Esquema de la app de costeo de importación (Supabase / PostgreSQL).
--
-- Cómo aplicarlo:
--   Supabase Dashboard -> SQL Editor -> pega este archivo -> Run.
-- Es idempotente: se puede correr varias veces sin romper nada.
--
-- Portabilidad: este mismo archivo se aplica al Supabase de desarrollo
-- (personal de Marvelsa) y luego al de la organización (producto final).
-- La app NO tiene nada hardcodeado del proyecto; todo va por secrets.
--
-- Seguridad: ambas tablas tienen RLS activado y SIN policies. Eso significa
-- que solo la "service_role key" (que vive en los secrets del servidor de
-- Streamlit, nunca en el navegador) puede leer/escribir. La anon key queda
-- bloqueada.

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

-- Evita duplicados al sembrar (categoria + proveedor + tipo).
create unique index if not exists costeo_tarifas_uq
    on costeo_tarifas (categoria, proveedor, coalesce(tipo, ''));

-- ============================================================
-- RLS: activado y sin policies => solo service_role (servidor) accede.
-- ============================================================
alter table costeo_usuarios enable row level security;
alter table costeo_tarifas  enable row level security;

-- ============================================================
-- Seed del catálogo de tarifas (montos sin IVA; ya son públicos en el repo).
-- Los USUARIOS se siembran aparte (sus hashes no van al repo público).
-- ============================================================
insert into costeo_tarifas (categoria, proveedor, tipo, tarifa) values
    ('flete_terrestre',      'Henco',    'Sencillo', 26500),
    ('flete_terrestre',      'Henco',    'Full',     21000),
    ('flete_terrestre',      'RTC',      'Full',     37000),
    ('flete_terrestre',      'GISAP',    'Sencillo', 24800),
    ('maniobras_honorarios', 'WISE',     null,       13790),
    ('maniobras_honorarios', 'WOODWARD', null,       18192.50)   -- WOODWARD: pendiente de actualizar
on conflict (categoria, proveedor, coalesce(tipo, '')) do nothing;
