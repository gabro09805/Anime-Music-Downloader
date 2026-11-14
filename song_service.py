import json
import re
import shutil
import string
import subprocess
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


API_URL = "https://anisongdb.com/api/search_request"
MEDIA_BASE = "https://nawdist.animemusicquiz.com/"
HEADERS = {"User-Agent": "AnimeMusicDownloader/1.0", "X-Client-Id": "AnimeMusicDownloader"}
SEARCH_FIELDS = {
    "Anime": "anime_search_filter",
    "Titolo": "song_name_search_filter",
    "Artista": "artist_search_filter",
    "Compositore": "composer_search_filter",
}
DEFAULT_TEMPLATE = "{artista} - {titolo}"
OUTPUT_FORMATS = ("originale", "mp3", "aac")
TEMPLATE_FIELDS = ("anime", "titolo", "artista", "anno", "season", "tipo")


def anime_year(song):
    vintage = song.get("animeVintage")
    if not isinstance(vintage, str):
        return ""
    match = re.search(r"\b\d{4}\b", vintage)
    return match.group() if match else ""


def search_songs(query, category):
    query = query.strip()
    if not query:
        raise ValueError("Inserisci un termine di ricerca.")
    if category not in SEARCH_FIELDS and category != "Tutti":
        raise ValueError("Categoria di ricerca non valida.")
    fields = SEARCH_FIELDS.values() if category == "Tutti" else [SEARCH_FIELDS[category]]
    body = {"and_logic": False}
    body.update({field: {"search": query, "partial_match": True, "match_case": False} for field in fields})
    return post_api(API_URL, body)


FILTER_VALUES = {
    "song_types": ("opening", "ending", "insert"),
    "broadcasts": ("normal", "dub", "rebroadcast"),
    "song_categories": ("standard", "other", "character", "chanting", "instrumental"),
    "anime_types": ("tv", "movie", "ova", "ona", "special", "other"),
}
MATCH_MODES = {
    "partial": (True, False), "exact": (False, False),
    "partial_case": (True, True), "exact_case": (False, True),
}


def advanced_search(payload):
    if not isinstance(payload, dict):
        raise ValueError("Ricerca avanzata non valida.")
    fields = payload.get("fields")
    filters = payload.get("filters")
    if not isinstance(fields, dict) or not isinstance(filters, dict):
        raise ValueError("Campi o filtri di ricerca non validi.")
    body = {"and_logic": payload.get("and_logic", False),
            "ignore_duplicate": payload.get("ignore_duplicate", False)}
    if not all(isinstance(value, bool) for value in body.values()):
        raise ValueError("Opzioni di ricerca non valide.")
    max_others = payload.get("max_other_artist", 99)
    group = payload.get("group_granularity", 0)
    if type(max_others) is not int or not 0 <= max_others <= 99 or type(group) is not int or not 0 <= group <= 99:
        raise ValueError("Il numero di artisti e membri deve essere compreso tra 0 e 99.")
    arrangement = payload.get("arrangement", True)
    include_no_links = payload.get("include_no_links", True)
    if not isinstance(arrangement, bool) or not isinstance(include_no_links, bool):
        raise ValueError("Opzioni di ricerca non valide.")
    for label, target in SEARCH_FIELDS.items():
        field = fields.get(label, {})
        if not isinstance(field, dict) or not isinstance(field.get("text", ""), str):
            raise ValueError("Campo di ricerca non valido.")
        text = field.get("text", "").strip()
        mode = field.get("mode", "partial")
        if not isinstance(mode, str) or mode not in MATCH_MODES or len(text) > 500:
            raise ValueError("Modalità o testo di ricerca non valido.")
        if text:
            partial, case = MATCH_MODES[mode]
            config = {"search": text, "partial_match": partial, "match_case": case}
            if label in ("Artista", "Compositore"):
                config.update(group_granularity=group, max_other_artist=max_others)
            if label == "Compositore":
                config["arrangement"] = arrangement
            body[target] = config
    if not any(target in body for target in SEARCH_FIELDS.values()):
        raise ValueError("Inserisci almeno un termine di ricerca.")
    selected = {}
    for name, allowed in FILTER_VALUES.items():
        values = filters.get(name)
        if not isinstance(values, list) or not values or any(not isinstance(v, str) or v not in allowed for v in values):
            raise ValueError(f"Seleziona almeno un valore valido per {name}.")
        selected[name] = values
    season = filters.get("season", "").strip() if isinstance(filters.get("season", ""), str) else None
    if season is None:
        raise ValueError("Intervallo Season non valido.")
    if season:
        match = re.fullmatch(r"(winter|spring|summer|fall)\s+(\d{4})(?:\s*[-–—]\s*(winter|spring|summer|fall)\s+(\d{4}))?", season, re.I)
        if not match:
            raise ValueError("Season non valida. Usa ad esempio Spring 2020 - Fall 2024.")
        a, ay, b, by = match.groups()
        b, by = b or a, by or ay
        order = ["winter", "spring", "summer", "fall"]
        if (int(ay), order.index(a.lower())) > (int(by), order.index(b.lower())):
            raise ValueError("L'intervallo Season deve essere crescente.")
        selected["season"] = {"start": f"{a.title()} {ay}", "end": f"{b.title()} {by}"}
    difficulty = filters.get("difficulty", "")
    if not isinstance(difficulty, str):
        raise ValueError("Difficoltà non valida.")
    difficulty = difficulty.strip()
    if difficulty:
        match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(?:-\s*(\d+(?:\.\d+)?))?", difficulty)
        if not match:
            raise ValueError("Difficoltà non valida. Usa un numero o intervallo tra 0 e 100.")
        start = float(match.group(1))
        end = float(match.group(2) or match.group(1))
        if not 0 <= start <= end <= 100:
            raise ValueError("La difficoltà deve essere un intervallo crescente tra 0 e 100.")
        selected["difficulty"] = {"start": start, "end": end}
    body["filters"] = selected
    songs = post_api(API_URL, body)
    return songs if include_no_links else [song for song in songs if song.get("audio") or song.get("HQ") or song.get("MQ")]


