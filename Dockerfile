# The whole workshop app - SkyBook and Pulse - in one image.
#
#   docker build -t workshop .
#   docker run -d --restart unless-stopped -p 8000:8000 workshop
#
# Or use docker-compose.yml, which adds Redis and keeps the data.

FROM python:3.12-slim

# Don't buffer stdout, so "docker logs" shows the request log as it happens.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

WORKDIR /app

# Requirements first, so changing the code does not reinstall everything.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py mock_server.py ./
COPY pulse/ ./pulse/

# The question bank is written to while the workshop runs, so it lives in a
# directory we can mount a volume onto.
ENV PULSE_DB=/data/pulse.db
RUN mkdir -p /data && cp pulse/pulse.db /data/pulse.db

# Run as a normal user, not root.
RUN useradd --create-home --uid 10001 workshop && chown -R workshop /app /data
USER workshop

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,os,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/health', timeout=4).status==200 else 1)"

CMD ["python", "main.py"]
