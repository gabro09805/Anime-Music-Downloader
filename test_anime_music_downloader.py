import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import song_service as app


class DownloadTests(unittest.TestCase):
    def test_advanced_search_builds_expected_api_filters(self):
        settings = {
            "fields": {"Anime": {"text": "Naruto", "mode": "exact_case"},
                       "Compositore": {"text": "Test", "mode": "partial"}},
            "filters": {name: list(values) for name, values in app.FILTER_VALUES.items()},
            "and_logic": True, "ignore_duplicate": True, "max_other_artist": 2,
            "group_granularity": 1, "arrangement": False, "include_no_links": False,
        }
        settings["filters"]["season"] = "Fall 1999 - Spring 2011"
        settings["filters"]["difficulty"] = "10 - 90"
        rows = [{"songName": "linked", "audio": "a.mp3"}, {"songName": "missing"}]
        with patch.object(app, "post_api", return_value=rows) as post:
            self.assertEqual(app.advanced_search(settings), rows[:1])
        body = post.call_args.args[1]
        self.assertEqual(body["anime_search_filter"], {"search": "Naruto", "partial_match": False, "match_case": True})
        self.assertEqual(body["composer_search_filter"]["max_other_artist"], 2)
        self.assertFalse(body["composer_search_filter"]["arrangement"])
        self.assertTrue(body["and_logic"])
        self.assertEqual(body["filters"]["season"], {"start": "Fall 1999", "end": "Spring 2011"})
        self.assertEqual(body["filters"]["difficulty"], {"start": 10.0, "end": 90.0})

    def test_advanced_search_rejects_bad_filters(self):
        settings = {"fields": {"Anime": {"text": "Naruto", "mode": "partial"}},
                    "filters": {name: list(values) for name, values in app.FILTER_VALUES.items()}}
        for change in ({"song_types": []}, {"season": "Fall 2020 - Winter 2019"},
                       {"difficulty": "101"}, {"anime_types": ["invalid"]}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                app.advanced_search({**settings, "filters": {**settings["filters"], **change}})
        for mode in ("unknown", [], None):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                app.advanced_search({**settings, "fields": {"Anime": {"text": "Naruto", "mode": mode}}})

    def test_advanced_search_modes(self):
        filters = {name: list(values) for name, values in app.FILTER_VALUES.items()}
        for mode, flags in app.MATCH_MODES.items():
            with self.subTest(mode=mode), patch.object(app, "post_api", return_value=[]) as post:
                app.advanced_search({"fields": {"Titolo": {"text": "Test", "mode": mode}}, "filters": filters})
                actual = post.call_args.args[1]["song_name_search_filter"]
                self.assertEqual((actual["partial_match"], actual["match_case"]), flags)

    def test_filename_template(self):
        song = {"animeENName": "Hunter/Name", "songName": "A:B", "songArtist": "Artist",
                "animeVintage": "Fall 1999", "songType": "Opening 1"}
        template = "{anime} - {titolo} - {artista} - {anno} - {season} - {tipo}"
        app.validate_options("aac", template)
        self.assertEqual(app.filename_for_song(song, template),
                         "Hunter_Name - A_B - Artist - 1999 - Fall 1999 - Opening 1")
        self.assertEqual(app.filename_for_song({}, app.DEFAULT_TEMPLATE), "Artista sconosciuto - Senza titolo")
        self.assertLessEqual(len(app.safe_filename("音" * 180).encode("utf-8")), 200)

    def test_invalid_options(self):
        for output_format, template in [
            ("wav", "{titolo}"), (None, "{titolo}"), ("mp3", ""), ("mp3", "{invalid}"),
            ("mp3", "{titolo.__class__}"), ("mp3", "{titolo!r}"), ("mp3", "{titolo:10}"),
            ("mp3", "{titolo"), ("mp3", "{titolo}.mp3"), ("mp3", "x" * 201),
        ]:
            with self.subTest(output_format=output_format, template=template), self.assertRaises(ValueError):
                app.validate_options(output_format, template)

    def test_conversion_options_and_copy_same_format(self):
        song = {"audio": "file.mp3", "songArtist": "Artist", "songName": "Song", "animeENName": "Anime"}
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(app, "copy_media", side_effect=lambda url, out: out.write(b"audio")), \
             patch.object(app.shutil, "which", return_value="ffmpeg") as which, \
             patch.object(app.subprocess, "run") as run:
            direct = app.download_song(song, tmp, "mp3", "{anime} - {titolo}")
            self.assertEqual(direct.name, "Anime - Song.mp3")
            run.assert_not_called()
            which.assert_not_called()
            run.return_value.returncode = 0
            result = app.download_song(song, tmp, "aac", "{anime} - {titolo}")
            self.assertEqual(result.name, "Anime - Song.aac")
            args = run.call_args.args[0]
            self.assertIn("aac", args)
            self.assertNotIn("libmp3lame", args)
            app.download_song({"HQ": "video.webm"}, tmp, "aac")
            self.assertIn("aac", run.call_args.args[0])

    def test_anime_year(self):
        for vintage, expected in [
            ("Fall 1999", "1999"), ("Fall 2011", "2011"), ("2004", "2004"),
            ("", ""), (None, ""), ("Unknown", ""), ("Season 12345", ""),
        ]:
            with self.subTest(vintage=vintage):
                self.assertEqual(app.anime_year({"animeVintage": vintage}), expected)
        self.assertEqual(app.anime_year({}), "")

    def test_media_url_and_filename_validation(self):
        self.assertEqual(app.media_url("file name.mp3"), app.MEDIA_BASE + "file%20name.mp3")
        for value in ("../file.mp3", "folder/file.mp3", "http://example.com/a.mp3"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                app.media_url(value)
        self.assertEqual(app.safe_filename("CON"), "_CON")
        self.assertEqual(app.safe_filename('a/b: c'), "a_b_ c")

    def test_download_preserves_existing_file(self):
        song = {"audio": "file.mp3", "songArtist": "Artist", "songName": "Song"}
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "Artist - Song.mp3"
            existing.write_bytes(b"existing")
            with patch.object(app, "copy_media", side_effect=lambda url, out: out.write(b"audio")):
                result = app.download_song(song, tmp)
            self.assertEqual(existing.read_bytes(), b"existing")
            self.assertEqual(result.name, "Artist - Song (1).mp3")
            self.assertEqual(result.read_bytes(), b"audio")

    def test_failed_download_removes_partial_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            def fail(url, output):
                output.write(b"partial")
                raise RuntimeError("network error")

            with patch.object(app, "copy_media", side_effect=fail):
                with self.assertRaisesRegex(RuntimeError, "network error"):
                    app.download_song({"audio": "file.mp3"}, tmp)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_video_conversion_and_failure_cleanup(self):
        song = {"HQ": "video.webm", "songArtist": "Artist", "songName": "Song"}
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(app.shutil, "which", return_value="ffmpeg"), \
                 patch.object(app, "copy_media", side_effect=lambda url, out: out.write(b"video")), \
                 patch.object(app.subprocess, "run") as run:
                run.return_value.returncode = 1
                run.return_value.stderr = "conversion failed"
                with self.assertRaisesRegex(RuntimeError, "conversion failed"):
                    app.download_song(song, tmp)
                self.assertEqual(list(Path(tmp).iterdir()), [])
                run.return_value.returncode = 0
                run.side_effect = lambda args, **kwargs: (
                    Path(args[-1]).write_bytes(b"converted") and run.return_value
                )
                result = app.download_song(song, tmp)
                self.assertEqual(result.read_bytes(), b"converted")

    def test_invalid_source_and_missing_ffmpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "Nessun file"):
                app.download_song({}, tmp)
            with patch.object(app.shutil, "which", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "FFmpeg"):
                    app.download_song({"HQ": "video.webm"}, tmp)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_search_request_and_invalid_response(self):
        response = io.BytesIO(b'[{"songName":"Example"}]')
        with patch.object(app, "urlopen", return_value=response) as urlopen:
            self.assertEqual(app.search_songs(" example ", "Anime"), [{"songName": "Example"}])
            body = urlopen.call_args.args[0].data
            self.assertIn(b'"search": "example"', body)
            self.assertIn(b'"anime_search_filter"', body)
        with patch.object(app, "urlopen", return_value=io.BytesIO(b'{"unexpected":true}')):
            with self.assertRaisesRegex(RuntimeError, "elenco non valido"):
                app.search_songs("example", "Anime")

    def test_all_fields_use_or_logic(self):
        with patch.object(app, "urlopen", return_value=io.BytesIO(b"[]")) as urlopen:
            app.search_songs("Naruto", "Tutti")
            body = json.loads(urlopen.call_args.args[0].data)
            self.assertIs(body["and_logic"], False)
            for field in app.SEARCH_FIELDS.values():
                self.assertEqual(body[field]["search"], "Naruto")


if __name__ == "__main__":
    unittest.main()
