# SONAR v2 — Plan de Mejoras con Inteligencia Artificial

> **Rama:** `version2`
> **Base:** `master` (commit `af1ff97` — MVP + Phase 2 Twitter/X)
> **Objetivo:** Agregar capacidades de IA/Agentes gratuitas sobre la base ya construida.
> Marca cada ítem con `[x]` cuando esté completado. Si la sesión se interrumpe, retoma desde el primer `[ ]`.

---

## Módulo 1 — NLP Avanzado (mejoras al pipeline existente)

### 1.1 Detección de narrativas y temas (Topic Modeling) ✅ commit 4dca314
- [x] Instalar `scikit-learn>=1.4.0` (TF-IDF+KMeans; se usa también en módulo 2.1)
  - Nota: se descartó BERTopic/sentence-transformers para evitar añadir PyTorch (~2 GB Docker)
- [x] Crear `backend/app/workers/nlp/topics.py`
  - TF-IDF bilingüe (es/en) + MiniBatchKMeans con K dinámico (2–8 clusters)
  - Stopwords 100+ términos + ruido digital; etiquetas: top-5 términos del centroide
  - Re-etiqueta menciones de los últimos 7 días en cada ejecución
- [x] Migración 005: columnas `topic_id INT` + `topic_label VARCHAR(120)` en mentions
- [x] Tarea Celery `detect_topics` → cada hora
- [x] API `GET /entities/{id}/topics` + `POST .../analyze` (trigger manual)
- [x] Nube de temas en `EntityDetail.jsx` — píldoras de tamaño proporcional al conteo

### 1.2 Extracción de entidades nombradas (NER)
- [ ] Crear `backend/app/workers/nlp/ner.py` con clase `EntityExtractor`
  - Usa `spacy` con modelo `es_core_news_sm` (gratuito, 12 MB)
  - Extrae personas, organizaciones, lugares mencionados junto a la entidad monitoreada
  - Guarda en tabla nueva `mention_entities`
- [ ] Migración Alembic: tabla `mention_entities (id, mention_id, entity_type, entity_text)`
- [ ] Tarea Celery `extract_ner` — corre cada hora
- [ ] Endpoint `GET /api/v1/entities/{id}/related-entities` — co-ocurrencias más frecuentes
- [ ] Componente React `RelatedEntities.jsx` — grafo de co-menciones en EntityDetail

### 1.3 Clasificación automática de urgencia ✅ commit e262292
- [x] Crear `backend/app/workers/nlp/urgency.py`
  - Combina: sentimiento negativo + hate speech + reach alto → score 0-100
  - Usa reglas + pesos (no requiere modelo extra)
  - Guarda `urgency_score FLOAT` en `mentions`
- [x] Migración Alembic: columna `urgency_score NUMERIC(5,1)` + índice en `mentions`
- [x] Filtro en `GET /api/v1/mentions?min_urgency=70` — para vista prioritaria
- [x] Badge de urgencia en `Mentions.jsx` (Crítico/Urgente/Atención + filtro)

---

## Módulo 2 — Detección de Bots Mejorada

### 2.1 Clasificador de bots con ML (reemplaza heurísticas simples)
- [ ] Crear `backend/app/workers/nlp/bot_classifier.py`
  - Features: ratio tweets/día, % retweets, diversidad léxica, hora media de actividad, antigüedad cuenta
  - Modelo: `sklearn.ensemble.GradientBoostingClassifier` entrenado con dataset público (Botometer-lite)
  - Serializar modelo en `backend/storage/models/bot_model.pkl`
- [ ] Migración Alembic: columna `bot_probability FLOAT` en `account_profiles`
- [ ] Script de entrenamiento `backend/scripts/train_bot_model.py` (se corre una vez)
- [ ] Integrar en pipeline NLP existente — enriquecer perfil al scraping
- [ ] Umbral configurable en `.env`: `BOT_THRESHOLD=0.7`
- [ ] Visualización en `Dashboard.jsx` — donut chart porcentaje bots por plataforma

