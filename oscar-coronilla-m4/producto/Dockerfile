# Imagen del HR Assistant para Render (spec/04-production.md, punto 5).
FROM python:3.12-slim

# Sin archivos .pyc y con la salida sin búfer, para que el log JSON salga al instante
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Primero las dependencias, para aprovechar la caché de capas de Docker
COPY requirements.txt .
RUN pip install -r requirements.txt

# Solo lo que el producto necesita para correr; .dockerignore deja fuera el resto
COPY app/ ./app/
COPY data/ ./data/

# Usuario sin privilegios: el proceso nunca corre como root
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Render indica el puerto en PORT; en local se usa 8000
EXPOSE 8000

# Forma de shell para expandir ${PORT:-8000}; exec deja a uvicorn como proceso 1
# y así recibe las señales de parada. --no-access-log mantiene el log solo en JSON.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log
