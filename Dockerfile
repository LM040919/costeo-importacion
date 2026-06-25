# Imagen para desplegar la app de costeo (Streamlit) en Coolify / cualquier host con Docker.
FROM python:3.13-slim

WORKDIR /app

# Dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código de la app
COPY . .

# Streamlit escucha en este puerto (configúralo igual en Coolify: Port = 8501)
EXPOSE 8501

# Health check que Coolify/Docker pueden usar
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