---

## Módulo 3 — Agente de Resumen Automático (LLM gratuito)

### 3.1 Resumen diario con Groq API (Llama 3 gratuito) ✅ commit ad618d1
- [x] Agregar `GROQ_API_KEY` y `SUMMARY_MODEL` a `.env.example`, `.env`, `config.py`
- [x] Crear `backend/app/workers/nlp/summarizer.py`
  - Prompt estructurado: temas principales, tono general, punto de atención
  - Muestra balanceada por sentimiento (máx 40 menciones)
  - Upsert por (entity_id, date) — no duplica si se llama dos veces
- [x] Migración 004: tabla `daily_summaries` con unique constraint por entidad+fecha
- [x] Tarea Celery `generate_daily_summaries` — diario a las 23:50
- [x] API `GET /entities/{id}/summaries` + `POST .../generate` (trigger manual)
- [x] Widget en `EntityDetail.jsx` — texto IA con fondo púrpura, botón "Generar ahora"
- [x] `requirements.txt`: `groq>=0.9.0`

### 3.2 Narrativa automática en reportes PDF
- [ ] Modificar `backend/app/reports/generator.py`
  - Antes de generar PDF, llamar a `DailySummarizer` para obtener párrafo introductorio
  - Incluir sección "Análisis Ejecutivo" generado por IA al inicio del reporte
- [ ] Indicador visual en PDF: "Generado con IA — Llama 3.1 (Groq)"

---

## Módulo 4 — Detección de Tendencias y Anomalías

### 4.1 Detección de picos anómalos ✅ commit 5e52881
- [x] Crear `backend/app/workers/analytics/anomaly.py`
  - Algoritmo: Z-score sobre ventana de 7 días (volumen + % negativo)
  - Si `z_score >= 2.5` → Anomaly + Alert automática con regla de sistema
- [x] Migración 003: tabla `anomalies` + ENUM `anomaly_detected` + `created_by` nullable
- [x] Tarea Celery `detect_anomalies` — corre cada 30 minutos
- [x] Alertas automáticas con severidad escalada (medium/high/critical por z-score)
- [x] Panel en `EntityDetail.jsx` — lista con barras de z-score por severidad
- [x] API `GET /entities/{id}/anomalies?days=7`

### 4.2 Predicción de tendencia (7 días)
- [ ] Crear `backend/app/workers/analytics/trends.py`
  - Usa `statsmodels` ARIMA simple o suavizado exponencial (Holt-Winters)
  - Predice menciones diarias para los próximos 7 días por entidad
  - Guarda en tabla `trend_forecasts`
- [ ] Migración Alembic: tabla `trend_forecasts (id, entity_id, forecast_date, predicted_count, confidence_low, confidence_high)`
- [ ] Tarea Celery `compute_trends` — corre diariamente a las 00:30
- [ ] Endpoint `GET /api/v1/entities/{id}/forecast`
- [ ] Gráfico de línea punteada en `EntityDetail.jsx` — proyección 7 días

---

## Módulo 5 — Agente de Monitoreo Autónomo

### 5.1 Agente de investigación de contexto (Groq + búsqueda)
- [ ] Crear `backend/app/workers/agents/context_agent.py`
  - Cuando se detecta pico anómalo → agente busca contexto en RSS feeds ya configurados
  - Envía al LLM: "¿Por qué podría estar aumentando la mención de {entidad}? Contexto: {titulares recientes}"
  - Guarda explicación en `anomalies.context_explanation`
- [ ] Integrar con motor de alertas — adjuntar contexto a alertas tipo ANOMALY
- [ ] Mostrar "¿Por qué?" en tarjeta de alerta en `Alerts.jsx`

### 5.2 Sugerencia automática de palabras clave
- [ ] Crear `backend/app/workers/agents/keyword_suggester.py`
  - Analiza menciones de los últimos 30 días por entidad
  - Extrae términos frecuentes co-ocurrentes que NO están en las keywords actuales
  - Genera lista de sugerencias con score de relevancia
