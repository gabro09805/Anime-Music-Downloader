FROM python:3.10-slim

# Installa FFmpeg e altre dipendenze di sistema necessarie
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Imposta la cartella di lavoro
WORKDIR /app

# Copia i requisiti e installali
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia tutto il resto del codice nel contenitore
COPY . .

# Imposta le variabili d'ambiente
ENV DOWNLOAD_DIR=/downloads \
    PORT=8080 \
    PYTHONUNBUFFERED=1

# Espone la porta della Web GUI
EXPOSE 8080

# Comando per avviare il programma
CMD ["python", "web_app.py"]\n
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