def post_api(url, body):
    request = Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={**HEADERS, "Content-Type": "application/json"}, method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            data = json.load(response)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Errore API HTTP {exc.code}: {detail[:500]}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Impossibile contattare AnisongDB: {exc}") from exc
    except (ValueError, UnicodeError) as exc:
        raise RuntimeError("Risposta non valida da AnisongDB.") from exc
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise RuntimeError("AnisongDB ha restituito un elenco non valido.")
    return data


def get_song(song_id):
    if type(song_id) is not int or song_id <= 0:
        raise ValueError("Identificativo della traccia non valido.")
    songs = post_api("https://anisongdb.com/api/ann_song_ids_request", {"ann_song_ids": [song_id]})
    for song in songs:
        if song.get("annSongId") == song_id:
            return song
    raise ValueError("Traccia non trovata su AnisongDB.")


def media_url(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("File multimediale non disponibile.")
    value = value.strip()
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("URL multimediale non valido: è richiesto HTTPS.")
        return value
    if value in (".", "..") or "/" in value or "\\" in value or ".." in value:
        raise ValueError("Nome del file multimediale non valido.")
    return MEDIA_BASE + quote(value, safe="")


def safe_filename(value):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
    name = name[:180].encode("utf-8")[:200].decode("utf-8", errors="ignore").rstrip(" .") or "traccia"
    if re.match(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", name, re.I):
        name = "_" + name
    return name


def validate_options(output_format, template):
    if not isinstance(output_format, str) or output_format not in OUTPUT_FORMATS:
        raise ValueError("Formato di output non valido.")
    if not isinstance(template, str) or not template.strip() or len(template) > 200:
        raise ValueError("Il modello deve contenere da 1 a 200 caratteri.")
    if re.search(r"\.(mp3|aac|m4a|ogg|opus|wav|flac)$", template.strip(), re.IGNORECASE):
        raise ValueError("Non inserire l'estensione nel modello: viene aggiunta automaticamente.")
    try:
        parts = list(string.Formatter().parse(template))
    except ValueError as exc:
        raise ValueError("Modello non valido: controlla le parentesi graffe.") from exc
    for _, field, spec, conversion in parts:
        if field is not None and (field not in TEMPLATE_FIELDS or spec or conversion):
            raise ValueError("Segnaposto non valido. Usa: " + ", ".join("{" + name + "}" for name in TEMPLATE_FIELDS))


def filename_for_song(song, template):
    values = {
        "anime": song.get("animeENName") or song.get("animeJPName") or "Anime sconosciuto",
        "titolo": song.get("songName") or "Senza titolo",
        "artista": song.get("songArtist") or "Artista sconosciuto",
        "anno": anime_year(song) or "Anno sconosciuto",
        "season": song.get("animeVintage") or "Season sconosciuta",
        "tipo": song.get("songType") or "Tipo sconosciuto",
    }
    return safe_filename(template.format_map(values))


def reserve_output(directory, name, extension):
    for index in range(10000):
        suffix = f" ({index})" if index else ""
        path = directory / f"{name}{suffix}{extension}"
        try:
            return path, path.open("xb")
        except FileExistsError:
            continue
    raise OSError("Impossibile trovare un nome libero per il file.")


def copy_media(url, output):
    request = Request(url, headers={"User-Agent": HEADERS["User-Agent"]})
    try:
        with urlopen(request, timeout=60) as response:
            shutil.copyfileobj(response, output, length=128 * 1024)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Download non riuscito: {exc}") from exc


def download_song(song, directory, output_format="originale", template=DEFAULT_TEMPLATE):
    validate_options(output_format, template)
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError("La cartella di destinazione non esiste.")
    audio = song.get("audio")
    video = song.get("HQ") or song.get("MQ")
    if not audio and not video:
        raise ValueError("Nessun file audio o video disponibile per questa traccia.")
    source = media_url(audio or video)
    name = filename_for_song(song, template)
    original_extension = Path(urlparse(source).path).suffix.lower() if audio else ""
    if audio and original_extension not in {".mp3", ".m4a", ".ogg", ".opus", ".wav", ".flac", ".aac"}:
        raise ValueError("Formato audio non riconosciuto.")
    extension = (original_extension if audio else ".mp3") if output_format == "originale" else f".{output_format}"
    needs_conversion = not audio or extension != original_extension
    ffmpeg = shutil.which("ffmpeg") if needs_conversion else None
    if needs_conversion and not ffmpeg:
        raise RuntimeError("Questa traccia richiede FFmpeg per convertire o estrarre l'audio.")
    path, output = reserve_output(directory, name, extension)
    try:
        if not needs_conversion:
            with output:
                copy_media(source, output)
        else:
            output.close()
            with tempfile.TemporaryDirectory(prefix="anime-music-") as tmp:
                media_path = Path(tmp) / "media"
                with media_path.open("wb") as downloaded:
                    copy_media(source, downloaded)
                codec_args = ["-codec:a", "aac", "-b:a", "192k"] if extension == ".aac" else ["-codec:a", "libmp3lame", "-q:a", "2"]
                result = subprocess.run(
                    [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                     "-i", str(media_path), "-vn", *codec_args, str(path)],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if result.returncode:
                    raise RuntimeError(f"FFmpeg non è riuscito a estrarre l'audio: {result.stderr.strip()}")
        return path
    except Exception:
        output.close()
        path.unlink(missing_ok=True)
        raise
