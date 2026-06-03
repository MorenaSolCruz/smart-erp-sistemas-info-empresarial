FROM python:3.12-slim

# Evita archivos .pyc y fuerza logs sin buffer para que Docker muestre eventos al instante.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
# Instala Django, DRF, MongoEngine, requests y dependencias del backend.
RUN pip install --no-cache-dir -r requirements.txt

# Copia el codigo backend dentro del contenedor.
COPY . /app

# Puerto donde Django sirve la API.
EXPOSE 8000

