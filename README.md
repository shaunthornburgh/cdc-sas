# Casa Dolce Casa S.A.S. — Operations Platform

Monorepo for the operations platform for Casa Dolce Casa S.A.S. (real estate).

| Part      | Stack                                                                  |
|-----------|------------------------------------------------------------------------|
| backend/  | FastAPI · SQLAlchemy 2.0 · Alembic · Pydantic v2 · PostgreSQL 16 · Redis |
| frontend/ | Nuxt 3 · Vue 3 · TypeScript                                            |
| local dev | Docker Compose (Postgres + Redis, API optional)                        |

## Structure

```
.
├── docker-compose.yml        # db (Postgres 16), redis, api (opt-in profile)
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app factory, CORS, routers
│   │   ├── core/             # config.py (settings from backend/.env), security.py (argon2, JWT), token_store.py (revoked tokens in Redis)
│   │   ├── db/               # Declarative Base, UUID/timestamp mixins, session, pg_enum
│   │   ├── api/router.py     # /api/v1 router (one router per module)
│   │   ├── api/deps.py       # DbSession, RedisClient, CurrentUser
│   │   ├── api/permissions.py # require_cargo / require_actividad / require_funcion
│   │   ├── api/routes/       # one file per module (thin: validate, call the service, commit)
│   │   ├── models/           # SQLAlchemy models, one file per module + enums.py
│   │   ├── schemas/          # Pydantic request bodies
│   │   ├── services/         # business rules, one file per module (rules in each module's docstring)
│   │   └── scripts/          # seed.py + seed_<module>.py (demo data)
│   ├── alembic/              # Migrations (env.py reads app settings)
│   ├── tests/                # API tests, one file per module (need Postgres)
│   └── pyproject.toml
└── frontend/
    ├── nuxt.config.ts        # runtimeConfig.public.apiBase
    ├── assets/css/           # tokens.css (colours, fonts, radii) + main.css (prototype class names)
    ├── layouts/default.vue   # Sidebar (desktop), top bar + bottom navigation (phone)
    ├── layouts/auth.vue      # Centered layout for /login
    ├── middleware/auth.global.ts # Login required unless public; `cargos` page meta → 403
    ├── plugins/auth.ts       # Auth state, token cookies, authenticated fetch with refresh
    ├── composables/          # useAuth, useApi and one use<Module>() per module
    ├── components/           # PageBar, ConfirmDialog, banners (PreopBanner, PausaBanner) and module pieces
    ├── types/                # API types per module
    ├── utils/                # labels, dates, permissions shared by pages
    ├── error.vue             # 403 / 404 / error page
    └── pages/                # see «Modules» below
```

## Modules

Each module has its own section further down (rules, endpoints, demo data, simplifications). Prototype
codes refer to `CDC_Software_Operativo/paginas/*.dc.html`; decisions (G-0xx) to its `DECISIONS.md`.

| Module | Pages | Who | Prototypes |
|--------|-------|-----|------------|
| Login, Mi perfil | `/login`, `/perfil` | Everyone | Z01, M11 |
| Inicio | `/` (general), `/asesor`, `/coordinacion` | Each cargo its own | M01, M02, K01, K11 |
| Usuarios | `/usuarios` | Gerencia, Coordinación | G04 |
| Atención y Preventa: leads y citas | `/leads`, `/leads/[id]`, `/citas` | Atención, Pre-ventas, managers | C01–C03 |
| Mis citas | `/mis-citas` | Asesores | M03 |
| Captaciones | `/captaciones` | Captadores, managers | K12, M15 |
| Pedidos | `/pedidos` | Commercial team, managers | K06, C10 |
| Inmuebles · Administración de inmuebles | `/inmuebles`, `/inmuebles/administracion` | Commercial team, Auxiliar, managers | X14 |
| Negocios | `/negocios` | Auxiliar, Gerencia, Coordinación (no money), asesores (theirs) | X02, M16 |
| Pólizas | `/polizas` | Auxiliar, Gerencia | X11 |
| Preoperacional | `/preoperacional`, `/preoperacionales` | Everyone · reviewers | M07, C08, K09 |
| Pausas activas | `/pausas-activas` (+ `?tab=equipo`), reminder in each Inicio | Everyone · Auxiliar, Coordinación, Gerencia | G11 |
| Asistencia | `/asistencia` (+ `?tab=equipo`, `?tab=sedes`) | Everyone but Gerencia marks · team view | Z04, K17, X08 |
| Ausencias y permisos | `/novedades` | Auxiliar, Coordinación, Gerencia | K13 |
| Movimientos y GPS | `/movimientos` | GPS users · managers | K05, M05, K16, C09 |
| Rutas | `/rutas` | Captadores (Mi ruta) · managers | X08, M04 |
| Capacitaciones | `/capacitaciones` (+ `?tab=equipo`) | Everyone · Auxiliar, Coordinación, Gerencia | Z03, X07 |
| Rendimiento | `/resultados`, `/resultados/[id]`, `/equipo`, `/rendimiento`, `/rendimiento-empresa` | Each person · managers · Gerencia | C04, K07, K14, K18, G12 |
| Compensación | `/mis-pagos`, `/compensacion`, `/salarios` | Everyone (own) · Auxiliar, Gerencia | G05, X04, Z05, M12–M14 |
| Descargas del personal | `/descargas` | Auxiliar, Gerencia, Coordinación (team) | X10 |
| Plataformas tradicionales | `/plataformas` | Auxiliar, managers | K15 |
| Integraciones | `/integraciones` | Gerencia | G07 |
| Avisos · Agenda | `/avisos`, `/agenda` | Everyone | G09, M10, C05, M17, C07, X06, K19 |
| Registro de cambios | `/trazabilidad` | Gerencia, Coordinación | G06 |
| Configuración | `/configuracion` | Gerencia, Coordinación (its part) | Z02 |

## Ports

| Service  | URL                                  |
|----------|--------------------------------------|
| Frontend | http://localhost:3000                |
| API      | http://localhost:8100 (docs at `/docs`) |
| Postgres | localhost:5432 (user/pass/db: `cdc`) |
| Redis    | localhost:6379                       |

The API uses port 8100 instead of 8000 so it doesn't clash with other local projects.
You can override any host port: `API_PORT=8200 POSTGRES_PORT=5433 docker compose up -d`.

## Requirements

- Docker Desktop
- Node 20+ and pnpm (`npm i -g pnpm`)
- Python 3.12+ (only if you run the API outside Docker: `brew install python@3.12`)

## Quick start (everything in Docker)

```bash
cp backend/.env.example backend/.env
docker compose --profile api up -d --build                     # Postgres, Redis, API (migrates on start)
docker compose exec api python -m app.scripts.seed             # demo users + demo data for every module
cd frontend && cp .env.example .env && pnpm install && pnpm dev   # http://localhost:3000
```

Log in with any of the test users below (password `CasaDolce2026!`). The seed only adds what's missing,
so it's safe to run again. Demo dates are relative to the day you seed.

To start the demo data from scratch: `docker compose --profile api down -v`, then the commands above.

## 1. Start Postgres + Redis

```bash
docker compose up -d
```

## 2. Backend

**Option A: run in Docker (simplest).** This runs migrations, then uvicorn with hot reload:

```bash
cp backend/.env.example backend/.env
docker compose --profile api up -d --build
docker compose exec api python -m app.scripts.seed   # demo users (safe to re-run)
docker compose logs -f api
```

**Option B: run in a local virtualenv:**

```bash
cd backend
cp .env.example .env
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python -m app.scripts.seed
uvicorn app.main:app --reload --port 8100
```

Check it:

```bash
curl localhost:8100/api/v1/health         # liveness
curl localhost:8100/api/v1/health/ready   # checks Postgres + Redis
open http://localhost:8100/docs
```

Tests, lint and migrations (prefix with `docker compose exec api` when using Option A).
Tests need Postgres running: they create a separate `cdc_test` database from the migrations.

```bash
pytest
ruff check . && ruff format --check .
alembic revision --autogenerate -m "create users"   # after adding a model to app/models/__init__.py
alembic upgrade head
```

## 3. Frontend

```bash
cd frontend
cp .env.example .env
pnpm install
pnpm dev            # http://localhost:3000
```

Every page needs a login except ones that set `definePageMeta({ public: true })`.
To limit a page by cargo, use `definePageMeta({ cargos: ['gerencia', 'coordinacion'] })`; anyone else gets a 403 page.
The dashboard at `/` shows the current user's cargo, activities and GPS check-in status.

Other commands: `pnpm typecheck`, `pnpm build`, `pnpm preview`.

> Use pnpm. `npm install` currently fails on npm 10 with `Cannot read properties of null (reading 'edgesOut')` while resolving Nuxt's peer dependencies.

## Checks

```bash
docker compose exec api pytest                                         # 304 API tests (create a cdc_test database)
docker compose exec api sh -c "ruff check . && ruff format --check ."  # lint + format
cd frontend && pnpm typecheck && pnpm build                            # types + production build
```

Tests that depend on «today» pin the clock (`fechas.now`), so they pass any day of the week. A few
use relative times («in 30 minutes») and could misbehave if run within minutes of midnight in Bogotá.
Stop `pnpm dev` before `pnpm build` (Nuxt refuses to build while a dev server runs).

## Stop / reset

```bash
docker compose --profile api down        # stop
docker compose --profile api down -v     # stop and wipe the database
```

## Design system

The UI follows the approved prototypes (`CDC_Software_Operativo/paginas/*.dc.html`).
- **Tokens:** `frontend/assets/css/tokens.css` holds the colours, fonts and radii.
- **Shared classes:** `frontend/assets/css/main.css` uses the **same class names as the prototypes**, so markup can be copied across almost directly:

| Class | Use |
|-------|-----|
| `.ttl` | Bebas Neue title (32px, 26px on mobile) |
| `.lbl` / `.mut` | Small uppercase label / muted text |
| `.card` (`.card.focus` = 2px green border) | White card, radius 16px |
| `.btn` + `.bp` / `.bs` / `.br` (`.sm` = 32px) | Primary / secondary / danger button |
| `.chip` + `.ok` `.warn` `.bad` `.info` `.gray` `.pend` | Status chips |
| `.act.on1` / `.act.off1` | Active / inactive activity pill |
| `.in` / `.sel` / `.fld` | Input, select, field with label |
| `.opt` (`.on`) | Single-choice option button |
| `.tbl`, `.av`, `.note` (`.ok` `.bad` `.warn`) | Table, 30px avatar, note box |

- **Components:** `PageBar` (white top bar with back link, title and actions), `AppSwitch` (`.sw` toggle), `ConfirmDialog`, `BrandLogo`.
- **Layout:** desktop has the dark green sidebar (256px); at 760px and below it switches to a white top bar with bottom navigation.
- **Light theme only**, as in the prototypes.

## Test users

Created by `python -m app.scripts.seed` (refuses to run outside `local`/`test`).
All share the password **`CasaDolce2026!`** (override with `SEED_PASSWORD`).

| Email                    | Cargo                   | Activities / function      |
|--------------------------|-------------------------|----------------------------|
| gerencia@example.com     | Gerencia                | none                       |
| coordinacion@example.com | Coordinación            | none                       |
| asesor@example.com       | Asesor                  | Captación + Ventas (GPS on) |
| bruno@example.com        | Asesor                  | Captación                  |
| carla@example.com        | Asesor                  | Arriendos                  |
| diego@example.com        | Asesor                  | Ventas + Arriendos         |
| preventas@example.com    | Asesor                  | Function: Pre-ventas       |
| auxiliar@example.com     | Auxiliar administrativa | none                       |
| atencion@example.com     | Atención al Cliente     | Function: Atención al Cliente |

## Auth

| Endpoint                   | Body                         | Notes |
|----------------------------|------------------------------|-------|
| `POST /api/v1/auth/login`  | `{email, password}`          | Returns access + refresh tokens and the user |
| `POST /api/v1/auth/refresh`| `{refresh_token}`            | Returns a new pair; the old refresh token stops working |
| `POST /api/v1/auth/logout` | `{refresh_token}` + Bearer header | Revokes both tokens |
| `GET  /api/v1/auth/me`     | Bearer header                | Current user |

- Access tokens last 15 minutes and refresh tokens 7 days (`JWT_ACCESS_TTL_MINUTES`, `JWT_REFRESH_TTL_DAYS`).
- Passwords are hashed with argon2id.
- Revoked tokens are kept in Redis until they would have expired.
- The user is loaded from the database on every request, so deactivating someone or changing their activities takes effect immediately.
- The API refuses to start outside `local`/`test` unless `JWT_SECRET` is set to a random value of at least 32 characters.
- In Swagger (`/docs`), click **Authorize** and paste an access token.

The frontend keeps both tokens in cookies, so server rendering and route middleware can see the session. When an access token expires, it refreshes once and retries the request. A later improvement is to have the API set the refresh token as an `httpOnly` cookie, so page scripts can't read it.

## User management (`/api/v1/users`, Gerencia and Coordinación only)

| Endpoint | Body | Notes |
|----------|------|-------|
| `GET  /users` | `?q=&cargo=&is_active=` | List with cargo, activities, funcion |
| `GET  /users/{id}` | | |
| `POST /users` | `{email, password, full_name, cargo, funcion?, actividades?, is_active?}` | 201; duplicate email gives 409 |
| `PATCH /users/{id}` | any of `{full_name, cargo, is_active, funcion, telefono, documento, fecha_ingreso}` | Partial; `funcion: null` clears it; personal data changes go to `user_cambios` |
| `GET  /users/{id}/cambios` | | Personal data changes: before, after, who and when |
| `POST /users/{id}/activities` | `{actividades: [...]}` | Replaces the full set |
| `GET  /users/{id}/activities/history` | | Who switched each activity on or off, and when |
| `POST /users/{id}/funcion` | `{funcion: "pre_ventas" \| "atencion_cliente" \| null}` | |

Rules (a broken rule returns 422 with a message in Spanish; a permission problem returns 403):
- A user can have an independent function or commercial activities, not both. Remove one before adding the other.
- The Atención al Cliente cargo always has the Atención al Cliente function. Moving a user to that cargo sets the function, but fails if they still have activities.
- Pre-ventas can be assigned to any cargo (for now).
- Only Gerencia can create, edit or promote to Gerencia users.
- Nobody can change their own cargo or deactivate themselves.
- Deactivating a user ends their session on their next request.
- Every activity switched on or off is logged in `actividad_eventos` with who did it. `user_actividades.granted_by_id` also records who switched on each current activity.

The `/usuarios` page covers all of this: activities and función are edited inline in the table, and creating a user or editing name, cargo or status happens in a side panel that also shows the activity history.

### Permission helpers (`backend/app/api/permissions.py`)

