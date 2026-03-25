FROM python:3.11-slim
RUN apt-get update && apt-get install procps -y && rm -rf /var/lib/apt/lists/*
RUN useradd -m dockeruser
WORKDIR /app
RUN mkdir -p /app/grafs && mkdir -p /app/log
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ./Physical_properties.py .
RUN chown -R dockeruser:dockeruser /app
USER dockeruser
HEALTHCHECK --interval=30s --timeout=5s \
    CMD pgrep -f "Physical_properties.py" || exit 1
CMD ["python3", "Physical_properties.py"]