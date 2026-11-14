import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import web_app


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = web_app.ThreadingHTTPServer(("127.0.0.1", 0), web_app.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.host = f"127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        data = response.read()
        connection.close()
        return response.status, data

    def post(self, path, data, origin=None):
        return self.request("POST", path, json.dumps(data), {
            "Content-Type": "application/json",
            "Origin": origin or f"http://{self.host}",
        })

    def test_static_files_and_unknown_route(self):
        status, data = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Anime Music Downloader", data)
        self.assertEqual(self.request("GET", "/app.js")[0], 200)
        self.assertEqual(self.request("GET", "/style.css")[0], 200)
        self.assertEqual(self.request("GET", "/web_app.py")[0], 404)

    def test_search_response_and_input_validation(self):
        rows = [
            {"annSongId": 3, "animeENName": "Anime", "animeVintage": "Fall 1999",
             "songName": "<title>", "audio": "file.mp3"},
            {"annSongId": 4, "animeENName": "Anime", "animeVintage": "Fall 2011"},
            {"annSongId": 5, "animeENName": "Anime", "animeVintage": None},
        ]
        with patch.object(web_app, "search_songs", return_value=rows) as search:
            status, data = self.post("/api/search", {"query": "abc", "category": "Anime"})
        self.assertEqual(status, 200)
        songs = json.loads(data)["songs"]
        self.assertEqual(songs[0], {
            "id": 3, "anime": "Anime", "season": "Fall 1999", "year": "1999", "type": "", "title": "<title>", "artist": "", "source": "Audio", "details": rows[0]
        })
        self.assertEqual([song["year"] for song in songs], ["1999", "2011", ""])
        self.assertEqual([song["season"] for song in songs], ["Fall 1999", "Fall 2011", ""])
        search.assert_called_once_with("abc", "Anime")
        self.assertEqual(self.post("/api/search", {"query": 123})[0], 400)

    def test_advanced_search_passes_parameters_and_returns_details(self):
        settings = {"fields": {"Anime": {"text": "Naruto", "mode": "exact"}}}
        row = {"annSongId": 10, "animeJPName": "Naruto", "songComposer": "Composer"}
        with patch.object(web_app, "advanced_search", return_value=[row]) as search:
            status, data = self.post("/api/search", {"advanced": settings})
        self.assertEqual(status, 200)
        search.assert_called_once_with(settings)
        self.assertEqual(json.loads(data)["songs"][0]["details"]["songComposer"], "Composer")

    def test_download_uses_server_lookup_and_configured_directory(self):
        song = {"annSongId": 3, "audio": "file.mp3"}
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(web_app, "DOWNLOAD_DIR", Path(tmp)), \
             patch.object(web_app, "get_song", return_value=song) as get_song, \
             patch.object(web_app, "download_song", return_value=Path(tmp) / "song.mp3") as download:
            status, data = self.post("/api/download", {"id": 3, "audio": "https://evil.example/a.mp3"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data), {"filename": "song.mp3"})
        get_song.assert_called_once_with(3)
        download.assert_called_once_with(song, Path(tmp), "originale", "{artista} - {titolo}")

    def test_options_validation_and_download(self):
        options = {"format": "aac", "template": "{anime} - {titolo}"}
        self.assertEqual(self.post("/api/options/validate", options)[0], 200)
        self.assertEqual(self.post("/api/options/validate", {"format": "aac", "template": "{nope}"})[0], 400)
        with patch.object(web_app, "get_song", return_value={"annSongId": 3}) as lookup, \
             patch.object(web_app, "download_song", return_value=Path("output.aac")) as download:
            status, data = self.post("/api/download", {"id": 3, **options})
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(data)["filename"], "output.aac")
            download.assert_called_once_with({"annSongId": 3}, web_app.DOWNLOAD_DIR, "aac", options["template"])
            lookup.reset_mock()
            status, data = self.post("/api/download", {"id": 3, "format": "wav", "template": "{titolo}"})
            self.assertEqual(status, 400)
            lookup.assert_not_called()

    def test_denies_cross_origin_and_foreign_host(self):
        self.assertEqual(self.post("/api/download", {"id": 3}, "http://evil.example")[0], 403)
        self.assertEqual(self.request("GET", "/", headers={"Host": "evil.example"})[0], 403)
        self.assertEqual(self.request("POST", "/api/download", "{}", {
            "Host": "evil.example", "Origin": "http://evil.example", "Content-Type": "application/json"
        })[0], 403)
        self.assertEqual(self.request("POST", "/api/download", "{}", {
            "Origin": f"http://{self.host}", "Content-Type": "text/plain"
        })[0], 415)

    def test_download_and_upstream_errors_are_visible(self):
        with patch.object(web_app, "get_song", side_effect=ValueError("traccia non trovata")):
            status, data = self.post("/api/download", {"id": -1})
        self.assertEqual(status, 400)
        self.assertIn("traccia non trovata", json.loads(data)["error"])
        with patch.object(web_app, "search_songs", side_effect=RuntimeError("servizio non disponibile")):
            status, data = self.post("/api/search", {"query": "abc", "category": "Anime"})
        self.assertEqual(status, 502)
        self.assertIn("servizio non disponibile", json.loads(data)["error"])


if __name__ == "__main__":
    unittest.main()