```python
from app.api.permissions import require_cargo, require_actividad, require_funcion

# Route-level guard
@router.get("/reportes", dependencies=[Depends(require_cargo(Cargo.GERENCIA, Cargo.COORDINACION))])

# Guard + get the user
@router.post("/checkin")
def checkin(user: Annotated[User, Depends(require_actividad(ActividadComercial.CAPTACION))]): ...

# All listed activities required
require_actividad(ActividadComercial.VENTAS, ActividadComercial.ARRIENDOS, require_all=True)
```

There's no implicit superuser: if Gerencia should pass a check, list it explicitly.

## Atención y Preventa: leads and citas

Built from prototypes C01 (Atención y Preventa), C02 (Gestionar lead) and C03 (Control de citas), and decisions G-013, G-014, G-044 and G-045.

**Who can use it.** Users with the Atención al Cliente or Pre-ventas function, plus Coordinación and Gerencia. Asesores with only commercial activities, and the Auxiliar administrativa, get 403 and don't see the module in the menu.

**Leads**
- **Arriving:** leads come in without an owner. «Seguir lead» makes you the only owner, and only Coordinación or Gerencia can reassign it. Atención and Pre-ventas see unassigned leads and their own; managers see all leads.
- **Stages:**
  - `nuevo` → `en_gestion`, automatically after the first action.
  - `seguimiento` while a follow-up is pending.
  - `cita_programada`, set automatically when a cita is created.
  - `ganado` (managers only) and `perdido` close and archive the lead. Only managers can reopen it.
- **Perdido:**
  - It needs a reason.
  - «Número equivocado» never costs points.
  - «No contesta» costs points unless there were at least 3 calls on 3 consecutive days.
  - A lead with an active cita can't be closed.
- **History:** every action (call, message, options sent, observation, follow-up, cita, stage change, reassignment) is saved in `lead_eventos` with who did it and when.

**Citas**
- **Asesor:** an asesor who has the required activity and isn't booked within an hour of the slot.
- **Status:** `pendiente` (waiting for acceptance) → `aceptada` or `rechazada` → `realizada` or `cancelada`.
- **Rescheduling** needs a reason, and an accepted cita goes back to `pendiente`.
- **Needs action:** a cita appears in «Requieren acción» when it was rejected, has no asesor, or is still pending with less than 1 hour to go.
- **Asesor's answer:** asesores don't have their own screen yet, so Atención or Coordinación record whether the asesor accepted or rejected.

| Endpoint | Notes |
|----------|-------|
| `GET /leads?etapa=&abiertos=&assigned=me\|none\|<id>&fuente=&desde=&hasta=&q=` | List with filters |
| `GET /leads/stats?periodo=hoy\|semana\|mes` | KPI row |
| `GET /leads/responsables` | Managers: who a lead can be assigned to |
| `POST /leads` · `GET/PATCH/DELETE /leads/{id}` | CRUD (`DELETE` and `assigned_to_id` are for managers only) |
| `POST /leads/{id}/follow` | «Seguir lead» (409 if someone else already has it) |
| `POST /leads/{id}/actions` | `{tipo: llamada\|mensaje\|opciones\|observacion, …}` |
| `POST /leads/{id}/followups` · `…/followups/{sid}/complete` | Schedule a follow-up / mark it done |
| `POST /leads/{id}/stage` | `{etapa, motivo?}` |
| `GET /citas?bucket=accion\|pendientes\|aceptadas\|realizadas\|canceladas` | List + per-tab counts |
| `GET /citas/asesores?tipo=&scheduled_at=` | Who can take the cita and who is free |
| `POST /citas` · `GET/PATCH /citas/{id}` | Create / read / edit notes |
| `POST /citas/{id}/status` · `/reassign` · `/reschedule` | Status flow |

**Demo data.** `python -m app.scripts.seed` also creates 14 leads and 5 citas (only if there are no leads yet), covering every stage: four new leads without an owner, follow-ups due today, a rejected cita, a cita starting in under an hour, and one lead each archived as perdido and ganado. Log in as `atencion@`, `preventas@` or `coordinacion@` to see them. To reset them:
`docker compose exec db psql -U cdc -d cdc -c "TRUNCATE lead_eventos, lead_seguimientos, citas, leads RESTART IDENTITY CASCADE"`, then run the seed again.

## Captaciones

Built from prototypes K12 (Verificar captaciones, Coordinación and Gerencia) and M15 (Nueva captación, asesor), and the decision «Captaciones · registro rápido y verificación».

**Who can use it.** People with the **Captación** activity register captaciones and see only their own. Coordinación and Gerencia see all of them, verify them and can register one on behalf of a captador. Everyone else gets 403 and doesn't see the module in the menu. If Coordinación switches off someone's Captación activity, the module closes for them at once.

**Rules**
- **Two ways to register:** «Registro rápido» (venta or arriendo, property code, address) or «Formulario completo» (also property type, barrio, municipio, price or rent, owner and phone are required; area, rooms, bathrooms, parking and notes are optional).
- **Duplicate codes:** a property code can be in only one live captación («Inmueble ya registrado», 409). A partial unique index enforces this in the database, so two people submitting at once can't both succeed. Rejected captaciones don't block their code.
- **Verification:** every captación arrives `por_verificar`. Coordinación or Gerencia approve it, or reject it with a reason («código inexistente» or «el código no corresponde a esa dirección») plus an optional note. Only approved captaciones count.
- **Correcting:** «Corregir y volver a enviar» updates the same rejected captación; the code or address must change, and it goes back to `por_verificar`.
- **Published:** approved captaciones can be marked «Publicada».
- **Editing:** the captador can edit until it's approved and can withdraw it while it's `por_verificar`. Managers can always edit, reassign (only to someone with Captación) and delete.
- **GPS:** the browser's location is recorded only when captadores submit their own captación. Distance to the address needs geocoding, which isn't set up yet.
- **History:** every submission, edit, approval, rejection, resubmission, publication and reassignment goes into `captacion_eventos`.

| Endpoint | Notes |
|----------|-------|
| `GET /captaciones?estado=&asesor_id=&negocio=&publicada=&desde=&hasta=&q=` | `{items, counts, aprobacion_pct}` |
| `GET /captaciones/captadores` | Managers: who can own a captación |
| `POST /captaciones` · `GET/PATCH/DELETE /captaciones/{id}` | CRUD (`asesor_id` on create is for managers only) |
| `POST /captaciones/{id}/status` | `{estado: aprobada\|rechazada, motivo?, observacion?}` (managers) |
| `POST /captaciones/{id}/resubmit` | `{codigo_inmueble, direccion}`, rejected only |
| `POST /captaciones/{id}/publish` · `/reassign` | Mark published / change owner (managers) |

**Demo data.** The seed adds `bruno@example.com` (Captación) and 9 captaciones: 4 por verificar (one corrected and resubmitted), 3 aprobadas (2 published) and 2 rechazadas, split between `asesor@` and `bruno@`. To reset them: `TRUNCATE captacion_eventos, captaciones RESTART IDENTITY CASCADE`, then run the seed again.

## Coordinación dashboard (`/coordinacion`)

