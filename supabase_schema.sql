-- ANTIMO — esquema mínimo para la fase 1 de la migración a Supabase.
-- Correr una vez en el SQL Editor del proyecto de Supabase (Settings → SQL Editor → New query).

-- DATA calculada (equivalente a datos_dashboard.json). Una sola fila (id=1): el motor local
-- sigue siendo la única fuente de verdad del cálculo; scripts/seed_supabase.py sube el resultado.
create table if not exists antimo_data (
  id int primary key default 1,
  data jsonb not null,
  generado text,
  updated_at timestamptz not null default now(),
  constraint antimo_data_singleton check (id = 1)
);

-- Overrides editables desde el tablero (fase 1: precios y recetas).
create table if not exists precios_override (
  insumo text primary key,
  precio numeric not null,
  updated_at timestamptz not null default now()
);

create table if not exists recetas_extra (
  nombre text primary key,
  ingredientes jsonb not null,
  updated_at timestamptz not null default now()
);

-- RLS activado y sin policies: bloquea cualquier acceso con la clave "anon" (la que podría
-- terminar expuesta en el navegador). Los endpoints en /api usan la service_role key, que
-- siempre bypassea RLS — no hace falta ninguna policy para que el propio backend funcione.
alter table antimo_data enable row level security;
alter table precios_override enable row level security;
alter table recetas_extra enable row level security;
