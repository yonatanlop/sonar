FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema para WeasyPrint y otras libs
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-xlib-2.0-0 \
    libffi-dev \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Modelo spaCy para NER en español (12 MB, sin PyTorch)
RUN python -m spacy download es_core_news_sm

COPY . .

# Crear carpetas de almacenamiento
RUN mkdir -p storage/reports storage/uploads

# Entrypoint
RUN chmod +x entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]