Built from prototypes K01-DashCoord (desktop) and K11-CoordCel (phone). Coordinación and Gerencia land here after logging in (and the sidebar's «Inicio» takes them here); everyone else gets 403 and keeps their own home page. The page refreshes itself every minute.

- **KPI cards:** leads without an owner (and how many have waited more than 15 min), citas not yet accepted (and how many start within the hour), rejected citas, captaciones por verificar (and the oldest one), today's citas, and open leads split into venta and arriendo.
- **Summary cards:** this month's captaciones with a traffic-light chip (green ≥ 80 %, yellow 60–79 %, red < 60 %), and this month's leads (won, lost, lost with a penalty).
- **Mi equipo hoy:** one row per person: citas not yet accepted (red when within 1 hour), today's citas, overdue follow-ups, citas needing action, captaciones to correct.
- **Mi equipo · actividades:** C/V/A pills, GPS, captaciones approved this month (venta/arriendo), how many are waiting for verification, citas done and accepted. «No aplica» means the person doesn't have that activity.
- **Alertas en tiempo real:** most urgent first, built from live data, each with a link. On the phone each alert also has «Qué hacer».
- **Atención y Preventa:** leads followed, first response (average minutes from a lead arriving to someone taking it), calls, follow-ups on time (marked done within 30 min of their time), citas scheduled and done, leads won and open leads.

Pedidos and preoperacional were added to this dashboard by their own modules (see those sections). The prototype's tasks, GPS alerts, attendance and rendimiento tiles aren't on it: they live on their own pages (Agenda, Movimientos y GPS, Asistencia, Mi equipo).

| Endpoint | Content |
|----------|---------|
| `GET /dashboard/coordinacion` | Everything above in one request |
| `GET /dashboard/leads` · `/citas` · `/captaciones` · `/equipo` | One section each |

All of them are grouped queries over the existing tables. Coordinación and Gerencia only.

## Asesor home (`/asesor`) and «Mis citas» (`/mis-citas`)

Built from prototypes M01-Asesor1 and M02-Asesor2 (home) and M03-Citas. Asesores (at least one of Captación, Ventas or Arriendos) land on `/asesor` after logging in. The menu shows only what they can use: Inicio and Mis citas, plus Captaciones if they have Captación. Coordinación and Gerencia can open any asesor's home read-only from the team table on their dashboard (`/asesor?asesor=<id>`). Atención and the Auxiliar get 403.

**Home**
- **Mis pendientes y recordatorios** (most urgent first): citas to accept; citas another asesor rejected that this asesor can take (they have the activity and are free at that time); citas to close after the visit; reminders for citas within 1 hour or tomorrow; and, for captadores, rejected captaciones to correct and approved ones to mark published.
- **Today's citas** and **Mis actividades** (with GPS only if they have Captación).
- **Mis resultados del mes:** one tab per active activity. Captación: approved for venta and arriendo, por verificar, published. Ventas and Arriendos: citas, done, upcoming accepted, still to answer.
- **Quick actions:** Nueva captación (captadores only), Mis citas.

**Mis citas (M03)** has four tabs: Por responder, Próximas, Por cerrar and Cerradas. The asesor can:
- **Accept** a cita.
- **Reject** it, with a reason from the list plus a note.
- **Take** a cita another asesor rejected («El asesor ha rechazado esta cita. ¿Deseas tomar esta cita?»). The first one to take it keeps it; this is safe even if two people try at once.
- **Close** it after the visit, saying what happened.

Everything is recorded in the lead's history. Atención and Coordinación can still record an asesor's answer from Control de citas.

| Endpoint | Notes |
|----------|-------|
| `GET /asesor/inicio?asesor_id=` | Home (`asesor_id` for managers only) |
| `GET /asesor/citas?asesor_id=` | The four lists + counts |
| `POST /asesor/citas/{id}/aceptar` · `/rechazar` · `/tomar` · `/cerrar` | Only the asesor (managers can't do these for them) |

The preoperacional banner, pedidos reminders, the pausa activa reminder and «Mi puntaje del mes» were added by their modules. The prototype's entrada/GPS, «negocios pendientes» and pagos aren't on the home: they're on their own pages (Asistencia, Mis negocios, Mis pagos y bonos).

## Preoperacional (`/preoperacional`, `/preoperacionales`)

Built from prototypes M07 (phone), C08 (desktop, all cargos) and K09 (team review), and decisions G-007, G-008, G-012 and «Preoperacional según medio de transporte».

- **Who:** everyone does it, all cargos including Gerencia, with the same form, once per day (Bogotá date). Gerencia can switch it off per cargo; Coordinación sees that setting read-only. When it's off there is no reminder, and it neither counts nor lowers the score. The history is kept.
- **Form:** Carro or Moto need a plate and the 8 official SÍ/NO questions (a different list for each). Bicicleta, Transporte público, A pie and Otro are a travel report only. «Observaciones y novedades» is optional. Name, date and time are saved automatically.
- **Novedad:** any NO, or an observation, is a novedad. Coordinación and Gerencia mark it as reviewed, with an optional note.
- **Who sees whose:** Coordinación sees Asesores, Atención / Pre-ventas and the Auxiliar. Coordinación's own goes to Gerencia. Gerencia sees everyone.
- **Score (automatic):** based on business days (Mon–Fri) completed from the person's start, and today counts only once it's done. 100 % = 5 · 90–99 % = 4 · 80–89 % = 3 · 70–79 % = 2 · < 70 % = 1. A score of 2 or 1 costs 5 points. Gerencia's is a record only.
- **Where it shows up:**
  - **Asesor home and general home:** the M01 banner «ATENCIÓN: debes realizar el preoperacional» until it's done, then a green chip.
  - **Coordinación dashboard:** a «Preoperacional x/y» card, a column in «Mi equipo hoy», the phone tile, and alerts for people who haven't done it and novedades not yet reviewed.
- **Download:** a month (or one person's month) as CSV, which opens in Excel.

| Endpoint | Notes |
|----------|-------|
| `GET /preoperacional/formulario` | Means of transport, questions, today's record, who receives it |
| `POST /preoperacional` | `{medio, placa?, respuestas?: [8 × bool], observaciones?}` (409 if already done today) |
| `GET /preoperacional/mios?mes=AAAA-MM` | Calendar, score, novedades, missed days |
| `GET /preoperacional/equipo?fecha=` | K09: one day for everyone you review + the month's score |
| `POST /preoperacional/{id}/revisar` | `{nota?}` |
| `GET /preoperacional/config` · `PUT /preoperacional/config/{cargo}` | On/off per cargo (changes: Gerencia only) |
| `GET /preoperacional/export.csv?mes=&user_id=` | Coordinación / Gerencia |

**Demo data.** About 30 business days of history for every demo user (so last month has numbers too), with a few missed days and novedades (older ones already reviewed). Today Bruno has a novedad (brakes) and Asesor Demo hasn't done it yet. To reset: `TRUNCATE preoperacionales`, then run the seed again.

## Pedidos (`/pedidos`)

What a client is looking for (prototypes K06, K06-ger, M06, C10). Codes start at `PED-030`.

- **Who**: asesores with a commercial activity, Atención al Cliente / Pre-ventas, Coordinación and
  Gerencia. Auxiliar gets 403. Anyone allowed can create one, for themselves or for another person.
- **States**: `abierto` → `atendido` or `perdido` (with reason). The screen also shows derived states:
  Nuevo, Urgente, Vence hoy, Vencido · sin decidir, Recuperado (attended after it expired).
- **Expired pedidos are never lost automatically.** The responsable or Coordinación either extends the
  date (with a reason; only allowed once it has expired) or marks it lost. Expired ones stay in
  «Vencidos» for Gerencia.
- **Duplicates**: if the client (lead, phone digits or name) already has an open pedido, creation returns
  409 and the form offers «Actualizar PED-xxx» or «Es otra necesidad».
- **Changes**: only the responsable or a manager can update, attend or lose a pedido. Updates need
  «¿Qué cambió?», and the history keeps the before and after. Others can propose a property or comment.
  Only managers reassign.
- **Screens**: managers get KPIs, the team table and the «Vencidos» tab. Asesores and Atención get cards
  with «Mis pedidos» and the team's pedidos, plus filters for negocio, presupuesto, zona and
  «Próximos a vencer» (3 days).
- **Elsewhere**: the asesor home shows pedidos due today, expired or about to expire. The Coordinación
  dashboard has a «Pedidos vencidos» KPI, a «Pedidos por vencer» column and alerts for undecided ones.

Endpoints: `GET/POST /pedidos`, `GET /pedidos/opciones`, `GET/PATCH /pedidos/{id}`,
`POST /pedidos/{id}/extender|atendido|perdido|proponer|comentar|reasignar`.

## Rendimiento (`/resultados`, `/equipo`, `/rendimiento`, `/rendimiento-empresa`)

The month's result for each person (prototypes M08, C04, K14, K07, K18, G12). Everything is calculated
from data already in the system; nothing is entered by hand except weights, goals and the 1–5 ratings.
The rules are in the docstring of `backend/app/services/rendimiento.py`.

**Who has a result**: asesores (with a commercial activity), Atención y Preventa, and the Coordinador.
Gerencia and the Auxiliar don't have indicators yet (PENDIENTE DE CONFIGURACIÓN).

**How it's calculated**
- Result = Σ (cumplimiento × weight) + adjustments − deductions, shown from 0 to 100. One point is 1 %.
- Cumplimiento = achieved ÷ goal, capped at 100 %. An area «cumple» at 100 %.
- Areas with no data (nothing recorded in the system, or nothing to measure) don't count. The result
  uses the weight of the areas that have data, and the screen says so («calculado sobre el 65 %»).
- 1–5 ratings have no weight: each 2 or 1 takes off 5 points. The preoperacional rating comes from
  the preoperacional module; Puntualidad from «Marcar entrada» (see Asistencia).
- Atención y Preventa: +1 per lead ganado; −0.5 per lead perdido that «descuenta» (wrong numbers, and
  no contact after 3 calls on 3 days, don't).
- Traffic light: verde 80–100 · amarillo 70–79 · naranja 60–69 · rojo < 60.

**What counts in each area**

| Who | Area | Counts | Default goal / weight |
|---|---|---|---|
| Asesor | Ventas / Arriendos | Leads of that type marked «Ganado» this month whose last realized visit was with this asesor | 1 venta · 3 arriendos |
| Asesor | Captación | Captaciones approved this month (rejected ones don't count) | 10 |
| Asesor | weights | 1 activity 100 · 2 → 50/50 · 3 → 50/30/20 (Ventas, Arriendos, Captación) | |
| Atención | Leads gestionados · Llamadas | Distinct leads with an action by them · calls they logged | 30 · 45 |
| Atención | Seguimientos a tiempo | Follow-ups due this month, done ≤ 30 min late (cancelled ones excluded) | 100 % |
| Atención | Citas programadas / realizadas | Client citas they scheduled this month (not control visits or inventories) / of those, realized | 12 · 10 |
| Atención | Conversión · Cierres | Citas ÷ leads gestionados · leads ganados assigned to them | 40 % · 5 |
| Coordinador | Resultados del equipo | Average result of asesores and Atención | weight 50 |
| Coordinador | Monitoreo y seguimiento | Captaciones of the month verified within 24 h (more criteria pending) | weight 15 |
| Coordinador | Plataformas · Rutas | Days their platforms were up to date · average of Gerencia's 1–5 ratings of the routes they created (4 of 5 = 80 %) | weights 20 · 15 |

**Avoiding double counts**: a won lead counts once for the asesor of its last realized visit (Ventas
or Arriendos) and once for the Atención person it's assigned to (Cierres). These are different
indicators, as in the prototype. A captación counts once, when it's approved.

**Who configures what** (every change goes to `rendimiento_cambios` with before and after):
- Weights must add up to exactly 100 and apply from this month. Goals apply from next month, so this
  month keeps the goals it started with.
- Asesores' weights and goals: Coordinación or Gerencia. Atención's and the Coordinador's: Gerencia.
- Ratings for asesores and Atención: Coordinación only (Gerencia and the Auxiliar consult). Ratings
  for the Coordinador: the Auxiliar or Gerencia. Nobody rates themselves, and only the current month
  can be rated.

**Who sees what**: everyone sees their own result («Mis resultados», with a «Puntaje» tab on mobile
and a card on the asesor home). Coordinación sees asesores and Atención in «Mi equipo». Gerencia and
the Auxiliar also see the Coordinador. «Rendimiento de la empresa» (Gerencia only) averages each area
and the company, compares with last month, and flags areas under 60 %.

Endpoints: `GET /rendimiento/mio`, `/equipo`, `/equipo.csv`, `/empresa`, `/personas/{id}`,
`/config/{id}`, `/cambios/{id}` (all take `?periodo=AAAA-MM`), plus `PUT /config/{id}/pesos`,
`PUT /config/{id}/metas` and `PUT /calificaciones/{id}`.

The demo seed (`seed_rendimiento`) creates a month of work, plus last month, so the screens show
numbers close to the prototype's.

## Compensación (`/mis-pagos`, `/compensacion`, `/salarios`)

Commissions, bonuses, payments and salaries (prototypes G05, G05-aux, X04, Z05, M12–M14). The rules
are in the docstring of `backend/app/services/compensacion.py`. **Every percentage, amount and date
is an example value** that Gerencia edits in «Configuración», because the prototypes mark them
«PENDIENTE DE CONFIGURACIÓN».

**Trigger: closed deals (`NEG-0140…`)**: one is created for each lead marked «Ganado». The system
works out who took part:
- *cerrador*: the asesor of the lead's last completed visit
- *filtro*: the Atención y Preventa person the lead is assigned to
- *captador*: chosen by the Auxiliar or Gerencia (leads aren't linked to captaciones yet)

If the lead stops being «Ganado», the deal becomes «caído» and its unpaid commissions are cancelled.

**Ganancia efectiva**: there are no deal amounts in the system yet, so the Auxiliar or Gerencia enters
what the company keeps from the deal (after colleagues and referrals, without IVA) in «Negocios
cerrados». Commissions are generated at that moment.

| Who | What | Example rule |
|---|---|---|
| Asesor who closed | Commission | ganancia × 33.3 % × 70 % |
| Asesor who got the property | Commission | ganancia × 33.3 % × 30 % (not paid if there's no captador) |
| Atención y Preventa | Commission for a cita that ended in a deal | ganancia × 5 % |
| Coordinador | Group commission | 2.5 % of the team's ganancia, when the month reaches $20.000.000 |
| Everyone with a result | Performance bonus | $200.000 if the month's Rendimiento is ≥ 80 % (Coordinador: per «modalidad») |

Bonuses and the group commission are calculated with «Calcular bonos de …» once the month has ended.
Running it twice doesn't duplicate anything. Gerencia and the Auxiliar can also record a commission
or bonus by hand.

**Approval flow** (G05): Generada → «Dar visto bueno» (Auxiliar only) → «Aprobar» (Gerencia only).
Approving schedules a payment «en proceso» for the 5th of the next month. Then «Registrar pago»
(Gerencia) marks it Pagada. Before approval, either of them can «Ajustar» the amount (needs a
reason, and goes back to Generada for a new visto bueno). Either can «Anular» with a reason. Every
step is in the «Historial» (`compensacion_eventos`).

**Salaries** (X04): Gerencia sets each person's monthly salary. Each pay period is half of it (paid
on the 15th and the 30th). The Auxiliar «Confirmar a pagar», and Gerencia «Aprobar y pagar», which
creates the payment. Incapacidades and permisos no remunerados from «Ausencias y permisos» are
discounted automatically (see Novedades below). There are no other deductions yet.

**Who sees what**:
- Everyone sees their own pay in «Mis pagos y bonos» (Z05 table on desktop, M12–M14 cards on mobile;
  asesores also reach it from «Mis resultados»).
- The Auxiliar and Gerencia see and manage everything.
- **Coordinación sees only its own**, following DECISIONS (pay data is outside Coordinación's scope).

**Simplifications** (to revisit when the related modules exist):
- The trigger is still the lead «Ganado». Since «Negocios» exists, the ganancia comes from the deal's value
  and Gerencia's tariffs when the Auxiliar gives «negocio cerrado»; entering it by hand here still works
  for deals without a value.
- No partial commission payments for sales.
- Hours worked don't change the salary: Asistencia records entry and exit, but «Horas trabajadas»
  (X03) and «Valor y productividad» (G08) aren't built. Absences do (Novedades).
- No legal deductions (salud, pensión) or auxilio de transporte.
- «Excel» downloads are CSV, and there's no PDF certificate yet.

Endpoints:
- `GET /compensacion/mio`, `GET /compensacion` (G05 board), `GET /compensacion/export.csv?tab=`
- `POST /compensacion/{comisiones|bonos}` and `/{comisiones|bonos}/{id}/accion`
- `POST /compensacion/pagos/{id}/pagar`, `PUT /compensacion/cierres/{id}`
- `POST /compensacion/calcular?periodo=`, `PUT /compensacion/config`, `GET /compensacion/historial/{entidad}/{id}`
- `GET /compensacion/salarios?periodo=&corte=`, `POST /compensacion/salarios/accion`,
  `PUT /compensacion/salarios/config/{user_id}`

The demo seed (`seed_compensacion`) sets salaries, registers the ganancia of every deal except the two
newest, takes last month through to payment (including bonuses and the group commission), leaves
this month in a mix of states, and pays the salary periods whose day has passed.

## Inmuebles (`/inmuebles`)

The property catalog. Rules are in `backend/app/services/inmuebles.py`.

**Prototype note**: X14 is «Administración de inmuebles» (move-in/move-out inventories, repairs,
owner and tenant requests), not a catalog, and no prototype has a catalog screen. So:
- The page borrows X14's layout: KPI cards that filter, tabs, a filter row, and cards that expand
  to show details and history.
- The fields come from the full captación form (M15).
- «Enviar opciones» follows C02.
- X14's operations (inventories, repairs, complaints) are their own page:
  «Administración de inmuebles» below.

**Where properties come from**: when Coordinación approves a captación, its property is created
with the same code, or an existing one with that code is linked and its empty fields are filled.
The captación and its captador are recorded. A quick captación (only code and address) makes a
property with «datos incompletos». Coordinación and Gerencia can also register one by hand. A code
with a captación still «por verificar» is refused, because approving it creates the property.

**Statuses** (none are defined in the prototypes, so these are a simplification):
- disponible → separado → arrendado (rentals) or vendido (sales), or retirado
- Separado and retirado need a note.
- Only Coordinación and Gerencia change the status.
- Only «disponible» properties can be offered to a client.

**Who**:
- Asesores, Atención y Preventa, the Auxiliar, Coordinación and Gerencia see the catalog.
- The owner's name and phone are only shown to Coordinación, Gerencia, the Auxiliar and the
  property's captador.
- The captador can complete the data of their properties («Mis captaciones» tab), but not the
  code, business type or status.
- New properties come from «Nueva captación». Registering by hand is only for Coordinación and
  Gerencia.
- Deleting is only for properties registered by hand and never sent to a client. The rest are
  «retirado».

**Filters**: negocio, tipo, zona (same list as pedidos), price range (same ranges as pedidos), at
least N bedrooms, «datos incompletos», and text (code, address, barrio, municipio).

**Used elsewhere**:
- Lead «Enviar opciones» (C02): pick available properties of the lead's business type, with the
  lead's zone first and «Ya enviado» on those already sent. The lead's history lists the codes, and
  each property's history records which client it was sent to.
- Pedido «Proponer un inmueble»: pick from the catalog, or keep typing freely.

**Simplifications**:
- A closed deal doesn't change the property's status automatically, because leads and citas aren't
  linked to a property yet (the cita's «inmueble» is still free text).
- No photos.

Endpoints:
- `GET /inmuebles` (filters and KPIs), `GET /inmuebles/opciones`, `POST /inmuebles`
- `GET`, `PATCH`, `DELETE /inmuebles/{id}`, `POST /inmuebles/{id}/estado`
- `GET /inmuebles/para-lead/{lead_id}`

The seed (`seed_inmuebles`) registers the codes the prototypes use in different statuses, brings
in every approved captación, and has captadores complete most quick ones (a few stay incomplete).

## Administración de inmuebles (`/inmuebles/administracion`, X14)

Inventories, repairs, and owner / tenant requests, each linked to a property in the catalog.
Rules are in `backend/app/services/administracion.py`. The page follows X14: six KPI cards that
pick the tab (and its status filter), three tabs, «Desde / Hasta / Estado» filters, a «nuevo» form
and cards that expand. The catalog links to it, filtered to one property
(`?inmueble=<id>`, «Inventarios y reparaciones» on each card).

**Inventarios (INV-xxx)**: «Entrega al inquilino» or «Recepción al terminar».
- programado → realizado (the asesor checked a room) → firmado, or «con novedades» if a room is
  regular / malo.
- A new inventory has X14's eight rooms. Each one gets bueno / regular / malo, a note (required
  for regular and malo) and a photo count.
- Signing needs every room checked. After that the inventory is locked.
- «Crear solicitud de reparación con las novedades» makes one repair from the findings, only once.
- Only a «programado» inventory can be rescheduled or deleted.

**Reparaciones (MAN-xxx)**: recibida → cotizada → aprobada → en ejecución → terminada.
- Leaving «recibida» needs a provider and a quote, and «terminada» needs to know who pays.
- After «terminada» the repair is locked. Its time is counted from the report date to the end date.
- «Registrar avance» logs provider, amount, who pays and a comment.
- Only a «recibida» repair can be deleted.

**Solicitudes (PQR-xxx)**: petición / queja / reclamo / sugerencia, from the owner or the tenant,
with channel and priority.
- abierta → en trámite → respondida (by sending the answer) → cerrada.
- Closing a request with no answer needs a reason.
- The deadline is **15 business days** (`PLAZO_DIAS_HABILES`). An open request past it shows as
  «Fuera de plazo» (in red, with its own KPI and filter).

**Who**:
- Coordinación, Gerencia and the Auxiliar see and manage everything: they schedule, assign,
  change statuses, register signatures and delete.
- Anyone else who can see the catalog (asesores, Atención y Preventa) sees **only the records
  assigned to them** and works on them. The asesor fills in their inventory, the person following
  a repair logs progress, and the person in charge of a request answers it.
- Other people's records return 404. The KPIs count only what the user can see.
- A property with any of these records can't be deleted from the catalog: it's «retirado».
- Each record keeps its history, and the property's history shows the main steps.

**Simplifications** (X14 marks several of these «PENDIENTE DE CONFIGURACIÓN»):
- **Photos are a count per room**. There's no file upload yet.
- Signatures are one action by the Auxiliar / Coordinación / Gerencia («firmado por propietario e
  inquilino»), not a digital signature. There's no inventory document (acta) yet.
- X14's «avance» is one free-text field that the prototype parses. Here it's a small form (provider,
  amount, who pays, comment).
- Repair statuses can be set in any order (as in X14), except for the two checks above.
- When the owner pays, there's no automatic discount in their settlement, no management % and no
  hand-off to the financial software.
- Providers are free text: there's no provider list.
- No notifications: X14 alerts Gerencia about urgent repairs and late requests. Here they're
  only highlighted in red.
- Business days are Monday to Friday, without Colombian public holidays.
- Responsables can be anyone active who can see the catalog, plus the Auxiliar and managers.

Endpoints (`/api/v1/administracion-inmuebles`):
- `GET /resumen` (KPIs, properties, responsables, labels)
- `GET|POST /inventarios`, `GET|PATCH|DELETE /inventarios/{id}`,
  `PATCH /inventarios/{id}/ambientes/{ambiente_id}`, `POST /inventarios/{id}/firmar`,
  `POST /inventarios/{id}/reparacion`
- `GET|POST /reparaciones`, `GET|PATCH|DELETE /reparaciones/{id}`,
  `POST /reparaciones/{id}/avance`, `POST /reparaciones/{id}/estado`
- `GET|POST /solicitudes`, `GET|PATCH|DELETE /solicitudes/{id}`,
  `POST /solicitudes/{id}/responder`, `POST /solicitudes/{id}/estado`
- The lists take `desde`, `hasta`, `estado` (`fuera_de_plazo` for requests) and `inmueble_id`.

The seed (`seed_administracion`) adds X14's example records with dates relative to today:
- inventories: one with findings (already turned into a repair), one clean, two this week;
- repairs at every stage;
- requests: open, late, answered, and one assigned to `asesor@example.com`.

## Novedades: ausencias y permisos (`/novedades`, K13)

**Prototype note**: K13 «Novedades» is about the **staff**: absences and permits per employee, plus
a tab for the novedades reported in the preoperacional. It has no leads, captaciones, inmuebles,
priority or assignment, so those aren't part of this module.

Rules are in `backend/app/services/novedades.py`.

**Incapacidades y permisos** (tab 1):
- Types: incapacidad, permiso no remunerado, permiso remunerado.
- Each one has an employee, «desde» and «hasta», a note, and a supporting-document count.
- Days are calendar days, both ends included («1 y 2 oct» = 2 días).
- One person can't have two registered novedades on the same days, and one novedad can't pass 180
  days.
- Statuses: «registrada», or «anulada» (needs a reason). An annulled one stays on record, hidden
  unless «Ver anuladas» is on, and stops counting.
- Only the note and attachments can be edited. Wrong dates or type: annul it and register it again.
- Three cards: days of each type inside the «Desde / Hasta» range (this month by default).
- The table shows Empleado, Tipo, Fechas, Días, Observación and Registro. Click a row for the
  details and actions. Filters: type, employee, «Ver anuladas».

**Salary** («Salarios del mes»):
- Incapacidad and permiso no remunerado are discounted at salario mensual ÷ 30 per day, in the pay
  period(s) they fall in (1–15 and 16–end of month). The discount is capped at the period's salary.
- The period's «Novedades» column shows a summary, e.g. «Permiso no remunerado 2 días · Permiso
  remunerado 1 día». The paid permit is only counted.
- Only periods «por confirmar» change: registering, annulling or a new salary recalculates them.
- A period already confirmed by the Auxiliar or paid by Gerencia isn't touched. The response
  warns about it («ajústalo a mano»).

**Del preoperacional** (tab 2): the preoperacionales with a novedad in the range, with «Por revisar»
or «✓ Revisada». «Marcar como revisada» uses the existing `POST /preoperacional/{id}/revisar`, with
the same rules as K09: Coordinación reviews its team, Gerencia reviews everyone, the Auxiliar only
views.

**Who**:
- Coordinación and the Auxiliar register and annul.
- Gerencia sees everything but doesn't register (as in K13, where Gerencia receives them).
- Nobody else opens the page. Employees see their discount in «Mis pagos y bonos».

**Navigation**:
- Sidebar «Ausencias y permisos»: in EQUIPO for Coordinación and Gerencia, in PERSONAL for the
  Auxiliar.
- «Ausencias» in the Auxiliar's bottom nav.
- A card on the Coordinación / Gerencia dashboard, since their bottom nav is full.

**Simplifications**:
- Supporting documents are a count; there's no file upload yet.
- No notifications: K13 says «le avisa a Gerencia». Here Gerencia sees the novedades on this page,
  and the «Registro» column shows who registered each one and when.
- Incapacidades are discounted as K13 says. The EPS / ARL reimbursement and its rules (who pays from
  which day) aren't modelled.
- The top button goes to «Asistencia del día» (K17, see Asistencia).
- K13's «Del preoperacional» also lists people who didn't do it today. That stays in
  «Preoperacionales» (K09).

Endpoints (`/api/v1/novedades`):
- `GET /opciones` (types, help text, employees, default range)
- `GET ?desde=&hasta=&tipo=&empleado_id=&anuladas=` (list, days per type, preoperacional novedades
  to review)
- `POST` (returns `avisos` for confirmed / paid periods)
- `GET|PATCH /{id}` (note and attachments only)
- `POST /{id}/anular` (`{motivo}`)
- `GET /preoperacional?desde=&hasta=`

The seed (`seed_novedades`) registers K13's example rows this month. It adds one more permiso no
remunerado on the 20th–21st, so an unconfirmed period shows a discount, and one annulled by
mistake.

## Movimientos y GPS (`/movimientos`, K05)

**Prototype note**: K05 «Movimientos y GPS» isn't a generic movements ledger. It's the **field / GPS
control** of the staff: alerts when an asesor leaves the route or stays still too long, their
justification and review, and the Coordinador's / Atención y Preventa's field work. There are no
amounts. A movimiento links to an employee and, when it applies, an inmueble (by code, linked to the
catalog if it exists) or a cita (apoyo en cita). Leads and captaciones are reached through the cita;
there's no direct link. Built from K05 / K05-ger, M05 «Justificar», K16 and C09 «Trabajo en campo»,
and decisions G-002, G-036, G-039, G-040, G-048 and G-081.

Rules are in `backend/app/services/movimientos.py`.

**Types** (codes `MOV-0001`…):
- Alerts: «Salida de ruta», «Tiempo detenido» (asesores with Captación), «Salida de la zona»
  (Coordinador). The Coordinador and Atención y Preventa also get «Tiempo detenido», but only
  while they're in the field: their GPS is on only then.
- Field records: «Trabajo en campo (Coordinador)» (apoyo en cita, acompañamiento en ruta, salida
  grupal, otra) and «Atención en campo» (apoyo en cita, otra; no acompañamiento, G-040).

**Statuses**: Sin justificar → Justificada · por revisar → ✓ Aprobada / ✕ Rechazada · −1 punto.
Field records are «Registro de campo». «Vencida» isn't stored: it's an alert still unjustified
after the deadline.

**Rules**:
- The GPS only reports during the working day (8:00 a. m.–6:00 p. m.). A late report from a phone
  that was offline is accepted up to 24 h later.
- Justifying (M05, only the person): a cita fuera de ruta / cita no programada / inventario needs
  the inmueble code, client and observation. A personal reason needs the reason, plus who
  authorized it (salidas) or optional evidence (tiempo detenido).
- Coordinación reviews asesores and Atención y Preventa. Gerencia reviews the Coordinador (as in
  K05-ger, Gerencia doesn't review asesores). Nobody reviews themselves. The review note is optional.
- A rejected alert, or one left unjustified past the deadline, takes **1 point** off that month's
  rendimiento (shown in «Descuentos» on the results page). A pending alert also shows as an aviso
  there.
- The deadline is **PENDIENTE DE CONFIGURACIÓN** until Coordinación or Gerencia sets it on the page.
  Until then nothing expires. Once it passes, the alert can't be justified any more.
- Coordinación and Gerencia set the stopped time that triggers an alert (15 / 20 / 30 / other
  minutes, 20 by default) on the same page. Each alert keeps the threshold it was created with.
- One open field record per person. Finishing it turns the GPS off. A record left open counts
  until 6:00 p. m. that day.
- Location privacy: lists never return coordinates. «Ver ubicación» calls `POST /{id}/ubicacion`,
  which logs who looked and when in the history.
- History: every action (registered, justified, approved, rejected, finished, location viewed) is
  a `movimiento_eventos` row with actor, time and status before → after. Config changes and
  downloads are logged too, without a movimiento.

**Who sees what**:
| Role | Page |
|------|------|
| Gerencia | «Indicadores y registro» (Desde/Hasta, last 30 days by default; empleado, acción, estado filters; 6 KPIs; «Por empleado» 5 at a time; registro with «Ver más»; CSV download) and «Configuración y mapa» |
| Coordinación | «Hoy, configuración y mapa» (K05), plus «Indicadores y registro» and «Mi trabajo en campo» (K16) |
| Asesor with Captación | «Mis alertas de GPS»: their alerts and the M05 form |
| Atención y Preventa | «Trabajo en campo y GPS»: start / finish field work (C09), their alerts |
| Auxiliar, asesores without Captación | No access (no GPS) |

**Navigation**: sidebar «Movimientos y GPS» in EQUIPO for Coordinación and Gerencia (G-081 puts it
under «Empleados»), plus a card on the Coordinación / Gerencia dashboard since their bottom nav is
full. Asesores with Captación and Atención y Preventa get it in MI DÍA and in the bottom nav («GPS»
/ «Campo»).

**Simplifications**:
- No real GPS tracking. `POST /movimientos/alertas` is the endpoint the phone would call; the demo
  alerts come from the seed. Route and zone detection belong to that future integration.
- The map is a schematic SVG like the prototype's: today's positions placed relative to each
  other, not a real map. «Ver ubicación» opens OpenStreetMap.
- «Descargar (Excel)» downloads a CSV that Excel opens (same as Rendimiento).
- No notifications: M05 opens from the bell in the prototype. Here the person sees their pending
  alerts on the page and as an aviso in «Mis resultados».
- «Días en campo programados» (K16 / C09) isn't built, and isn't part of the Agenda either.
- Coordinación's page adds the registro and «Mi trabajo en campo» tabs to K05's single view, so it
  has the history and filters too and can register its own field work.
- Evidence for a tiempo detenido is a file count, like the other modules (no uploads yet).

Endpoints (`/api/v1/movimientos`):
- `GET /opciones` (labels, motives per type, what this person can start, asesores and citas for
  field work, config, default range)
- `GET ?desde=&hasta=&empleado_id=&tipo=&estado=` (list + KPIs + per person + own pending alerts;
  everyone except Coordinación / Gerencia only gets their own)
- `GET /export.csv` (same filters; Coordinación / Gerencia)
- `GET /panel` (config, who has GPS, people in the field now, today's alerts, map points)
- `PUT /config` (`{minutos_alerta?, plazo_horas?}`; `plazo_horas: null` sets it back to pending)
- `POST /alertas` (`{tipo, ocurrido_at?, lat?, lng?, lugar?}`: the phone reports an alert)
- `POST /campo` (`{tipo_campo, actividad_campo, cita_id?, acompanados_ids?, detalle?}`)
- `GET /{id}` · `GET /{id}/historial`
- `POST /{id}/justificar` · `/aprobar` · `/rechazar` (`{nota?}`) · `/finalizar` · `/ubicacion`

The seed (`seed_movimientos`) loads K05-ger's example log over the last 30 days: today's alerts for
the asesor (one to justify, one to review, one approved), Bruno's, the Coordinador's (one waiting for
Gerencia), Atención's, and the Coordinador's / Atención's field work. «Today» rows whose time hasn't
come yet move to yesterday.

## Plataformas tradicionales (`/plataformas`, K15)

**Prototype note**: K15 «Actualización de plataformas» isn't about publishing listings. It's the
**control of the paid real-estate portals** (Ciencuadras, Espacio Urbano, Proppi…): each portal's
plan (price, dates, quota, featured listings), the periodic «actualización» where someone checks
the portal and records what's used, and how much each portal brings in. Built from K15 (Coordinación)
and K15-ger (Gerencia), and decisions G-019, G-0xx (rendimiento del Coordinador) and G-079.

Rules are in `backend/app/services/plataformas.py`.

**Model**:
- `plataformas`: one row per portal. Its `fuente` matches the leads' source, so results come from
  real leads. It has a colour, an active flag and the assigned responsable.
- `plataforma_planes`: each paid period (price, activation, expiry, total quota, featured listings,
  alarm days). A renewal is a new row, so past costs stay right.
- `plataforma_actualizaciones`: each update (active listings, total quota, featured used, note),
  with who did it, who was responsable then, days since the previous one and whether it was on time.
- `plataforma_eventos`: registro de cambios (responsable, plans, on/off, rule, downloads).
- `plataformas_config`: the rule «se debe actualizar al menos cada N días».

**Statuses**:
- Portal: «Al día», «Atrasada» (last update more than N days ago) or «Sin actualizar».
- Update: «A tiempo», or «Tarde (más de N días)» when it came more than N days after the previous one.
- Plan: «Activo · vence 14 oct», «⚠ Vence en N días» (inside the alarm), «Vencido · inactivo»,
  «Renovado · sigue desde …» (the next plan is already registered) or «Sin plan registrado».

**Rules**:
- The rule is 7 days, an example value shown as «PENDIENTE DE CONFIGURACIÓN» until Gerencia saves it.
- Publicaciones activas can't pass the cupo total, nor destacados usados the plan's destacados.
  The «Cupo total del plan» typed in an update also corrects the current plan.
- Cost of a range = each plan's price spread over its days × the plan days inside the range, up to
  today. Cost per lead / per cierre divides that.
- Leads = leads created in the range with that `fuente`; citas = their citas in the range (not
  cancelled); cierres = their leads «Ganado» in the range.
- **Rendimiento**: the Coordinador's «Actualización de plataformas» area (until now «sin datos»)
  is the share of days of the month that the portals assigned to them were «al día». With nothing
  assigned, the area has no data and doesn't count.

**Who**:
| Role | Can |
|------|-----|
| Coordinación | K15: see the portals and register updates for any of them; download the history |
| Auxiliar administrativa | Same page; registers only the portals assigned to her (she appears in K15-ger's log) |
| Gerencia | K15-ger: «Actualizaciones» (KPIs, last update per portal, assign responsable, the rule, log with «Ver más»), «Resultados de los portales» (KPIs, per-portal table, plans, leads per month chart), «Histórico y descarga». Doesn't register updates. |
| Everyone else | No access |

The responsable can be someone from Coordinación or the Auxiliar.

**Navigation**: «Actualización de plataformas» (Coordinación) / «Plataformas tradicionales»
(Gerencia) in COMERCIAL, as in the Coordinación menu (G-0xx moved it into Comercial). The Auxiliar has
it in PERSONAL. There's also a card on the Coordinación / Gerencia dashboard. No bottom-nav item:
these are desk tasks and the managers' bottom nav is full.

**Simplifications**:
- Plans are registered by Gerencia on this page (tap the plan chip in «Resultados»). The prototype
  expects them to come from «Integraciones» (G-019), which has no live connectors yet. The portals are the
  traditional `fuente` values: Finca Raíz and Metrocuadrado exist but start inactive. A brand-new
  portal needs a new `fuente_lead` value (migration).
- The download is a CSV that Excel opens. There's no PDF option.
- Atención y Preventa doesn't appear as a possible responsable (K15-ger lists them, but no Atención
  screen links to K15, so they couldn't register).
- Rendimiento uses the current responsable for the whole month: changing it mid-month moves the
  whole month to the new person.
- No automatic expiry notification: the alarm shows as the plan chip.

Endpoints (`/api/v1/plataformas`):
- `GET /opciones` (portals, responsables, who has updated, default range: last three months)
- `GET ?desde=&hasta=&plataforma_id=&quien_id=` (portals with status, KPIs, updates in the range)
- `GET /resultados?desde=&hasta=&plataforma_id=` · `GET /historico` (5-row preview) · `GET /historico.csv`
- `GET /cambios` (registro de cambios) · `PUT /regla` (`{dias_regla}`, Gerencia)
- `POST /{id}/actualizaciones` (`{cupo_usado, cupo_total, destacados_usados, destacados_total?, observacion?}`)
- `PUT /{id}/responsable` · `POST /{id}/planes` · `PUT /{id}/activa` (Gerencia)

The seed (`seed_plataformas`) creates the three K15 portals with K15's quotas and prices: the
current quarterly plan, the previous one, and about five months of updates with K15's gaps. Proppi
is late and about to expire. It also adds closed leads from the portals for the last four months
(K15-ger's figures): mostly «Perdido», a few «Ganado». The «Ganado» ones show up as deals in
Compensación, without a closing asesor or commission.

## Configuración (`/configuracion`, Z02)

Built from Z02 (Coordinación) and Z02-ger (Gerencia). Rules are in
`backend/app/services/configuracion.py`.

**Storage**: table `configuracion`, one row per section. It stores only the values that differ from
the defaults; the defaults live in code (`DEFAULTS`), so nothing needs seeding and a fresh database
shows Z02's example values. Every change goes to `configuracion_eventos` with who, when, and the
values before and after. The page shows the last 15.

**Sections** (Gerencia edits everything; Coordinación only reads the pay dates):
| Section | What | Used by |
|---------|------|---------|
| Marca | Logo (PNG or SVG, < 150 KB, stored as a data URL), name, tagline, three greens | **Wired**: sidebar, mobile bar, login and `BrandLogo`. Greens become CSS variables on `<html>` during server rendering (hover and sidebar shades are derived). Traffic-light colours never change. `GET /configuracion/marca` is public so the login page can show it. |
| Pendientes para salir a producción | 10 items. 3 resolve themselves when set where they live (GPS deadline in Movimientos, the update rule in Plataformas, retención in Tarifas); 7 Gerencia ticks as defined. «Activar uso real» only works with none left. | The flag is stored; nothing else changes with it yet |
| Fechas de pago al personal | Salary cuts and the commission pay day | **Wired**: reads and writes Compensación's config (`dia_corte_1`, `dia_corte_2`, `dia_pago`), already used by «Salarios del mes», «Comisiones» and «Mis pagos» |
| Tarifas de intermediación | Arriendo %, papelería, IVA, venta %, referidos %, retención (empty = pending) | **Wired**: ganancia of each deal in «Negocios» |
| Automatizaciones y avisos | Minutes before a lead without responsable alerts; daily summary time; escalation | **Wired**: the minutes drive the «sin responsable» alert on the Coordinación dashboard (was hardcoded at 15). The other two are stored for the future notifications module. |
| Idioma | Español / English / Italiano | Only Spanish can be applied; the others show «traducción pendiente» |
| Leads ganados y perdidos | Points per lead ganado / perdido; minimum calls on consecutive days | **Wired**: rendimiento of Atención y Preventa (was `PUNTOS_LEAD_*`) and `leads.perdida_descuenta` (was 3 calls in 3 days). Values are chosen from lists, and a lost lead must cost less than a won one adds. |

The cards at the bottom link to the settings that live on their own pages (users, absences,
indicators and weights, compensation, salaries, GPS, platforms).

**Simplifications**:
- The automations status table only lists what really runs: the unattended-lead alert and the lead
  points. The others say «Pendiente: módulo de avisos» instead of Z02's example statuses.
- Lead points apply to the whole current month when changed. Z02 says «desde el día siguiente»,
  which would need the rules' history per day. The call rule applies to leads marked lost from then on.
- Cards for screens that don't exist are left out: cargos laborales, costos del personal, valor y
  productividad and carga de leads desde Excel.
- «Si el día cae en fin de semana o festivo, se paga el día hábil anterior» is still pending, as in
  the prototype.
- Z02's list of 26 pendientes (G-053) is reduced to the 10 it shows.

Endpoints (`/api/v1/configuracion`):
- `GET /marca` (public) · `GET` (the whole page; Coordinación gets only brand and pay dates)
- `PUT /marca` · `POST /marca/restaurar` · `PUT /pagos`
- `PUT /tarifas` · `PUT /automatizaciones` · `PUT /idioma` · `PUT /leads` (partial updates)
- `PUT /pendientes/{clave}` (`{resuelto}`) · `POST /uso-real`

## Avisos (`/avisos`, G09 · M10 · C05)

**Prototype note**: G09 «Avisos y agenda» (Gerencia) and M10 / C05 «Notificaciones» (asesor, Atención)
aren't a bulletin board. An aviso says **what happened, what to do, until when, and has the button to
do it**. Decisions: the bell only gets what asks for an action with a deadline; informative notices
go to «Resumen del día»; no aviso repeats. Rules are in `backend/app/services/avisos.py`.

**Model**:
- `avisos`: one notice for one person. `origen` is `sistema` (generated, with a `clave` per event,
  unique per person) or `comunicado`. It stores the chip, level, title, detail, «qué debes hacer»,
  deadline, link + button text, G09's data boxes, `requiere_accion` (bell vs. resumen), status
  (por atender / atendido, by hand or resolved on its own) and `leido_at`.
- `aviso_notas`: «Agregar nota». `comunicados`: announcements; each copy is an aviso and its
  `leido_at` is the read receipt. `agenda_items`: «Mi agenda».

**System avisos**: generated when the person opens the page or the bell polls (every minute). Each
generator returns what is pending now. A new event creates an aviso, a pending one is refreshed, and
one whose event is gone closes itself as «✓ Resuelto». Attended by hand stays attended.
| Aviso | Who gets it | Closes on its own when |
|-------|-------------|------------------------|
| Lead sin responsable (after the minutes set in Configuración) | Coordinación | someone takes the lead |
| Nuevo lead (last 3 days, no responsable) | Atención y Preventa | same |
| Cita por aceptar | the asesor | accepted / rejected |
| Cita rechazada | Coordinación; Atención for its own leads | reassigned / cancelled |
| Justificar (GPS alert) | the person | justified (or the deadline passes) |
| Justificación por revisar | Coordinación (asesores, Atención) / Gerencia (Coordinador) | reviewed |
| Captación por verificar (warn after 24 h) | Coordinación | verified |
| Novedad del preoperacional | Coordinación | reviewed |
| Plataforma atrasada | its responsable (Coordinación if none) | updated |
| Salarios por confirmar / por aprobar | Auxiliar / Gerencia | confirmed / paid |
| Comisiones y bonos (visto bueno / aprobar / pagar) | Auxiliar / Gerencia | the next step is done |
| Área por debajo del 60 % (weekly) | Gerencia | — Gerencia closes it |
| Actividad asignada (someone put it in your agenda) | the owner of the agenda | done, rejected or justified |
| Ausencias y permisos del mes (informative) | Gerencia | — («Resumen del día») |

**Actions on an aviso** (G09): the button to go and do it, «Agregar nota», «Agendar en mi agenda»
(creates the agenda item and leaves a note), «Marcar como atendido» and «Abrir de nuevo».

**Comunicados** (requested; not in the prototypes): Gerencia sends to any cargo, Coordinación to
asesores and Atención y Preventa. «Alta» goes to the bell («Léelo y márcalo como atendido»);
«normal» goes to «Resumen del día». They can stop showing after a date. Showing it in «Resumen del
día» or attending it marks it read; «Avisos enviados» shows «Leído por N de M» and who. Gerencia
sees every comunicado, Coordinación its own.

**Navigation**: «Avisos y agenda» (Gerencia) / «Notificaciones» (everyone else) right under Inicio
in the sidebar, with a red badge of what is «Por atender». On the phone, a bell with the badge in the
top bar. Everyone has the page; each person only sees their own avisos and agenda.

**Simplifications**:
- «Mi agenda» is the Agenda module below (`/agenda`, and the tab in «Avisos y agenda»).
- The area check uses the month so far (the previous month during the first week), not the last
  calendar week: rendimiento has no weekly cut. It runs at most once per ISO week.
- Avisos are generated on request, not by a background job: no push, sound or email. Reminders at
  the time of an agenda item, the 7:30 summary and escalation (Configuración) wait for that job.
- Accept / reject a cita, «Seguir lead» and similar act on their own pages: the aviso's button
  takes you there, instead of confirming inside the notification as on M10.
- G09's «Integración» aviso isn't generated: Integraciones has no live connectors, so nothing fails.

Endpoints (`/api/v1/avisos`):
- `GET /conteo` (the bell: `por_atender`, `resumen_sin_leer`, `agenda_hoy`) · `GET ?vista=por_atender|atendidos|resumen`
- `POST /{id}/atender` (`{nota?}`) · `POST /{id}/reabrir` · `POST /{id}/notas` · `POST /{id}/agendar` · `POST /leidos` (`{ids}`)
- `GET|POST /comunicados` (`{titulo, cuerpo, audiencia[], prioridad, expira_el?}`) · `GET /opciones`

The seed (`seed_avisos`) sends two comunicados (Gerencia «alta» to everyone; Coordinación «normal» to
asesores and Atención), some already read, and puts G09's example activities in each person's
agenda. System avisos come from the demo data the first time each person opens the page.

## Agenda (`/agenda`, G09 · M17 · C07 · X06 · K19)

Decisions G-088 («Agendas con jerarquía»), G-089 («Agenda sencilla y dinámica») and G-090 (tasks
«Atrasada»). Rules are in `backend/app/services/agenda.py`; the page is `components/AgendaView.vue`,
used by `/agenda` and by the «Mi agenda» tab of «Avisos y agenda».

**One view per person** that joins what the system puts there with activities added by hand:
| Colour (legend) | What | From |
|-----------------|------|------|
| Cita | citas of the asesor; for Atención also the citas of its leads | Citas |
| Seguimiento | follow-ups of the leads assigned to the person | Leads |
| Vencimiento | open pedidos whose deadline falls that day | Pedidos |
| Control e inventario | visita de control and inventario citas | Citas |
| Agregada por la persona / Asignada por otra persona | activities added by hand | `agenda_items` |

System items are read-only. «Abrir ›» only shows in your own agenda.

**Who sees which agenda** (G-088): each person their own; Coordinación also asesores' and Atención
y Preventa's; Gerencia and the Auxiliar everyone's. Asesores and Atención only see their own (between
asesores nothing is seen or touched).

**Who adds in which agenda**: each person in their own; Coordinación in asesores' and Atención's;
Gerencia in all; the Auxiliar in all but Gerencia's.

**Activity statuses**: Pendiente · **Atrasada** (pending and its date/time passed) · ✓ Hecha ·
Rechazada · Justificada.

**What can be done** (shown in the detail when you tap an activity):
- The owner of the agenda marks it **hecha** (if pending).
- What **someone else** put can't be deleted by the owner: it's **rejected** or **justified**, with
  a mandatory reason. Whoever put it gets an aviso in «Resumen del día» («Juan rechazó «…» · Motivo:
  …», or «marcó hecha»).
- Each person only **deletes** what they put (also in someone else's agenda). It stays in
  «Actividades eliminadas» (the small link at the bottom) with who deleted it and when, and who had
  put it and when.
- When someone puts an activity in your agenda you get «Actividad asignada» in the bell; it closes
  on its own once you answer it.

**Top bar** (G-089, the same in every agenda): «Agenda de [persona]» (only for whoever can see other
agendas), ‹ › and «Hoy», Día / Semana, «+ Agregar». The week starts today (seven days). «Agregar»
asks in which agenda (only the allowed ones), the activity, date, time, priority and note.

**Navigation**: «Agenda» (Coordinación) / «Mi agenda» (everyone else) under «Notificaciones» in the
sidebar, with a grey badge of today's pending activities. Gerencia has it in «Avisos y agenda»
(G-089) and can also open `/agenda`. «Agendar en mi agenda» from an aviso adds to your own agenda.

**Simplifications**:
- Accepted route zones appear (M17's «Ruta del coordinador», see Rutas). Firmas, pólizas and other
  system items X06 shows aren't there: firmas (Negocios), pólizas, salaries and commissions come
  as avisos instead. Programmed capacitaciones do appear.
- No reminder at the time of each activity and no Google Calendar / Outlook sync: they need the
  background job and Integraciones.
- An activity can't be edited: delete it and add it again (only what you put). Dates in the past
  aren't accepted.
- The deleted list shows the last 20 for that agenda.

Endpoints (`/api/v1/agenda`):
- `GET /personas` (the agendas you can see, yours first, with whether you can add in each)
- `GET ?user_id=&desde=&hasta=` (items, deleted, legend; default 7 days from today, max six weeks)
- `POST` (`{para_id?, titulo, fecha, hora?, prioridad, nota?}`)
- `POST /{id}/hecha` · `POST /{id}/rechazar` (`{motivo}`) · `POST /{id}/justificar` (`{motivo}`) · `DELETE /{id}`

The seed (`seed_agenda`) adds G09's activities between people: Coordinación → asesores and Atención,
the Auxiliar → an asesor, Gerencia → Coordinación and the Auxiliar. One was rejected with a reason
and one deleted by whoever put it. Personal activities come from `seed_avisos`.

## Mi perfil (`/perfil`, Z01 · M11)

Built from Z01 (Atención), Z01-coord, Z01-aux, Z01-ger and M11 (asesor, phone), and the decision
«Foto y nombre en el perfil». Rules are in `backend/app/services/perfil.py`.

**What the person can change** (the decision): **their photo** and **their password**. The name and
the other personal data (teléfono, cédula, fecha de ingreso) are changed only by Coordinación or
Gerencia in «Usuarios» (same rules as before: Coordinación can't touch Gerencia's users). Every
change is logged with the value before and after, who and when. The page says it in each cargo's
words: «Tu nombre lo cambia Gerencia», «…los cambian Coordinación o Gerencia; si algo está mal,
avísale a tu coordinador».

**New user fields**: `telefono`, `documento` (cédula), `fecha_ingreso`, `foto` (a data URL, loaded
apart because it can be large) and `politica_aceptada_at`. **`user_cambios`** holds the history of
name, cargo, status, teléfono, cédula, fecha de ingreso, photo and password changes. The cédula is
stored only masked there, and the photo as «con / sin foto». «Usuarios» › «Editar datos» shows it.

**Page** (as Z01):
- Photo (or initials) with name and cargo, the activities (asesor), «Cambiar foto» / «Quitar foto».
- «Mis datos»: área, correo (usuario), teléfono, fecha de ingreso, the row of each cargo
  (Coordinador · Equipo a cargo · Reporta a · Acceso) and the cédula masked («••••••2210»). Asesores
  also see their means of transport from their last preoperacional (M11).
- «Mis resultados · [mes]» card for whoever has a result (asesores, Atención, Coordinación).
- «Accesos rápidos» (M11): resultados, pagos y bonos, preoperacional, agenda.
- «Seguridad»: change password, «Cerrar sesión» (with confirmation), and the data policy acceptance
  date (or a button to accept it).

**Navigation**: the name card at the top of the sidebar shows the photo and opens «Mi perfil»
(decision «Foto visible…»). There's also «Mi perfil» next to «Cerrar sesión», and on the phone the
avatar in the top bar opens it.

**Simplifications**:
- **Password**: the prototype sends a link to the email; there is no email service, so it's changed
  on the page with the current password (minimum 8 characters, different from the current one and
  from the email). Other open sessions aren't closed.
- The photo is stored in the database as an image (JPG, PNG or WebP, < 300 KB). There's no file
  storage or cropping.
- The data policy text itself isn't in the app: only the date it was accepted. Existing demo users
  count as having accepted it on their start date.
- «Coordinador» lists the active Coordinación users: there are no teams per coordinator yet.

Endpoints:
- `GET /api/v1/perfil` · `GET|PUT /api/v1/perfil/foto` (`{foto}`; null removes it) ·
  `POST /api/v1/perfil/password` (`{actual, nueva}`) · `POST /api/v1/perfil/politica`
- `PATCH /api/v1/users/{id}` now also takes `telefono`, `documento` and `fecha_ingreso` (empty clears
  them) · `GET /api/v1/users/{id}/cambios` (the history, Gerencia / Coordinación)

The seed (`seed_perfil`) fills the demo users' teléfono, cédula and fecha de ingreso with the
prototypes' example values.

## Registro de cambios (`/trazabilidad`, G06)

G06 «Registro de cambios» (the decisions renamed «Trazabilidad») and G06-coord: who did what, when,
and how it was before and after. It can't be edited or deleted. Rules are in
`backend/app/services/trazabilidad.py`.

**It stores nothing new.** It reads the histories each module already keeps and the records that
already say who did something and when, and shows them as one list, newest first:
| Module (chip) | Read from |
|---------------|-----------|
| Leads · Citas · Seguimientos | `lead_eventos` (cita events → «Citas», seguimientos → «Seguimientos») |
| Captaciones · Pedidos · Inmuebles · Administración | `captacion_eventos` · `pedido_eventos` · `inmueble_eventos` · `admin_eventos` |
| Indicadores | `rendimiento_cambios` (pesos, metas, calificaciones) |
| Usuarios | `actividad_eventos` (activities on/off) and `user_cambios` (name, cargo, status, personal data, photo, password) |
| Ausencias | `novedades` (registered by / annulled by) |
| Preoperacional | `preoperacionales` reviewed (who and when) |
| GPS | `movimiento_eventos` (state before → after, location views, config, downloads) |
| Plataformas | `plataforma_eventos` and `plataforma_actualizaciones` |
| Agenda | `agenda_items` (added / assigned, answered, deleted) |
| Avisos | `comunicados` sent |
| Comisiones · Bonos · Pagos · Salarios · Negocios | `compensacion_eventos` (by entity) |
| Integraciones | `integracion_eventos` (data saved, tests, disconnections, settings) |
| Pólizas | `poliza_eventos` (studies, decisions, signatures, activations, insurers and deadlines) |
| Rutas | `ruta_eventos` (assigned, accepted / rejected, adjusted, cancelled, rated, arrivals) |
| Asistencia | `asistencia_eventos` (entradas, salidas, reviews, sedes, assigned locations); the schedule and rules are under Configuración |
| Configuración | `configuracion_eventos` (and this page's downloads) |

Each row has Fecha, Hora, Usuario («Sistema» when nobody did it), Módulo, Acción, Registro (code or
person, linked to its page) and Antes / Después (where the history keeps them; otherwise the detail).

**Who**: Gerencia sees everything. Coordinación sees the operation of its team: it doesn't see
Comisiones, Bonos, Pagos, Salarios, Negocios, Integraciones, Pólizas or Configuración (G06-coord; asking for them returns
403). The Auxiliar and everyone else have no access (no prototype gives it to them).

**Filters** (as G06): module chips, user, Desde / Hasta (last 7 days by default, at most a year),
search by code or text (LD-, CIT-, NEG-, MOV-… or a name). 50 rows at a time with «Ver más».
«Descargar (Excel)» gives a CSV with the current filters (up to 10.000 rows), and the download is
logged (`configuracion_eventos`, section `registro_cambios`).

**Navigation**: «Registro de cambios» in CONTROL Y AJUSTES (Coordinación and Gerencia), and a card in
Configuración. G06's «Reportes e historial» doesn't exist yet, so the top button goes to Configuración.

**Simplifications**:
- Only what the modules already log is shown. Some actions don't leave a trace yet: creating a user,
  changing a cita outside its lead's history, attending an aviso, deleting is mostly soft. The
  prototype's «Permisos» chip isn't there: there are no per-cargo permissions to change.
- Before / after come from each history as it was stored. Some keep only a text (the detail), and
  compensación and configuración keep field names («iva pct: 19.0 → 18.0»).
- The list is merged in memory, up to 3.000 rows per source in the range. That's enough for the
  demo and a few months of real use; a large volume will need a database view or a shared table.
- How long the records are kept: PENDIENTE DE CONFIGURACIÓN, as in G06.

Endpoints (`/api/v1/registro-cambios`):
- `GET /opciones` (modules this person can see, users, default range, scope note)
- `GET ?desde=&hasta=&modulo=&usuario_id=&q=&offset=&limit=` (`items`, `total`)
- `GET /export.csv` (same filters)

## Integraciones (`/integraciones`, G07)

G07 «Integraciones» (decision G-019): what each platform produces (leads, costs, cost per lead,
closed deals) and the data to connect it. **Only Gerencia** sees and manages it (403 for everyone
else); it's in CONTROL Y AJUSTES and has a card in Configuración. Rules are in
`backend/app/services/integraciones.py`.

**Catalog** (as G07, created automatically on first use): Plataformas tradicionales (Ciencuadras,
Espacio Urbano, Proppi, Finca Raíz, Metrocuadrado), Redes sociales (Facebook, Instagram, TikTok),
Canales y servicios (Correo de avisos de portales, WhatsApp Business, Google Maps, Google Calendar /
Outlook, Firma electrónica). Each one stores its state, how its data arrives, a monthly cost, the
connection data and «Avisar a Gerencia si la conexión falla» (`integraciones`); every action is an
`integracion_eventos` row, shown in its history and in «Registro de cambios».

**Resultados (real data)**: for lead sources, leads, costos, costo por lead, cerrados (arriendos ·
ventas), conversión, costo por negocio cerrado, en proceso and último lead come from the leads whose
`fuente` is that platform, in the Desde / Hasta range (last 90 days by default). Cost: portals use
their plans in «Plataformas tradicionales» (one source of truth); social networks and services use
the monthly cost registered here, spread over the days of the range up to today. The 4 KPIs add up
all platforms. Services show their cost and a usage figure: WhatsApp counts the messages sent by
WhatsApp recorded in the leads; the others show «—» until they exist.

**Conexión (no real connectors)**: the app can't talk to any external platform yet, so:
- «Guardar y conectar» saves the data and leaves the integration **«Por confirmar conexión»**,
  never «Conectado» (no integration can reach that state today).
- «Probar conexión» answers honestly «Todavía no hay conector para X» and logs the test.
- **Secrets are not stored.** Fields marked as keys keep only a hint («••••1234») to show they were
  typed; the value itself is discarded and never returned. Leaving a key empty keeps the hint.
  When connectors exist, the keys will need encrypted storage and re-entry.
- «Desconectar» (with confirmation) clears the connection data; results already received stay.
- Google Calendar / Outlook asks for nothing here: each person would authorize it from Mi agenda.

**+ Agregar integración**: name, group, how the data arrives, user/code and monthly cost; it starts
«Por confirmar conexión».

**Simplifications**:
- A new platform added here has no leads: lead sources are the `fuente_lead` enum, so a new source
  needs a code change. It also doesn't appear in «Actualización de plataformas» (same reason).
- «Avisar a Gerencia si la conexión falla» is saved but never fires: without connectors, nothing fails.
- «Último dato» is the last lead from that source, not the last sync.
- Costs of Facebook, Instagram, TikTok and Maps in the seed are G07's example quarter figures ÷ 3.
  The real cost origin is PENDIENTE DE CONFIGURACIÓN, as in G07.

Endpoints (`/api/v1/integraciones`):
- `GET ?desde=&hasta=` (KPIs, groups with each item's summary and state)
- `POST` (add) · `GET /{id}` (results, connection, history) · `PATCH /{id}` (cost, how, alert)
- `PUT /{id}/datos` (save connection data) · `POST /{id}/probar` · `POST /{id}/desconectar`

## Pólizas (`/polizas`, X11)

X11 «Pólizas» (decisions G-087, G-075, G-072, G-084, G-034, F-020): rental policies, separate from
«Negocios». **The Auxiliar administrativa and Gerencia** see and manage it; «Comparar pólizas» is
only for Gerencia; everyone else gets 403. It's in the sidebar (Gerencia: COMERCIAL; Auxiliar:
NEGOCIOS) and has a card in Configuración. Rules are in `backend/app/services/polizas.py`.

**Data**: `aseguradoras` (name, NIT, contact, active, days to activate after the contract signature
and warning days), `poliza_tipos` (each policy an insurer offers: price as % of the rent per month,
study cost, response days, coverages), `polizas` and `poliza_eventos` (every change, with who and
when; shown in «Registro de cambios»). **Only rentals** carry a policy: a policy belongs to a closed
rental deal (`NEG-…`) and/or a rental property; older contracts can use a short description.

**Flow**:
1. «Registrar póliza» (insurer, type, canon, filing number) → **En estudio**.
2. **Aprobada** or **Negada** (with the reason). When approved, the asesor who closed the deal gets
   the G-034 aviso («Se aprobó la póliza del arriendo NEG-…»).
3. A denied study can be retaken **once** with a reason (G-084). If the second study is approved it
   counts as a **póliza recuperada**.
4. «Registrar firma del contrato» starts the insurer's deadline.
5. «Activar póliza» (date and policy number; supporting file marked as present) → **Activa**, in
   «Contratos activos». Activating after the deadline is allowed and logged as «fuera del plazo».
6. **Terminada** when the contract ends. Policies can be edited (canon, filing number, property
   insurance; insurer only while in study) and deleted with a reason, except active ones.

**Tabs** (as X11): Indicadores (active policies, monthly cost = canon × price, insured rent,
activated in the Desde / Hasta range, to activate; table and bars by insurer), Contratos activos,
**En trámite** (added, see below), Alertas de activación, Aseguradoras (list, add with the first
policy, add more policies, deactivate, delete, deleted list, editable deadlines, recent changes) and,
for Gerencia, Comparar pólizas (cards with price, cost for an example rent per month and first year,
study cost and response, approval % of studies decided in the range, active policies, properties
with insurance, insured rent, coverages; filters, sorting, side-by-side for 2 or 3 with the best of
each row in green).

**Alerts** (G-087): approved, signed and not active. «Por vencer» from the warning days, «Vencida»
after the deadline. The Auxiliar gets both in Avisos; Gerencia only the expired ones.

**Insurers**: names can't repeat; one used by any policy can't be deleted, only deactivated (G-087's
proposed rule); a deleted one keeps who deleted it and when.

**Seed**: the prototype's Entidad 1 / 2 / 3 (ejemplo) with 70 / 45 / 60 days and their five
policies; the nine closed rental deals in every state (one expired and one about to expire, a denied
one, a second study, two active…) and 12 older active contracts. DATOS DE EJEMPLO.

**Simplifications**:
- Studies are registered and decided in the **«En trámite»** tab here, not on the deal's page:
  «Negocios» shows each rental's policy state and links to this page (G-087 keeps them separate).
- The 2 points per recovered policy (G-084) aren't added: the Auxiliar has no result in
  rendimiento yet. Recovered policies are recorded and counted in Indicadores.
- **Reclamaciones** aren't recorded, so the comparator shows «No se registran todavía».
- «Inmuebles con seguro» counts active policies marked «incluye seguro del inmueble»; the property
  insurance isn't a separate record.
- The supporting file isn't uploaded: there's no file storage yet, only a «hay soporte» flag.
- How often the reminder repeats is PENDIENTE DE CONFIGURACIÓN, as in X11: the aviso stays open until
  the policy is activated, and a new one appears when it expires.
- The policy cost isn't deducted from each deal's ganancia (F-020): deal ganancia is still entered
  by hand in Compensación.

Endpoints (`/api/v1/polizas`):
- `GET ?desde=&hasta=&aseguradora_id=` (KPIs, by insurer, active contracts, alerts, in progress)
- `GET /opciones` (rental deals without a policy, rental properties, active insurers and types)
- `GET /comparar?desde=&hasta=` (Gerencia)
- `POST` · `GET /{id}` · `PATCH /{id}` · `POST /{id}/decidir` · `/retomar` · `/firma` · `/activar`
  · `/terminar` · `/eliminar`
- `GET /aseguradoras` · `POST /aseguradoras` · `PATCH /aseguradoras/{id}` ·
  `POST /aseguradoras/{id}/tipos` · `DELETE /aseguradoras/{id}`

## Rutas (`/rutas`, X08 · M04 · G-083)

Field routes for asesores with Captación (G-002: route and GPS depend on Captación). One page with two
views. Rules are in `backend/app/services/rutas.py`.

**Data**: `rutas` (asesor, from / to, weekdays Mon–Sat, observation, origin manual / excel, state,
rejection reason, rating), `ruta_zonas` (1 to 3 per route: zone, hours, weekdays), `ruta_llegadas`
(arrival at a zone on a day) and `ruta_eventos` (history, in «Registro de cambios»). Zones are the
same list as pedidos.

**«Rutas y ubicación del equipo»** (X08):
- **Coordinación** programs the routes in three tabs:
  - **Asignar una por una**: asesor (only with Captación), period (day, week, month or range),
    weekdays, and 1 to 3 zones with their hours and days.
  - **Subir plantilla de Excel**: download the template, upload it, review row by row (rows with
    errors aren't assigned) and assign the correct ones.
  - **Rutas asignadas**: filters by dates, asesor and state; 5 at a time with «Ver más»; rejected
    ones show the reason and can be adjusted and sent again (the old one is cancelled); pending and
    accepted ones can be cancelled.
- Validation (G-083):
  - dates in order and not already over;
  - at least one day, and zone days within the route days;
  - end hour after start;
  - no repeated zone, no overlapping hours the same day;
  - no other pending or accepted route for that asesor in those dates (also between rows of one file).
- **Gerencia** and the **Auxiliar** only consult (same filters). Gerencia rates accepted routes 1 to
  5 (G-051).
- «Ubicación y ruta de cada persona» shows where each person checks in today: «En ruta · zones» when
  their accepted route has zones today, otherwise the main office. The Auxiliar and Gerencia can
  download it.

**«Mi ruta de hoy»** (M04, asesores with Captación; sidebar MI DÍA and bottom bar):
- Routes to answer: accept, or reject with a reason and an explanation (both required).
- The accepted routes, then a schematic map and today's timeline: route zones (with their arrival),
  citas and pedido deadlines from the agenda.
- «Marcar llegada al siguiente punto» records the arrival at the next zone, once per zone and day.

**Wired into**:
- **Avisos**: «Nueva ruta asignada» (asesor), «Ruta rechazada» (Coordinación, closes when adjusted
  or cancelled), plus informative «Ruta aceptada» (Coordinación) and «Ruta cancelada» (asesor).
- **Agenda**: accepted route zones appear in the asesor's agenda (green, «Ruta del coordinador»).
- **Rendimiento**: the Coordinador's «Rutas del equipo» area is the average of Gerencia's ratings of
  the routes they created that overlap the month (4 of 5 = 80 %); before, it had no data.
- **Registro de cambios**: «Rutas» module (Coordinación and Gerencia).

**Seed**: Asesor Demo has an accepted route this week (today's first arrival marked), a pending one
for next week (from the template) and last week's, rated 5. Bruno has the whole month accepted with
3 zones (rated 4) and a rejected one. DATOS DE EJEMPLO.

**Simplifications**:
- The «Excel» template is a **CSV** (`;`-separated) that Excel opens and saves; real `.xlsx` files
  aren't read yet.
- The map is a schematic drawing (as in M04), not a real map: there's no map provider yet
  (Integraciones: Google Maps «Sin conectar»).
- Arrivals are marked by hand; they aren't checked against the GPS position, and GPS alerts
  («salida de ruta») still come from Movimientos y GPS, not from the zones.
- Sedes, schedules and check-in radius are in Asistencia («Sedes y horario»). The location table
  here stays read-only and comes from the accepted routes.
- The real zone list and rejection reasons are PENDIENTE DE CONFIGURACIÓN (example values).
- Coordinación can also cancel an accepted route that hasn't ended (G-083 only mentions pending
  ones), so plans can change mid-period.

Endpoints (`/api/v1/rutas`):
- `GET /opciones` · `GET /mi-ruta` · `POST /llegada`
- `GET ?desde=&hasta=&asesor_id=&estado=` · `GET /ubicaciones` · `GET /{id}`
- `POST` (with `reemplaza_id` to adjust a rejected one) · `POST /{id}/cancelar` ·
  `POST /{id}/responder` · `POST /{id}/calificar`
- `GET /plantilla.csv` · `POST /importar` (`confirmar: false` reviews, `true` assigns)

## Asistencia (`/asistencia`, Z04 · K17 · X08)

Clock-in and clock-out (decisions G-048 … G-051). Rules are in `backend/app/services/asistencia.py`.
One page, three tabs:
- **Mi asistencia** (Z04), for whoever marks.
- **Asistencia y ausencias** (K17), for Coordinación, the Auxiliar and Gerencia.
- **Sedes y horario** (X08 part), edited by the Auxiliar and Gerencia.

Sidebar: «Marcar entrada y salida» in MI DÍA (everyone but Gerencia; «Entrada» in the bottom bar),
«Asistencia y ausencias» in EQUIPO / PERSONAL. «Ausencias y permisos» links back to it.

**Data**: `sedes` (name, address, coordinates, radius 50/100/200 m, main one), `ubicaciones_asignadas`
(each person's sede, who changed it and when), `marcaciones` (one per person and day: entrada and
salida with location, state, minutes and reviews) and `asistencia_eventos` (Registro de cambios). The
schedule and rules live in Configuración's store (section «asistencia»).

**Who marks**: asesores, Atención, the Coordinador and the Auxiliar (switch per cargo; Gerencia off,
G-050).

**Marcar entrada** (one button, G-049):
- The browser's location is checked against the assigned place:
  - the person's sede (default the main one; Coordinación changes asesores' and Atención's, the
    Auxiliar and Gerencia anyone's);
  - for asesores with an **accepted route** that has zones today, the zone of that time (Rutas).
- The **preoperacional comes first** for those who do it (switchable).
- Up to 30 min after 8:00 (15/30/45/60). Late 1–10 min = leve, more = grave; both are
  impuntualidad.
- Outside the place, or with no location, a window asks «Cambio solicitado» / «Imprevisto» plus a
  justification. Coordinación reviews it; the Coordinador's and the Auxiliar's go to Gerencia.
  - Accepted: the marked hour counts.
  - Rejected: the person gets «Marca entrada cuando estés en la sede o ubicación asignada» and can
    mark again. Until they do it's impuntualidad, all day if they never do.

**Marcar salida**:
- Before the hour needs «Imprevisto» / «Permiso personal autorizado», reviewed by Coordinación or the
  Auxiliar; rejected = the time not worked is discounted.
- 15+ min after the hour = horas extra, accepted by Coordinación **and** the Auxiliar (both answer).
- «Recuerda marcar salida» shows from 5 min before.

**Asistencia y ausencias** (K17): today's KPIs (marked / total, pending, leves · graves and minutes
in the range, accepted horas extra), «Por aprobar» with the actions each role can take, today's
table (absences registered in Ausencias y permisos show as «Ausencia») and the range's records.
The Auxiliar and Gerencia download the CSV.

**Wired into**:
- **Salarios**: unconfirmed pay periods discount impuntualidad and rejected early exits by the minute
  (monthly salary ÷ 30 ÷ 8 h) and list accepted horas extra.
- **Mis resultados**: the Puntualidad rating is now automatic (days on time ÷ days marked, on the
  preoperacional's 1–5 scale) and a 2 or 1 takes off 5 points, as G-051 says.
- **Avisos**: items to review for each reviewer; «Marca entrada cuando estés…» for a rejected entrada.
- **Rutas**: the location table uses each person's sede.

**Seed**: main sede (Guayabal) and «Punto de atención Envigado»; two weeks of entradas and salidas
with the prototype's cases (leve, grave, outside accepted, rejected, horas extra accepted, early exit
accepted). Today: most marked, Pre-ventas outside pending, Carla not marked; yesterday, Diego's horas
extra and Bruno's early exit pending. DATOS DE EJEMPLO.

**Simplifications**:
- No map provider: a sede's coordinates are taken on site («Tomar mi ubicación») or typed. Route zones
  use example centers with a configurable radius (2 km). «Otra zona» can't be checked.
- With no sede registered, nobody's location can be checked, so marks are accepted «sin verificar».
- Past the limit, a normal entrada can't be marked; the day stays «Sin marcar · impuntualidad» for
  Coordinación to handle (absences go in Ausencias y permisos). Days without marking aren't
  discounted by themselves.
- The value of horas extra and surcharges is PENDIENTE (contador): they're listed, not paid. The
  per-minute discount uses 8 hours a day until the contador confirms it.
- The reminder is shown on the page (no push notification).
- The Coordinador's dashboard and the Inicio pages don't show «Marcar entrada» yet; it's in the menu.

Endpoints (`/api/v1/asistencia`):
- `GET /mia` · `POST /entrada` · `POST /salida` (`{lat, lng, motivo?, texto?}`; without a needed
  justification they answer `requiere_justificacion` and save nothing)
- `GET /equipo?desde=&hasta=` · `POST /{id}/revisar` (`que`: entrada · salida · extra) ·
  `GET /export.csv`
- `GET /config` · `PUT /config` · `POST /sedes` · `PATCH /sedes/{id}` · `PUT /ubicacion/{user_id}`

## Negocios (`/negocios`, X02 · M16)

X02 «Negocios» and M16 «Detalle del negocio» (decisions G-029, G-031, G-033, G-034, G-055, G-059,
G-060, G-087, G-091). Rules are in `backend/app/services/negocios.py`.

**The record.** A negocio is the `Cierre` (`NEG-0140…`) that Compensación already creates for each lead
marked «Ganado». The module adds the deal's data to that same row (property, canon or price, last offer,
where the documents are, contract attached, notary appointment) and its signature flow. Money received
on sales goes in `negocio_abonos`. Every change is a `compensacion_eventos` row (entidad `cierre`), shown
in the deal's history and in «Registro de cambios» (module «Negocios», now linking to `/negocios`).

**Who.**
- **Auxiliar administrativa**: manages everything (sidebar: NEGOCIOS › Negocios).
- **Gerencia**: sees everything and can edit the deal's data (value, % of the sale, documents), but
  doesn't confirm signatures: that's the Auxiliar's job (G-029), as in the prototype (sidebar: COMERCIAL).
- **Coordinación**: sees all deals read-only, without money (no ganancia, no amounts received), as with
  the rest of the pay data (sidebar: COMERCIAL).
- **Asesores**: «Mis negocios», only the deals they close (M16).
- Everyone else gets 403.

**Flow.**
1. **Stages** (example ones, PENDIENTE DE CONFIGURACIÓN). Arriendo: Estudio del arrendatario → Contrato en
   firma → Contrato firmado. Venta: Oferta presentada → Promesa firmada → Escrituración → Escriturada.
   The asesor (or the Auxiliar) «Pasar etapa» with an observation and, optionally, the offer or negotiated
   condition (G-059); staying on the same stage records a new offer. Moving a sale to Escrituración needs
   the notary appointment (date, time, notaría), which sends a reminder 2 days before (G-031).
2. **«Solicitar cierre»** (asesor): «¿El cliente ya firmó?». The Auxiliar gets an aviso and the deal shows
   in «Firmas por confirmar».
3. The Auxiliar **confirms the signature** (date, contract optional, observation) or **returns it** with a
   reason (the asesor gets an aviso). Rentals have one signature; sales two (G-033): the promesa first,
   then the escritura. The last one gives **«negocio cerrado»**: the final stage, the ganancia efectiva is
   sent to Compensación (which generates the commissions, G-029), the asesor gets an aviso, and for a
   rental with an approved policy the contract signature is recorded in «Pólizas» (the insurer's
   deadline to activate starts). The Auxiliar can also confirm a deal that has no asesor.
4. **Negocio caído** (G-055): the asesor reports it with a reason (the Auxiliar gets an aviso) and the
   Auxiliar confirms it, or keeps the deal going («Seguir con el negocio»); the Auxiliar can also confirm
   one directly. «Póliza negada» is a reason only for rentals (G-060). A confirmed caída cancels the
   deal's unpaid commissions, no longer counts in Rendimiento, and the asesor and Gerencia get an aviso.
   The lead stays «Ganado», and Compensación's sync no longer reopens such a deal.
5. **Money received** on sales (G-033): value, date, moment (promesa, escritura, other), supporting file.

**Ganancia** (G-087), from «Tarifas de intermediación» in Configuración:
- Arriendo: charged once = canon × 20 % + IVA + papelería $75.000 (IVA included). Minus the IVA
  collected, the team's commissions, one month of the policy (canon × the policy's price; months
  PENDIENTE) and the referral (10 % of the canon).
- Venta: price × % (per deal, default from Configuración) + IVA, minus the IVA and the commissions.
- The *ganancia efectiva* sent to Compensación is the charge without IVA, minus referrals.
- Until a deal is closed, commissions are estimated with Compensación's percentages («proyectada»).
  A deal that loses money shows the red alert.
- IVA of the canon (commercial use) and retención (tenant is a company) are shown apart: they aren't
  the company's money.

**Page.** Tabs Firmas por confirmar · En proceso · Cerrados · Caídos. «Indicadores de negocios» (G-091):
Desde/Hasta and Tipo; Total, En negociación, Por cerrar, Cerrados, Caídos (+ reported) and Ganancia
(closed + projected); a tap on a figure filters the list. Bars by type and «Ganancia de cada negocio».
Each deal card has stage, closing request, signatures, policy (rentals) or money received (sales),
documents, the ganancia breakdown, policy activation (closed rentals, linking to «Pólizas»), the actions
and the history. Asesores get the M16 layout: data, stage stepper, «Pasar etapa», «Negocio caído»,
notary appointment, history and «Solicitar cierre».

| Endpoint | Notes |
|----------|-------|
| `GET /negocios?desde=&hasta=&tipo=` | Board (asesor: their deals). Default: from the 1st of the month 3 months back to today |
| `GET /negocios/{id}` · `PATCH /negocios/{id}` | Detail with history · deal data (Auxiliar, Gerencia) |
| `POST /negocios/{id}/etapa` | `{etapa?, oferta?, observacion, notaria?, notaria_at?}` (asesor of the deal, Auxiliar) |
| `POST /negocios/{id}/solicitar` | `{nota?}` (asesor of the deal) |
| `POST /negocios/{id}/confirmar` · `/devolver` | `{fecha, contrato_adjunto, observacion?}` · `{motivo}` (Auxiliar) |
| `POST /negocios/{id}/caida` · `/caida/descartar` | `{motivo, observacion}`: the asesor reports, the Auxiliar confirms |
| `POST /negocios/{id}/abonos` | `{valor, fecha, momento, soporte}` (Auxiliar, sales) |

**Migration.** Deals from before this module that already had a ganancia count as signed on the day the
lead was won; the rest start «en proceso» on the first stage.

**Demo data.** `seed_negocios` gives every deal a value (before Compensación registers the ganancia, so
commissions follow the tariffs), links rentals to their policy's property, closes the deals that have a
ganancia and the platform leads won without an asesor, and adds deals in every state: a contract and a
promesa to confirm, a request returned to the asesor, a sale in escrituración with money received and
the notary in two days, a caída reported by the asesor and one confirmed. Log in as `auxiliar@`,
`gerencia@`, `coordinacion@`, `diego@`, `carla@` or `asesor@`. On a database seeded before this module,
deal values are worked out backwards from the ganancia already registered; for the realistic values,
reset the database and seed again.

**Simplifications** (to revisit):
- Deals still start when a lead is marked «Ganado» (by managers). G-055's «Ganado set by the system when
  the Auxiliar confirms» would mean creating deals before the lead is won; not done.
- Rendimiento still counts a deal when the lead is won, not at the promesa (sales) or the signature.
- No partial commissions per payment received on a sale (percentages PENDIENTE): commissions are
  generated at «negocio cerrado».
- «Subir contrato» and supporting files are marked as present; no file storage yet.
- «Seguimiento del cliente» and «Documentación OK / Observaciones de documentos» from M16 aren't built;
  follow-ups stay in the lead and the agenda.
- No «negocios pendientes» on the asesor's home, and no «negocios con pérdida» on the Auxiliar's home yet.
- The deal's «Activar póliza» stays in «Pólizas» (G-087 separated them); the card links there.

## Descargas del personal (`/descargas`, X10)

X10 «Descargas del personal». Rules are in `backend/app/services/descargas.py`.

**Who.** The Auxiliar administrativa (X10 is in her PERSONAL menu) and Gerencia download everyone.
Coordinación downloads its team, with the same rule as each module (preoperacionales of asesores,
Atención y Preventa and the Auxiliar; asistencia and pausas activas of asesores and Atención;
ausencias of everyone but Gerencia), never its own, and not capacitaciones (G-047). Everyone else gets 403. Sidebar: PERSONAL (Auxiliar), EQUIPO (Gerencia,
Coordinación).

**Page** (as X10): tabs per file; «Todo el personal (grupal)», «Por cargo» or «Por empleado»;
Desde / Hasta (at most a year; this month by default); Formato; «El archivo trae: …»; «Se descargará: …»
with the real number of rows; «Descargar»; «Descargas recientes» (the person's last 6).

**Files** (CSV with `;` and a BOM, which Excel opens with accents, like the other exports). Named
`CDC_<Tipo>_<Quién>_<desde>_a_<hasta>.csv` (accents dropped from the name).

| Tab | One row per | Columns |
|-----|-------------|---------|
| Preoperacionales | person and business day that counts | estado (Realizado / No realizado), hora, medio, placa, respuestas SÍ/NO, the NO questions, novedad, observaciones, revisada por and when, the month's score and % (same rules as «Mi preoperacional») |
| Asistencia | person and day with a marcación | as K17's «Descargar Excel»: ubicación asignada, dónde marcó, entrada y estado, minutos tarde, leve o grave, salida y estado, minutos que se descuentan, horas extra aceptadas, observación |
| Ausencias y permisos | absence that touches the period | NOV-number, tipo, desde, hasta, days within the period, observación, soportes, registered by and when, estado, cancelled by and reason |
| Pausas activas | person, working day and pause that already closed | persona, cargo, fecha, pausa (mañana / tarde), hora programada, estado (Realizada / No realizada / Ausencia), hora en que marcó «Realizada», the person's compliance in the period (%) |
| Capacitaciones | person and training in the period | CAP-number, fecha, hora, tema, área, presentó, lugar, origen (programada por… / registrada por…), estado, respuesta, participó, motivo, qué aprendió, observaciones |

Cargo groups are X10's: Asesores, Atención y Preventa (the Atención cargo and Pre-ventas), Coordinación,
Administrativa, Gerencia.

Every download is logged in `configuracion_eventos` (section `descargas`) and shows in «Registro de
cambios» as module **Descargas** (Gerencia and Coordinación).

| Endpoint | Notes |
|----------|-------|
| `GET /descargas` | Tabs (with the groups you can download), people, groups, your recent downloads |
| `GET /descargas/{pre\|asi\|aus\|pau\|cap}/vista-previa?desde=&hasta=&alcance=tod\|car\|emp&grupo=&user_id=` | Rows, text and file name |
| `GET /descargas/{pre\|asi\|aus\|pau\|cap}.csv?…` | The file (same filters) |

**Simplifications**:
- «PDF (con resumen)» is listed as pending; only Excel (CSV).
- The other modules keep their own downloads (preoperacional by month, asistencia, rendimiento,
  comisiones, movimientos, plataformas, registro de cambios); this page doesn't repeat them.

## Capacitaciones (`/capacitaciones`, Z03 · X07)

Z03 «Mis capacitaciones» and X07 «Capacitaciones del equipo» (decisions G-046 and G-047). Rules are in
`backend/app/services/capacitaciones.py`.

**Data.** `capacitaciones` (CAP-001…: origen *programada* or *registrada*, tema, área, quién presenta,
lugar o enlace, date and time, estado *programada* → *realizada* or *cancelada*, who it's for),
`capacitacion_participantes` (one row per person: respuesta *pendiente / acepta / no* with the reason,
whether they attended, what they learned, observations) and `capacitacion_eventos` (every change, shown
in «Registro de cambios» as module **Capacitaciones**).

**Who.**
- **Everyone** has «Mis capacitaciones» (sidebar, above «Mi perfil»).
- **The Auxiliar, Coordinación and Gerencia** also have «Capacitaciones del equipo» (`?tab=equipo`;
  sidebar: PERSONAL for the Auxiliar, EQUIPO for Coordinación and Gerencia).
- **Only the Auxiliar and Gerencia** download the Excel (G-047).

**Flow.**
1. **Programar** (X07): date, time, área, tema, who presents, place or link, and who takes part: the
   whole team, Comercial (asesores), Atención y Preventa, Administrativa (the Auxiliar) or specific
   people. Everyone active except Gerencia can take part. Each participant gets an aviso, and the
   training appears in their agenda (new «Capacitación» colour). Their history shows «Programada por
   Gerencia / Coordinación / la Auxiliar administrativa».
2. **Responder** (Z03): «Aceptar participación», or «No podré participar» with a reason (cita con
   cliente, incapacidad o permiso, vacaciones, otro motivo, which asks for the detail). The answer can
   change until the training is closed. Declined trainings leave the person's agenda.
3. **Marcar asistencia**: once the start time has passed, an organizer marks who attended (those who
   accepted come checked). The training becomes «realizada». The person who programmed it gets an aviso
   until it's done. A programmed training can be cancelled with a reason.
4. **Registrar participación** (Z03): anyone records a training they took on their own (date, time,
   área, tema, who presented, what they learned, observations). The Auxiliar and Gerencia get an aviso
   in the daily summary.
5. **Qué aprendí**: after attending a programmed training, the person can add what they learned from
   their history.

**Team view (X07).** Desde/Hasta (this month by default). KPIs: programadas, por responder, registradas
por el equipo, no participaron (and how many with a reason). Each programmed training shows how many
accepted (or attended), haven't answered or won't take part, with each person's answer and reason. There's
also the list of trainings the team registered, and «Descargar Excel» (the Descargas file for the
period).

| Endpoint | Notes |
|----------|-------|
| `GET /capacitaciones/mias` | Z03: to answer, history, áreas, motivos |
| `GET /capacitaciones/equipo?desde=&hasta=` | X07 (Auxiliar, Coordinación, Gerencia) |
| `POST /capacitaciones` | Programar `{fecha, hora, area, tema, presenta, lugar?, participantes: todo\|com\|ate\|adm\|per, personas?}` |
| `POST /capacitaciones/registrar` | `{fecha, hora, area, tema, presenta, aprendio, observaciones?}` |
| `POST /capacitaciones/{id}/responder` | `{acepta, motivo?, detalle?}` (participants) |
| `POST /capacitaciones/{id}/completar` | `{asistentes: [user_id]}` (organizers, after it started) |
| `POST /capacitaciones/{id}/cancelar` · `/aprendizaje` | `{motivo}` · `{aprendio, observaciones?}` |

**Demo data** (`seed_capacitaciones`, relative to today): the prototype's trainings.
- Three upcoming ones, programmed by Gerencia, Coordinación and the Auxiliar, with a mix of answers.
- One already held, with its attendance marked and one absence with a reason.
- One held yesterday, still waiting for its attendance.
- Four the team registered themselves.

**Simplifications**:
- Organizers program and see the whole team (everyone but Gerencia). Coordinación isn't limited to its
  own team, as X07-coord shows the same list.
- The notification is an aviso in the bell and the agenda item; there's no e-mail or reminder before
  the training.
- No attachments (certificates), evaluation or attendance list signature; no editing a programmed
  training (cancel and program it again).
- «Permisos (24 módulos)» and «Historial y reportes» from G-046 don't exist in the app.
- The prototype's Excel and PDF become the CSV of «Descargas del personal».

## Pausas activas (`/pausas-activas`, G11)

G11 «Pausas activas» and the reminder in each Inicio (decisions G-041, G-045, G-060, G-065). Rules are
in `backend/app/services/pausas.py`.

**The rule.** Two pauses a day (mañana and tarde) for every cargo, Gerencia included, on working days
(Monday to Friday) from the day the person started. Example schedule: 10:00 a. m. and 3:00 p. m., with
the reminder on screen for 15 minutes (PENDIENTE DE CONFIGURACIÓN). It doesn't count in the indicators
(G-045): it's a compliance record.

**The reminder.** During the window, each person's Inicio shows «Es hora de tu pausa activa de la
mañana / tarde», the message and «Realizada». The Inicio pages are the general home, the asesor's home,
and Coordinación's and Gerencia's dashboard. Tapping it records the person, date, pause, scheduled time
and the time they marked it, and the reminder goes away. Outside the window there's nothing to mark.
Once the window has passed without it, that pause is «No realizada». A day with a registered absence
(«Ausencias y permisos») shows «Ausencia» and doesn't count.

**Who.**
- **Everyone:** «Mis pausas activas» (sidebar, MI DÍA): compliance, done and missed in a Desde/Hasta
  range, and the day-by-day list. The reminder can also be marked there.
- **Auxiliar administrativa:** sets the schedule (both times on the 15-minute clock, mañana before
  12:00 and tarde after, 5–60 minutes on screen).
- **Auxiliar and Gerencia:** edit the message (it can't be empty).
- **Gerencia:** consults and downloads, but doesn't change the schedule (G-045).
- **Coordinación:** sees its team (asesores and Atención y Preventa), read-only.
- **Team view** (`?tab=equipo`; sidebar: PERSONAL › «Pausas activas (horario)» for the Auxiliar, EQUIPO for
  Coordinación and Gerencia), as G11:
  - The schedule card.
  - KPIs: mañana and tarde today (done / total and who's missing), compliance in the period, missed in
    the period.
  - Today's record.
  - With a person chosen, their pauses day by day.
  - «Descargar Excel» (the Descargas file).

Schedule and message changes go to «Registro de cambios» (module **Pausas activas**). They're stored in
`configuracion_eventos`, section `pausas_activas`.

**Data.** `pausas_config` (one row: both times, minutes on screen, message) and `pausas_activas` (one row
per pause marked «Realizada», with the time scheduled that day). Missed pauses aren't stored: they're
worked out from the schedule.

| Endpoint | Notes |
|----------|-------|
| `GET /pausas-activas/ahora` | The reminder on screen now (if any) and today's two pauses |
| `POST /pausas-activas/realizada` | Mark the pause on screen (409 outside the window or if already marked) |
| `GET /pausas-activas/mias?desde=&hasta=` | Own compliance and days (this month by default) |
| `GET /pausas-activas/equipo?desde=&hasta=&user_id=` | Team view (Auxiliar, Coordinación, Gerencia) |
| `PUT /pausas-activas/horario` · `PUT /pausas-activas/mensaje` | `{hora_manana, hora_tarde, minutos}` (Auxiliar) · `{mensaje}` (Auxiliar, Gerencia) |

**Demo data** (`seed_pausas`): the example schedule and six weeks of pauses for every active person,
most marked a few minutes after the time and a few missed, up to the pauses that have already closed
today.

**Simplifications:**
- Working days are Monday to Friday for everyone; Asistencia's schedule per sede isn't used.
- Missed pauses use today's schedule, so changing the times also changes the times shown for past
  missed pauses (marked ones keep theirs).
- The reminder refreshes every minute while the Inicio is open; there's no push notification. It isn't
  in the mobile bottom bar, which is already full. On the phone the Inicio reminder is the way in, as in
  the prototype.
- The prototype's «mostrar el aviso ahora» demo button isn't there.

## Business rules

- **Cargo** defines a person's general profile: Gerencia, Coordinación, Asesor, Auxiliar administrativa, Atención al Cliente.
- **Commercial activities** (Captación, Ventas, Arriendos) are switched on per person and stored in `user_actividades`, which records who granted each one. Coordinación will change them through `services.users.set_actividades`.
- **Atención al Cliente** and **Pre-ventas** are independent functions (`users.funcion`) and can't be combined with commercial activities. This is checked in the service and backed by a database trigger. The Atención al Cliente cargo always has the Atención al Cliente function (a check constraint enforces it).
- **GPS / check-in** applies only when Captación is active (`gps_checkin_enabled` on the user). The Coordinador and Atención y Preventa only have GPS while in the field (see Movimientos y GPS).

## Known simplifications and what production still needs

Each module lists its own simplifications. Across the app:

- **Prototype values.** Percentages, goals, schedules, insurers, tariffs and stages marked
  PENDIENTE DE CONFIGURACIÓN use example values that Gerencia (or the Auxiliar) can edit; the real
  ones still have to be entered.
- **Files.** Nothing is uploaded: supporting documents, contracts, certificates and photos are
  marked «adjunto» or kept as text (profile photos are small data URLs). Production needs object
  storage (e.g. S3) and an upload endpoint.
- **Background jobs.** Nothing runs on its own. Avisos are synced when someone opens the bell,
  reminders show while a page is open, and month-end bonuses are calculated with a button. A
  scheduler (cron, Celery/RQ or a cloud scheduler) is needed for the daily summary at 7:30, escalations,
  notary and agenda reminders, expiring policies and automatic month-end jobs.
- **Notifications.** In-app only (bell, banners). No e-mail, SMS, WhatsApp or push.
- **Integrations.** The Integraciones page stores connection data and costs, but no portal, social
  network, calendar or accounting connector exists. Leads are created by hand or by the seed.
- **GPS and location.** The browser location is recorded when someone marks, but there's no
  geocoding (distance to an address) and no background tracking.
- **Exports.** CSV that Excel opens; no .xlsx or PDF (summaries, certificates).
- **Auth.** Access and refresh tokens are in cookies the page can read; the refresh token should
  become `httpOnly`. People change their password in «Mi perfil», but there's no recovery by e-mail
  (it needs e-mail sending) and no 2FA.
- **Ops.** No production deployment, HTTPS, backups, monitoring or rate limiting yet. The API refuses
  to start outside `local`/`test` without a real `JWT_SECRET`, and the seed refuses to run there.
- **Financial software.** The «Software Financiero» described in the prototype's `PROJECT_STATE.md`
  is a separate phase and isn't started.

## Deployment (later)

Planned target: AWS App Runner or ECS Fargate for the API (`backend/Dockerfile`) and RDS PostgreSQL, plus ElastiCache Redis if needed.
