FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
ENV DB_PATH=/data/asistente.db
VOLUME /data
EXPOSE 8000
# proxy-headers: detrás de Caddy, para que los logs muestren la IP real (el puerto solo es accesible localmente)
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
