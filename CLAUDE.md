# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SONAR** — plataforma de monitoreo y análisis de redes sociales. Monitorea entidades (personas, organizaciones) en Reddit, YouTube, RSS, Twitter/X, Instagram y Facebook, aplicando NLP (sentimiento, odio, NER, embeddings) y generando alertas y reportes PDF.

## Architecture

```
sonar/
├── backend/          # FastAPI + Celery
├── frontend/         # React + Vite
└── docker-compose.prod.yml  # Producción (Oracle Cloud)
```

### Backend (`backend/app/`)

- **`main.py`** — FastAPI app; monta todas las rutas bajo `/api/v1`
- **`api/v1/`** — Endpoints REST: `auth`, `users`, `entities`, `mentions`, `alerts`, `platforms`, `dashboard`, `reports`, `chat`, `twitter_feeds`
- **`models/`** — ORM SQLAlchemy 2.0: `entity`, `mention`, `user`, `alert`, `social_platform`, etc.
- **`workers/celery_app.py`** — Definición de todas las tareas programadas (beat schedule)
- **`workers/tasks/`** — Tareas Celery: `scraping.py`, `nlp.py`, `alerts.py`, `analytics.py`
- **`workers/scrapers/`** — Scrapers por red social (twitter, instagram, facebook, reddit, youtube, rss)
- **`core/config.py`** — Settings cargados desde `.env`
- **`database.py`** — SessionLocal factory

### Frontend (`frontend/src/`)

- **`main.jsx`** → **`App.jsx`** — Router con rutas protegidas por rol (`PrivateRoute`, `AdminRoute`, `AnalystRoute`)
- **`pages/`** — Una página por vista; cada página usa React Query para datos
- **`api/client.js`** — Axios con interceptor JWT; proxy a `/api/v1` via Vite en desarrollo
- **`store/authStore.js`** — Zustand: token JWT, usuario, helpers de rol (`isAdmin`, `isAnalyst`)

### Data flow

1. Celery Beat dispara tareas de scraping → scrapers guardan `Mention` en DB
2. Tarea `process-pending-mentions` corre NLP (sentimiento, odio, embeddings) cada 5 min
3. `evaluate-alert-rules` revisa reglas y dispara notificaciones (Telegram/email) cada 5 min
4. Frontend consulta API → React Query cachea y refresca

## Commands

### Desarrollo local

```bash
# Levantar todo (dev)
docker compose up -d

# Ver logs en tiempo real
docker compose logs -f backend
docker compose logs -f worker

# Ejecutar migraciones manualmente
docker compose exec backend alembic upgrade head

# Crear migración nueva
docker compose exec backend alembic revision --autogenerate -m "descripcion"

# Scripts de administración
docker compose exec backend python scripts/create_admin.py
docker compose exec backend python scripts/add_twitter_account.py
```

### Frontend

```bash
cd frontend
npm run dev      # dev server con HMR (puerto 3000)
npm run build    # build de producción
```

### Producción (Oracle Cloud VM)

```bash
# Actualizar solo un servicio tras nuevo push
docker compose -f docker-compose.prod.yml pull frontend
docker compose -f docker-compose.prod.yml up -d frontend

# Actualizar backend + worker + beat
docker compose -f docker-compose.prod.yml pull backend
docker compose -f docker-compose.prod.yml up -d backend worker beat
```

## CI/CD

- **Rama**: `version2` → push dispara `.github/workflows/build.yml`
- Construye y publica imágenes en `ghcr.io/yonatanlop/sonar-backend:latest` y `sonar-frontend:latest`
- En la VM de Oracle se hace `docker compose pull` + `up -d` para aplicar los cambios

## Database migrations

Las migraciones corren automáticamente al iniciar el contenedor `backend` vía `entrypoint.sh`. Están en `backend/alembic/versions/` numeradas secuencialmente (`001_` … `016_`). Al agregar campos a un modelo ORM, siempre crear una nueva migración.

## Roles de usuario

| Rol | Acceso |
|-----|--------|
| `admin` | Todo, incluyendo gestión de usuarios |
| `analyst` | Análisis, reportes, configuración de entidades |
| `viewer` | Solo lectura |

Dependencias de FastAPI: `get_current_user`, `require_admin`, `require_analyst` en `api/deps.py`.

## Environment variables clave

| Variable | Uso |
|----------|-----|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Broker Celery |
| `SECRET_KEY` | Firma JWT |
| `NLP_MODE` | `api` (Groq) o `local` (HuggingFace) |
| `FACE_RECOGNITION_ENABLED` | `false` en producción (ahorra RAM) |
| `TELEGRAM_BOT_TOKEN` | Notificaciones Telegram |
| `YOUTUBE_API_KEY` | Scraping YouTube |
| `IG_ACCOUNT_1_USERNAME/PASSWORD` | Cuenta Instagram para scraping |
| `FB_COOKIES_FILE` | Cookies Facebook para scraping |

## Styling (frontend)

TailwindCSS con clases utilitarias propias definidas en `frontend/src/index.css`:
- `btn-primary`, `btn-secondary` — botones
- `card` — contenedor con sombra
- `input`, `label` — formularios
- `badge` — etiquetas de estado/rol
