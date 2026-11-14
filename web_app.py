import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from song_service import DEFAULT_TEMPLATE, advanced_search, anime_year, download_song, get_song, search_songs, validate_options


ROOT = Path(__file__).resolve().parent
DOWNLOAD_DIR = Path(os.environ.get("DOWNLOAD_DIR", "/downloads"))
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}
MAX_REQUEST_SIZE = 16384


class Handler(BaseHTTPRequestHandler):
    def valid_host(self):
        try:
            host = urlsplit("//" + self.headers.get("Host", ""))
            return (host.hostname in ("localhost", "127.0.0.1", "::1")
                    and not host.username and not host.password and (host.port is None or host.port > 0)
                    and not host.path and not host.query and not host.fragment)
        except ValueError:
            return False

    def send_data(self, status, data, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, status, value):
        self.send_data(status, json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):
        if not self.valid_host():
            self.send_json(403, {"error": "Host non autorizzato."})
            return
        resource = STATIC_FILES.get(urlsplit(self.path).path)
        if resource is None:
            self.send_json(404, {"error": "Pagina non trovata."})
            return
        filename, content_type = resource
        try:
            data = (ROOT / "web" / filename).read_bytes()
        except OSError:
            logging.exception("Impossibile leggere la risorsa %s", filename)
            self.send_json(500, {"error": "Impossibile caricare la pagina."})
            return
        self.send_data(200, data, content_type)

    def do_POST(self):
        if self.path not in ("/api/search", "/api/download", "/api/options/validate"):
            self.send_json(404, {"error": "Operazione non trovata."})
            return
        try:
            origin = urlsplit(self.headers.get("Origin", ""))
        except ValueError:
            self.send_json(403, {"error": "Origine della richiesta non autorizzata."})
            return
        host = self.headers.get("Host", "")
        if (not self.valid_host() or origin.scheme != "http" or origin.netloc != host
                or origin.path or origin.query or origin.fragment):
            self.send_json(403, {"error": "Origine della richiesta non autorizzata."})
            return
        if self.headers.get_content_type() != "application/json":
            self.send_json(415, {"error": "La richiesta deve essere in formato JSON."})
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
            if not 0 < length <= MAX_REQUEST_SIZE:
                raise ValueError("Dimensione della richiesta non valida.")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("Richiesta non valida.")
            if self.path == "/api/search":
                if body.get("advanced") is not None:
                    songs = advanced_search(body["advanced"])
                else:
                    query = body.get("query")
                    category = body.get("category")
                    if not isinstance(query, str) or not isinstance(category, str):
                        raise ValueError("Inserisci un termine e una categoria di ricerca validi.")
                    songs = search_songs(query, category)
                self.send_json(200, {"songs": [
                    {"id": song.get("annSongId"), "anime": song.get("animeENName") or song.get("animeJPName") or "",
                     "season": song.get("animeVintage") if isinstance(song.get("animeVintage"), str) else "",
                     "year": anime_year(song),
                     "type": song.get("songType") or "", "title": song.get("songName") or "",
                     "artist": song.get("songArtist") or "",
                     "source": "Audio" if song.get("audio") else "Video" if song.get("HQ") or song.get("MQ") else "",
                     "details": song}
                    for song in songs
                ]})
            elif self.path == "/api/options/validate":
                validate_options(body.get("format"), body.get("template"))
                self.send_json(200, {"ok": True})
            else:
                output_format = body.get("format", "originale")
                template = body.get("template", DEFAULT_TEMPLATE)
                validate_options(output_format, template)
                song = get_song(body.get("id"))
                path = download_song(song, DOWNLOAD_DIR, output_format, template)
                self.send_json(200, {"filename": path.name})
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            self.send_json(400, {"error": str(exc)})
        except (RuntimeError, OSError) as exc:
            logging.exception("Operazione non riuscita")
            self.send_json(502, {"error": str(exc)})


def main():
    if not DOWNLOAD_DIR.is_dir():
        raise SystemExit(f"La cartella dei download non esiste: {DOWNLOAD_DIR}")
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Server in ascolto sulla porta {port}; download in {DOWNLOAD_DIR}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