- [ ] Endpoint `GET /api/v1/entities/{id}/keyword-suggestions`
- [ ] Banner en `EntityDetail.jsx` — "Sugerimos agregar estas keywords: ..."

---

## Módulo 6 — Mejoras de UX con IA

### 6.1 Búsqueda semántica de menciones
- [ ] Instalar `sentence-transformers` (ya incluido en 1.1)
- [ ] Crear `backend/app/workers/nlp/embeddings.py`
  - Genera embeddings para cada mención al procesarse (vector 384 dims)
  - Guarda en tabla `mention_embeddings` o columna `embedding VECTOR` (pgvector)
- [ ] Migración Alembic: extensión `pgvector` + columna `embedding vector(384)` en `mentions`
- [ ] Endpoint `GET /api/v1/mentions/search?q=texto+semantico` — búsqueda por similitud coseno
- [ ] Barra de búsqueda semántica en `Mentions.jsx`

### 6.2 Clustering de menciones similares (deduplicación inteligente)
- [ ] En `backend/app/workers/nlp/pipeline.py` — al procesar mención nueva
  - Comparar embedding con últimas 1000 menciones de la misma entidad
  - Si similitud coseno > 0.92 → marcar como `is_duplicate=True`
- [ ] Migración Alembic: columna `is_duplicate BOOLEAN DEFAULT FALSE` en `mentions`
- [ ] Filtro por defecto en `GET /api/v1/mentions?exclude_duplicates=true`

---

## Orden de implementación recomendado

| Prioridad | Módulo | Valor | Complejidad |
|-----------|--------|-------|-------------|
| 🥇 1 | 1.3 Urgency Score | Alto | Baja |
| 🥇 2 | 4.1 Anomaly Detection | Alto | Media |
| 🥇 3 | 3.1 Resumen Groq | Alto | Baja |
| 🥈 4 | 1.1 Topic Modeling | Alto | Media |
| 🥈 5 | 2.1 Bot Classifier ML | Medio | Media |
| 🥈 6 | 3.2 Narrativa en PDF | Medio | Baja |
| 🥉 7 | 5.1 Context Agent | Alto | Alta |
| 🥉 8 | 4.2 Trend Forecast | Medio | Alta |
| 🥉 9 | 1.2 NER | Medio | Media |
| 🥉 10 | 5.2 Keyword Suggestions | Medio | Media |
| ⬇️ 11 | 6.1 Búsqueda Semántica | Medio | Alta |
| ⬇️ 12 | 6.2 Deduplicación | Bajo | Media |

---

## Estado de dependencias externas

| Servicio | Tier gratuito | Límite | Requerido para |
|----------|--------------|--------|----------------|
| Groq API | ✅ Sí | 14,400 tok/min | Módulos 3, 5 |
| HuggingFace | ✅ Sí (ya configurado) | 1,000 req/día | Módulos 1, 6 |
| pgvector | ✅ Sí (extensión PostgreSQL) | Sin límite | Módulo 6.1 |
| spaCy `es_core_news_sm` | ✅ Sí (local) | Sin límite | Módulo 1.2 |
| BERTopic | ✅ Sí (local) | RAM ~500MB | Módulo 1.1 |

---

## Variables de entorno nuevas

Agregar a `.env` cuando se llegue al módulo correspondiente:

```env
# ─── Groq API (Módulos 3 y 5) ────────────────────────────────
# Obtener gratis en: console.groq.com
GROQ_API_KEY=

# ─── IA / Agentes ─────────────────────────────────────────────
BOT_THRESHOLD=0.7
ANOMALY_ZSCORE_THRESHOLD=2.5
SUMMARY_MODEL=llama-3.1-8b-instant
```

---

*Última actualización: 2026-03-25 | Versión base: master@af1ff97*
