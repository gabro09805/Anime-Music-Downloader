FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY song_service.py web_app.py ./
COPY web ./web
RUN mkdir /downloads

ENV DOWNLOAD_DIR=/downloads PORT=8080 PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python", "web_app.py"]
