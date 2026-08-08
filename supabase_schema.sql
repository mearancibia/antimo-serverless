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

-- ================= CAJA DE RESPALDO (segunda caja de cobro) =================
-- Fuente de ventas INDEPENDIENTE de Bistrosoft, para cuando el cajero del POS no da abasto.
--
-- ⚠️ Por qué tablas nuevas y no `ventas`/`cajas`: el pull de Bistrosoft (sl_common.write_pull)
-- BORRA el mes entero de `ventas` antes de reinsertar, y hace upsert por `fecha_key` en `cajas`.
-- Una venta de respaldo escrita ahí se perdería en el próximo pull (ventas) o pisaría el cierre
-- de Bistrosoft (cajas). Acá quedan aparte y `sources.py` las SUMA al armar `src`.

-- tickets_backup es la FUENTE DE VERDAD: un ticket cobrado, entero. Las otras dos tablas se
-- derivan de acá. Tenerlo permite que reintentar un POST sea idempotente de verdad: el mismo
-- ticket upserta la misma fila y la caja de la noche se RECALCULA sobre el conjunto, en vez de
-- acumular sumas (que contarían doble ante un reintento por mala señal desde el celular).
create table if not exists tickets_backup (
  ticket text primary key,      -- id generado en el celular (uuid), único por cobro
  iso text not null,            -- noche de caja (corte 08:00, hora LOCAL)
  data jsonb not null,          -- {lineas, pagos, descuento, comensales, ts, user}
  creado_ts timestamptz not null default now()
);
create index if not exists tickets_backup_iso_idx on tickets_backup (iso);

-- ventas_backup: espejo plano del ranking de Bistrosoft (una fila por producto y noche).
-- `nombre` va CRUDO: el motor lo normaliza con norm()+UNIFICAR al leer, igual que el de la API.
-- Normalizarlo acá desdoblaría el producto en dos filas del tablero.
create table if not exists ventas_backup (
  id bigint generated always as identity primary key,
  ticket text not null references tickets_backup (ticket) on delete cascade,
  nombre text not null,
  fecha text,                   -- "DD-MM"
  iso text,                     -- "YYYY-MM-DD"
  unidades numeric,
  monto numeric,                -- en PESOS (no centavos)
  unique (ticket, nombre)
);
create index if not exists ventas_backup_iso_idx on ventas_backup (iso);

-- cajas_backup: cierre por noche, MISMA forma que bistro._nuevo_dia(). Derivada de los tickets.
create table if not exists cajas_backup (
  fecha_key text primary key,   -- ISO de la noche
  data jsonb not null
);

-- Válvula anti doble conteo: si una noche se volcó a mano al POS de Bistrosoft, sus datos ya
-- vienen por la API y el respaldo tiene que salir del cómputo. Excluye la noche ENTERA (ventas
-- Y caja): sacar solo una de las dos contaría los productos doble aunque los totales cerraran.
create table if not exists backup_excluido (
  iso text primary key,
  motivo text,
  updated_at timestamptz not null default now()
);

-- ================= COLA DE IMPRESIÓN (relay al revés) =================
-- La app se sirve por HTTPS y el navegador BLOQUEA como mixed content cualquier pedido a
-- http://192.168.x.x, así que el celular no le puede hablar al relay de la red del bar. Se da
-- vuelta la dirección: el celular encola acá, y el relay (en la PC del bar) PREGUNTA por HTTPS
-- cada pocos segundos. La conexión sale hacia afuera, que nunca está bloqueada: no hace falta
-- IP fija, ni abrir puertos, ni que el celular vea a la impresora.
--
-- `escpos` viaja YA RENDERIZADO (base64) desde el celular. Así hay UN SOLO codificador ESC/POS
-- —el de caja.html, testeado en scripts/test_escpos.js— y el relay queda tonto: lee bytes y los
-- escupe al socket 9100. Un segundo codificador en el relay se desincronizaría del primero.
-- `ticket` NO es clave foránea contra tickets_backup a propósito: acá también entran las
-- impresiones de prueba, que existen antes de que haya ninguna venta. Poder probar la impresora
-- sin cobrar es justo lo que hace falta el día que se instala.
create table if not exists cola_impresion (
  ticket text primary key,
  iso text not null,
  escpos text not null,                    -- bytes ESC/POS en base64
  estado text not null default 'pendiente' check (estado in ('pendiente','impreso')),
  intentos int not null default 0,
  creado_ts timestamptz not null default now(),
  impreso_ts timestamptz
);
create index if not exists cola_impresion_pend_idx on cola_impresion (estado, creado_ts);

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
-- Usuarios de la app. El password se guarda HASHEADO (PBKDF2-SHA256 con sal), nunca en texto
-- plano. Se cargan con scripts/crear_usuario.py.
create table if not exists users (
  username text primary key,
  password_hash text not null,
  created_at timestamptz not null default now()
);

-- Rol de cada usuario (RBAC). 'admin' = acceso total; 'cajero' = solo Compras, Caja y Costos
-- (con permiso de escritura ahí adentro). El reparto exacto de solapas y endpoints vive en
-- auth.py, que es la única fuente de verdad: esto sólo guarda a qué rol pertenece cada uno.
--
-- ⚠️ El default es 'admin' A PROPÓSITO: los usuarios que ya existían antes del RBAC siguen
-- entrando igual que antes, así esta migración no le saca el acceso a nadie de golpe. Los
-- cajeros se crean explícitamente (crear_usuario.py --rol cajero).
alter table users add column if not exists role text not null default 'admin';
do $$ begin
  alter table users add constraint users_role_chk check (role in ('admin','cajero'));
exception when duplicate_object then null; end $$;

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
    'tickets_backup','ventas_backup','cajas_backup','backup_excluido','cola_impresion',
    'users','audit_log'
  ] loop
    execute format('alter table %I enable row level security;', t);
  end loop;
end $$;
