-- ANTIMO — esquema completo para la arquitectura serverless (Vercel + Supabase).
-- Correr en el SQL Editor del proyecto de Supabase. Es idempotente (create if not exists):
-- se puede volver a correr sin romper nada.
--
-- Modelo: el motor de costeo (engine.py) corre en las funciones /api y lee TODO de acá.
--   - Tablas de DATOS MAESTROS (del Excel base): costo_base, lista_precios, recetas,
--     maestro_productos, opex_base. Se siembran una vez con scripts/seed_supabase.py.
--   - Tablas de DATOS del negocio: ventas (rankings), cajas (cierres). También se siembran;
--     los pulls futuros de Bistrosoft las actualizan.
--   - Tablas de OVERRIDE (ediciones del dueño desde el tablero): las escriben los endpoints.
--   - antimo_data: el DATA calculado (cache del último recálculo), lo lee /api/data.
--   - app_meta: pares clave→JSON para cosas sueltas (logo data-URI, opex.json, opex_cero).

-- ================= DATA calculada (cache que sirve /api/data) =================
create table if not exists antimo_data (
  id int primary key default 1,
  data jsonb not null,
  generado text,
  updated_at timestamptz not null default now(),
  constraint antimo_data_singleton check (id = 1)
);

-- ================= metadatos sueltos (logo, opex.json editable, opex_cero) =================
create table if not exists app_meta (
  key text primary key,
  value jsonb,
  updated_at timestamptz not null default now()
);

-- ================= DATOS MAESTROS (del Excel base) =================
create table if not exists costo_base (
  nombre text primary key,
  cb_cat text,
  precio numeric,
  pres text,
  cant_base numeric,
  unidad text,
  cxu numeric
);

create table if not exists lista_precios (
  nombre text primary key,      -- ya normalizado (norm())
  precio numeric
);

create table if not exists recetas (
  nombre text primary key,      -- Recetas Bebidas + Comida
  ingredientes jsonb not null   -- [[ingrediente, cantidad], ...]
);

create table if not exists maestro_productos (
  pos text primary key,
  cat text, canon text, tipo text,
  factor numeric, rend numeric, costeo text, nota text
);

create table if not exists opex_base (
  id bigint generated always as identity primary key,
  cat text, item text, cantidad numeric, unitario numeric, monto numeric
);

-- ================= DATOS del negocio (Bistrosoft) =================
-- ventas: una fila por (producto, noche). El motor agrupa por 'iso' (fecha ISO completa).
create table if not exists ventas (
  id bigint generated always as identity primary key,
  nombre text not null,
  fecha text,        -- "DD-MM" (etiqueta cruda del POS)
  iso text,          -- "YYYY-MM-DD" (o "" si no se pudo deducir el año)
  unidades numeric,
  monto numeric,
  unique (nombre, iso, fecha)
);

-- cajas: el cierre de cada noche tal cual lo arma el conector (jsonb completo).
create table if not exists cajas (
  fecha_key text primary key,   -- clave estable por noche
  data jsonb not null
);

-- ================= OVERRIDES (ediciones del dueño) =================
create table if not exists precios_override (
  insumo text primary key, precio numeric not null, updated_at timestamptz not null default now()
);
create table if not exists recetas_extra (
  nombre text primary key, ingredientes jsonb not null, updated_at timestamptz not null default now()
);
create table if not exists precio_lista_override (
  key text primary key, precio numeric not null, updated_at timestamptz not null default now()
);
create table if not exists pours_extra (
  key text primary key, rend numeric not null, updated_at timestamptz not null default now()
);
create table if not exists maestro_extra (
  pos text primary key, data jsonb not null, updated_at timestamptz not null default now()
);
create table if not exists insumos_extra (
  nombre text primary key, data jsonb not null, updated_at timestamptz not null default now()
);
create table if not exists combos_extra (
  pos text primary key, componentes jsonb not null, updated_at timestamptz not null default now()
);
create table if not exists sospechosos (
  key text primary key, data jsonb not null, updated_at timestamptz not null default now()
);
create table if not exists dias_cerrados (
  iso text primary key, motivo text, updated_at timestamptz not null default now()
);
create table if not exists stock (
  insumo text primary key, data jsonb not null, updated_at timestamptz not null default now()
);

-- ================= AUTENTICACIÓN + AUDITORÍA =================
-- Usuarios de la app (un solo nivel de acceso, sin roles). El password se guarda HASHEADO
-- (PBKDF2-SHA256 con sal), nunca en texto plano. Se cargan con scripts/crear_usuario.py.
create table if not exists users (
  username text primary key,
  password_hash text not null,
  created_at timestamptz not null default now()
);

-- Registro de auditoría: TODO lo que hace cada usuario (editar/borrar/pull/login/logout).
create table if not exists audit_log (
  id bigint generated always as identity primary key,
  ts timestamptz not null default now(),
  username text,
  action text,        -- nombre del endpoint / evento
  detail jsonb        -- payload enviado (con el password redactado)
);
create index if not exists audit_log_ts_idx on audit_log (ts desc);

-- ================= RLS: bloquea la clave anon; la service_role (server-side) siempre bypassa =================
-- Los endpoints en /api usan SUPABASE_SERVICE_KEY (service_role), que ignora RLS. Con RLS
-- activado y sin policies, cualquier acceso con la clave anon (la que podría filtrarse al
-- navegador) queda bloqueado. No hace falta ninguna policy para que el backend funcione.
do $$
declare t text;
begin
  foreach t in array array[
    'antimo_data','app_meta','costo_base','lista_precios','recetas','maestro_productos',
    'opex_base','ventas','cajas','precios_override','recetas_extra','precio_lista_override',
    'pours_extra','maestro_extra','insumos_extra','combos_extra','sospechosos','dias_cerrados','stock',
    'users','audit_log'
  ] loop
    execute format('alter table %I enable row level security;', t);
  end loop;
end $$;
