# SONAR — Guía de Inicio y Configuración
## Paso a paso para activar el monitoreo de redes sociales

> **Tiempo estimado:** 45–60 minutos para configuración completa
> **Requisito previo:** Docker Desktop instalado y corriendo

---

## ÍNDICE

1. [Arrancar el sistema por primera vez](#1-arrancar-el-sistema-por-primera-vez)
2. [Crear el usuario administrador](#2-crear-el-usuario-administrador)
3. [Configurar Reddit (obligatorio para MVP)](#3-configurar-reddit)
4. [Configurar YouTube](#4-configurar-youtube)
5. [Configurar RSS / Noticias (sin configuración)](#5-configurar-rss--noticias)
6. [Configurar Twitter / X](#6-configurar-twitter--x)
7. [Configurar notificaciones Telegram](#7-configurar-notificaciones-telegram)
8. [Configurar notificaciones Email](#8-configurar-notificaciones-email)
9. [Configurar notificaciones WhatsApp](#9-configurar-notificaciones-whatsapp)
10. [Configurar HuggingFace para NLP](#10-configurar-huggingface-para-nlp)
11. [Crear entidades y palabras clave](#11-crear-entidades-y-palabras-clave)
12. [Verificar que el monitoreo está corriendo](#12-verificar-que-el-monitoreo-está-corriendo)
13. [Resumen rápido de comandos](#13-resumen-rápido-de-comandos)

---

## 1. Arrancar el sistema por primera vez

Abre una terminal en la carpeta `sonar/`:

```bash
cd C:\Users\Anny Vargas\Documents\MIRA\AnalisisRedesSociales\sonar
```

Levanta todos los servicios:

```bash
docker compose up -d
```

Espera 30 segundos mientras la base de datos inicia. Luego verifica que todo esté corriendo:

```bash
docker compose ps
```

Deberías ver 6 servicios con estado `Up` o `running`:

| Servicio | Puerto | Qué hace |
|---|---|---|
| `sonar_db` | 5432 | Base de datos PostgreSQL |
| `sonar_redis` | 6379 | Cola de tareas y caché |
| `sonar_backend` | 8000 | API FastAPI |
| `sonar_worker` | — | Ejecuta los scrapers y NLP |
| `sonar_beat` | — | Programa las tareas automáticas |
| `sonar_frontend` | 3000 | Interfaz web |

Abre el navegador en: **http://localhost:3000**

---

## 2. Crear el usuario administrador

Solo se hace una vez. Corre el script:

```bash
docker compose exec backend python scripts/create_admin.py
```

Credenciales por defecto creadas:
- **Usuario:** `admin`
- **Contraseña:** `sonar2024!`

> ⚠️ **Cambia la contraseña** después del primer login desde **Mi Perfil → Cambiar contraseña**.

Inicia sesión en http://localhost:3000 con esas credenciales.

---

## 3. Configurar Reddit

Reddit es la fuente más robusta: **gratuita, sin límite diario, muy estable.**

### Paso 1 — Crear una aplicación Reddit

1. Ve a https://www.reddit.com/prefs/apps
2. Haz clic en **"Create App"** (o "Create another app")
3. Rellena el formulario:
   - **Name:** `SONAR Monitor` (o el nombre que quieras)
   - **Type:** selecciona **"script"**
   - **Description:** opcional
   - **Redirect URI:** `http://localhost:8080` (no importa para script)
4. Haz clic en **"Create app"**

### Paso 2 — Copiar las credenciales

Después de creada la app verás:
- Debajo del nombre de la app, una cadena corta → ese es el **`CLIENT_ID`**
- El campo **"secret"** → ese es el **`CLIENT_SECRET`**

### Paso 3 — Agregar al .env

Edita el archivo `sonar/.env`:

```env
REDDIT_CLIENT_ID=aqui_tu_client_id
REDDIT_CLIENT_SECRET=aqui_tu_client_secret
REDDIT_USER_AGENT=SONAR Monitor 1.0
```

### Paso 4 — Reiniciar el worker

```bash
docker compose restart worker beat
```

### Verificar

```bash
docker compose exec backend celery -A app.workers.celery_app call app.workers.tasks.scraping.scrape_reddit
```

Deberías ver `"status": "ok"` en la respuesta (puede tardar 10-30 segundos).

---

## 4. Configurar YouTube

YouTube Data API v3: **gratuita con 10,000 unidades/día** (suficiente para monitoreo normal).

### Paso 1 — Crear proyecto en Google Cloud

1. Ve a https://console.cloud.google.com
2. Haz clic en **"Seleccionar proyecto"** → **"Nuevo proyecto"**
   - Nombre: `SONAR Monitor`
3. Haz clic en **"Crear"**

### Paso 2 — Habilitar YouTube Data API v3

1. Ve al menú **"APIs y servicios"** → **"Biblioteca"**
2. Busca `YouTube Data API v3`
3. Haz clic en el resultado → **"Habilitar"**

### Paso 3 — Crear credenciales

1. Ve a **"APIs y servicios"** → **"Credenciales"**
2. Haz clic en **"+ Crear credenciales"** → **"Clave de API"**
3. Copia la clave generada

> Opcional pero recomendado: haz clic en **"Restringir clave"** → en restricciones de API selecciona "YouTube Data API v3". Esto evita uso no autorizado si la clave se expone.

### Paso 4 — Agregar al .env

```env
YOUTUBE_API_KEY=aqui_tu_api_key
```

### Paso 5 — Reiniciar

```bash
docker compose restart worker beat
```

### Verificar

```bash
docker compose exec backend celery -A app.workers.celery_app call app.workers.tasks.scraping.scrape_youtube
```

---

## 5. Configurar RSS / Noticias

**No requiere ninguna configuración.** El scraper de RSS funciona automáticamente desde el primer arranque.

Fuentes incluidas por defecto:

| País | Medios monitoreados |
|---|---|
| 🇨🇴 Colombia | El Tiempo, El Colombiano, Semana, El Espectador, La República |
| 🇲🇽 México | El Universal, Proceso, Animal Político, Milenio |
| 🇦🇷 Argentina | Infobae, La Nación, Clarín |
| 🇻🇪 Venezuela | El Nacional, Efecto Cocuyo |
| 🇨🇱 Chile | La Tercera, El Mercurio |
| 🇵🇪 Perú | El Comercio, La República |
| 🇪🇸 España | El País, El Mundo |
| 🇺🇸 USA (ES) | BBC Mundo, DW Español |

Para agregar más fuentes, edita:
```
sonar/backend/app/workers/scrapers/rss.py  →  diccionario RSS_SOURCES
```

---

## 6. Configurar Twitter / X

Twitter/X **no requiere API key de pago**. Usa `twscrape` con cuentas reales de Twitter.

### Paso 1 — Reconstruir la imagen (instala twscrape)

```bash
docker compose build backend
docker compose up -d
```

### Paso 2 — Preparar cuentas de Twitter

Necesitas **1 cuenta mínimo**, se recomiendan **2 o 3** para mayor estabilidad.

Opciones para obtener cuentas:
- Usa una cuenta personal secundaria (crea una nueva en twitter.com)
- La cuenta no necesita ser verificada
- Evita usar la cuenta principal del organismo

> ⚠️ Importante: Twitter detecta scraping y puede limitar las cuentas. Las cuentas con algo de historial (algunos tweets, algunos días de antigüedad) funcionan mejor que las recién creadas.

### Paso 3 — Agregar la(s) cuenta(s) al pool

```bash
docker compose exec backend python scripts/add_twitter_account.py
```

El script te pedirá interactivamente:
```
Username de Twitter: mi_cuenta_secundaria
Email:               mi@email.com
Contraseña:          **********
```

Repite el comando para cada cuenta adicional.

### Paso 4 — Verificar las cuentas

```bash
docker compose exec backend python scripts/add_twitter_account.py --list
```

Deberías ver algo como:
```
Cuentas en el pool (2 total):
  ✓ Activa — @cuenta1 (email1@gmail.com)
  ✓ Activa — @cuenta2 (email2@gmail.com)
```

### Paso 5 — Probar el scraping

```bash
docker compose exec backend celery -A app.workers.celery_app call app.workers.tasks.scraping.scrape_twitter
```

### Frecuencia automática

El scraper de Twitter corre automáticamente **cada 20 minutos** una vez configurado. Las cuentas se rotan para distribuir los rate limits.

### Si una cuenta queda bloqueada

```bash
# Ver estado de cuentas
docker compose exec backend python scripts/add_twitter_account.py --list

# Agregar una cuenta de reemplazo
docker compose exec backend python scripts/add_twitter_account.py
```

---

## 7. Configurar notificaciones Telegram

Telegram es el canal de notificación más recomendado: **gratis, instantáneo, sin límites**.

### Paso 1 — Crear el bot

1. Abre Telegram y busca **@BotFather**
2. Escribe `/newbot`
3. Ponle un nombre al bot: `SONAR Alertas`
4. Ponle un username: `sonar_alertas_bot` (debe terminar en `_bot`)
5. BotFather te dará el **token** — cópialo

### Paso 2 — Agregar el token al .env

```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUVwxyz
```

### Paso 3 — Reiniciar el backend

```bash
docker compose restart backend worker
```

### Paso 4 — Cada usuario configura su Chat ID

Cada persona que quiera recibir alertas debe:

1. Buscar el bot en Telegram (por el username que le pusiste)
2. Escribir `/start` al bot
3. Ir a https://t.me/userinfobot y escribir `/start` ahí también → te da tu **Chat ID**
4. En SONAR: ir a **Mi Perfil** → sección **Telegram** → ingresar el Chat ID → activar

> El Chat ID es un número como `123456789` o `-100123456789` (grupos tienen `-100` al inicio).

### Canales que usan Telegram

| Severidad | Telegram | WhatsApp | Email |
|---|:---:|:---:|:---:|
| 🔵 Baja | — | — | — |
| ⚠️ Media | ✓ | — | — |
| 🔴 Alta | ✓ | ✓ | ✓ |
| 🚨 Crítica | ✓ | ✓ | ✓ |

---

## 8. Configurar notificaciones Email

### Paso 1 — Crear una contraseña de aplicación Gmail

> **No uses tu contraseña normal de Gmail.** Google requiere una "contraseña de aplicación".

1. Ve a tu cuenta de Google: https://myaccount.google.com
2. Ve a **"Seguridad"** → **"Verificación en 2 pasos"** (actívala si no está activa)
3. Ve a **"Seguridad"** → **"Contraseñas de aplicaciones"**
4. Selecciona: App = `Correo`, Dispositivo = `Otro` → escribe `SONAR`
5. Haz clic en **"Generar"** → copia la contraseña de 16 caracteres

### Paso 2 — Agregar al .env

```env
GMAIL_USER=tu.email@gmail.com
GMAIL_APP_PASSWORD=abcd efgh ijkl mnop
```

> La contraseña de aplicación tiene espacios — inclúyelos tal como Gmail la muestra.

### Paso 3 — Reiniciar

```bash
docker compose restart backend worker
```

### Paso 4 — Activar en el perfil

Cada usuario va a **Mi Perfil** → sección **Email** → activa la casilla.

---

## 9. Configurar notificaciones WhatsApp

WhatsApp usa **CallMeBot** — servicio gratuito sin registro de tarjeta.

### Paso 1 — Activar CallMeBot para tu número

1. Guarda el número **+34 644 25 72 17** en tus contactos como "CallMeBot"
2. Envíale un WhatsApp con el texto exacto: `I allow callmebot to send me messages`
3. Recibirás una respuesta con tu **API Key** personal

### Paso 2 — Configurar en SONAR

Cada usuario va a **Mi Perfil**:
- **Número de WhatsApp:** tu número con código de país (ej: `573001234567` para Colombia)
- **API Key WhatsApp:** la clave que te envió CallMeBot
- Activa la casilla

### Paso 3 — Guardar

Haz clic en **"Guardar cambios"** en la sección de notificaciones.

---

## 10. Configurar HuggingFace para NLP

El análisis de sentimiento e identificación de discurso de odio requiere **HuggingFace**. El token es gratuito.

### Paso 1 — Crear cuenta y token

1. Ve a https://huggingface.co y crea una cuenta gratuita
2. Ve a https://huggingface.co/settings/tokens
3. Haz clic en **"New token"**
   - Name: `SONAR`
   - Type: **Read**
4. Copia el token generado (empieza con `hf_...`)

### Paso 2 — Agregar al .env

```env
HUGGINGFACE_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxx
NLP_MODE=api
```

> Con `NLP_MODE=api` el análisis se hace en los servidores de HuggingFace (gratis, sin RAM local).
> Si tu servidor tiene +2 GB de RAM disponible, puedes usar `NLP_MODE=local` para mayor velocidad.

### Paso 3 — Reiniciar

```bash
docker compose restart worker
```

### Verificar

```bash
docker compose logs worker --tail=50
```

Deberías ver líneas como: `[NLP] Procesadas X menciones pendientes`

---

## 11. Crear entidades y palabras clave

Una vez el sistema está corriendo, necesitas decirle **qué monitorear**.

### Crear una entidad

1. Ve a **Entidades** en el menú lateral
2. Haz clic en **"+ Nueva entidad"**
3. Rellena:
   - **Nombre:** nombre completo (ej: `Iglesia El Camino`)
   - **Tipo:** Iglesia / Político / Líder Religioso / etc.
   - **País:** Colombia, México, etc.
   - **Descripción:** opcional
4. Haz clic en **"Crear entidad"**

### Agregar palabras clave

Haz clic en la entidad → pestaña **Keywords**:

| Keyword | Peso | Cuándo usarlo |
|---|---|---|
| nombre completo | Normal (1) | Siempre |
| apodo / alias | Normal (1) | Si es conocido así |
| término sensible | Importante (2) | Palabras que merecen atención |
| `escándalo`, `denuncia`, `fraude` | Crítico (3) | Genera alerta inmediata |

### Agregar aliases

Pestaña **Aliases** → nombres alternativos, usernames de redes sociales, variaciones de escritura.

Ejemplos para "Pastor Juan Rodríguez":
- `@pastorjuan`
- `Juan Rodríguez pastor`
- `pastor Rodriguez`

### Configurar reglas de alerta

Pestaña **Reglas de alerta** de la entidad → crea las reglas que apliquen:

| Regla | Umbral sugerido | Ventana |
|---|---|---|
| Pico de Volumen | 3 (= 3x el promedio) | 60 min |
| Umbral Negatividad | 70 (= 70%) | 120 min |
| Discurso de Odio | 5 menciones | 60 min |
| Campaña Coordinada | 3 cuentas | 60 min |

---

## 12. Verificar que el monitoreo está corriendo

### Ver logs de los scrapers

```bash
# Logs del worker en tiempo real
docker compose logs -f worker

# Solo errores
docker compose logs worker 2>&1 | grep -i "error\|warning"
```

### Ver logs del NLP

```bash
docker compose logs -f worker | grep "NLP\|nlp"
```

### Forzar un scraping manual

```bash
# Reddit
docker compose exec backend celery -A app.workers.celery_app call app.workers.tasks.scraping.scrape_reddit

# YouTube
docker compose exec backend celery -A app.workers.celery_app call app.workers.tasks.scraping.scrape_youtube

# RSS
docker compose exec backend celery -A app.workers.celery_app call app.workers.tasks.scraping.scrape_rss

# Twitter/X
docker compose exec backend celery -A app.workers.celery_app call app.workers.tasks.scraping.scrape_twitter

# Procesar menciones pendientes con NLP
docker compose exec backend celery -A app.workers.celery_app call app.workers.tasks.nlp.process_pending_mentions
```

### Verificar desde el dashboard

1. Abre http://localhost:3000
2. El **Dashboard** debe mostrar menciones en las métricas superiores
3. Ve a **Menciones** para ver las publicaciones recolectadas con su análisis de sentimiento

### Frecuencia automática de cada scraper

| Plataforma | Cada cuánto corre | Requiere configuración |
|---|---|---|
| Reddit | 15 minutos | Sí — API key gratuita |
| YouTube | 30 minutos | Sí — API key gratuita |
| RSS / Noticias | 20 minutos | **No** |
| Twitter / X | 20 minutos | Sí — cuentas Twitter |
| NLP (análisis IA) | 5 minutos | Sí — token HuggingFace |
| Motor de alertas | 5 minutos | Automático |
| Limpieza (+12 meses) | Diario 3am | Automático |

---

## 13. Resumen rápido de comandos

```bash
# ── Arranque ──────────────────────────────────────────────────
docker compose up -d                          # Iniciar todo
docker compose down                           # Apagar todo
docker compose ps                             # Ver estado servicios

# ── Primer uso ────────────────────────────────────────────────
docker compose exec backend python scripts/create_admin.py

# ── Twitter: agregar cuentas ──────────────────────────────────
docker compose exec backend python scripts/add_twitter_account.py
docker compose exec backend python scripts/add_twitter_account.py --list

# ── Reiniciar tras cambios en .env ────────────────────────────
docker compose restart backend worker beat

# ── Reconstruir imagen (tras cambios en requirements.txt) ─────
docker compose build backend
docker compose up -d

# ── Ver logs ──────────────────────────────────────────────────
docker compose logs -f worker                 # Worker en tiempo real
docker compose logs -f backend                # Backend en tiempo real
docker compose logs backend --tail=100        # Últimas 100 líneas

# ── Scrapers manuales ─────────────────────────────────────────
docker compose exec backend celery -A app.workers.celery_app call app.workers.tasks.scraping.scrape_reddit
docker compose exec backend celery -A app.workers.celery_app call app.workers.tasks.scraping.scrape_youtube
docker compose exec backend celery -A app.workers.celery_app call app.workers.tasks.scraping.scrape_rss
docker compose exec backend celery -A app.workers.celery_app call app.workers.tasks.scraping.scrape_twitter
docker compose exec backend celery -A app.workers.celery_app call app.workers.tasks.nlp.process_pending_mentions

# ── Base de datos ─────────────────────────────────────────────
docker compose exec db psql -U sonar_user -d sonar_db   # Abrir consola SQL
```

---

## Orden recomendado para el primer día

```
1. docker compose up -d
2. docker compose exec backend python scripts/create_admin.py
3. Editar .env con credenciales Reddit + YouTube + HuggingFace
4. docker compose restart worker beat
5. Agregar cuentas Twitter: docker compose exec backend python scripts/add_twitter_account.py
6. Crear las primeras entidades + keywords desde la interfaz web
7. Verificar menciones en http://localhost:3000/mentions después de 20 minutos
```

---

*SONAR — Sistema de Observación y Navegación en Ambientes de Redes — v1.0*
