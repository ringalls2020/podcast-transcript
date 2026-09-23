"""Unit tests for URL parsing, track selection, and transcript formatting."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "youtube-transcript" / "scripts" / "fetch_transcript.py"


def load_module():
    spec = importlib.util.spec_from_file_location("fetch_transcript", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fetch = load_module()


class Snippet:
    def __init__(self, text: str, start: float = 0.0, duration: float = 1.0) -> None:
        self.text = text
        self.start = start
        self.duration = duration


class Fetched:
    def __init__(self, video_id: str, lines: list[Snippet], generated: bool = False) -> None:
        self.video_id = video_id
        self.language = "English"
        self.language_code = "en"
        self.is_generated = generated
        self._lines = lines

    def __iter__(self):
        return iter(self._lines)

    def __len__(self) -> int:
        return len(self._lines)

    def to_raw_data(self) -> list[dict[str, object]]:
        return [
            {"text": line.text, "start": line.start, "duration": line.duration}
            for line in self._lines
        ]


class Track:
    def __init__(
        self,
        code: str,
        language: str,
        generated: bool,
        translatable: bool,
    ) -> None:
        self.language_code = code
        self.language = language
        self.is_generated = generated
        self.is_translatable = translatable


class Missing(Exception):
    pass


class Catalog:
    def __init__(self, items: list[Track], error: Exception | None = None) -> None:
        self._items = items
        self._error = error or Missing("missing")
        self.calls: list[tuple[str, list[str]]] = []

    def find_transcript(self, codes: list[str]) -> object:
        self.calls.append(("find", list(codes)))
        raise self._error

    def find_generated_transcript(self, codes: list[str]) -> object:
        self.calls.append(("generated", list(codes)))
        raise self._error

    def find_manually_created_transcript(self, codes: list[str]) -> object:
        self.calls.append(("manual", list(codes)))
        raise self._error

    def __iter__(self):
        return iter(self._items)


class HitCatalog:
    def find_transcript(self, codes: list[str]) -> tuple[str, list[str]]:
        return ("hit", list(codes))

    def find_generated_transcript(self, codes: list[str]) -> tuple[str, list[str]]:
        return ("generated", list(codes))

    def find_manually_created_transcript(self, codes: list[str]) -> tuple[str, list[str]]:
        return ("manual", list(codes))

    def __iter__(self):
        return iter(())


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("jNQXAC9IVRw", "jNQXAC9IVRw"),
        ("  jNQXAC9IVRw  ", "jNQXAC9IVRw"),
        ("-abc1234567", "-abc1234567"),
        ("https://www.youtube.com/watch?v=jNQXAC9IVRw", "jNQXAC9IVRw"),
        ("https://www.youtube.com/watch?v=jNQXAC9IVRw&list=PLxxxx&t=12s", "jNQXAC9IVRw"),
        ("https://youtu.be/jNQXAC9IVRw", "jNQXAC9IVRw"),
        ("https://youtu.be/jNQXAC9IVRw?t=1", "jNQXAC9IVRw"),
        ("https://www.youtube.com/shorts/jNQXAC9IVRw", "jNQXAC9IVRw"),
        ("https://www.youtube.com/embed/jNQXAC9IVRw", "jNQXAC9IVRw"),
        ("https://www.youtube.com/live/jNQXAC9IVRw", "jNQXAC9IVRw"),
        ("https://www.youtube.com/v/jNQXAC9IVRw", "jNQXAC9IVRw"),
        ("https://m.youtube.com/watch?v=jNQXAC9IVRw", "jNQXAC9IVRw"),
        ("https://music.youtube.com/watch?v=jNQXAC9IVRw", "jNQXAC9IVRw"),
        ("https://www.youtube-nocookie.com/embed/jNQXAC9IVRw", "jNQXAC9IVRw"),
        ("youtube.com/watch?v=jNQXAC9IVRw", "jNQXAC9IVRw"),
    ],
)
def test_extract_video_id(value: str, expected: str) -> None:
    assert fetch.extract_video_id(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "https://example.com/watch?v=jNQXAC9IVRw",
        "https://www.youtube.com/playlist?list=PL1234567890",
        "https://www.youtube.com/watch?v=short",
        "not a video",
        "abcdefghijkextra",
    ],
)
def test_extract_video_id_rejects(value: str) -> None:
    with pytest.raises(ValueError, match="not a YouTube video URL or id"):
        fetch.extract_video_id(value)


def test_parse_args_defaults() -> None:
    args = fetch.parse_args(["https://youtu.be/jNQXAC9IVRw"])
    assert args.videos == ["https://youtu.be/jNQXAC9IVRw"]
    assert args.format == "text"
    assert args.languages is None
    assert args.list_transcripts is False
    assert args.translate is None


def test_parse_args_languages_and_format() -> None:
    args = fetch.parse_args(
        ["https://youtu.be/jNQXAC9IVRw", "--format", "json", "--languages", "de", "en"]
    )
    assert args.format == "json"
    assert args.languages == ["de", "en"]


def test_select_uses_requested_language_order() -> None:
    chosen = fetch.select_transcript(HitCatalog(), ["de", "en"], False, False)
    assert chosen == ("hit", ["de", "en"])


def test_select_falls_back_when_english_is_missing() -> None:
    german = Track("de", "German", False, False)
    catalog = Catalog([german])
    chosen = fetch.select_transcript(catalog, None, False, False)
    assert chosen is german
    assert catalog.calls == [("find", ["en"])]


def test_select_requested_language_does_not_fall_back() -> None:
    catalog = Catalog([Track("de", "German", False, False)])
    with pytest.raises(Missing):
        fetch.select_transcript(catalog, ["fr"], False, False)


def test_select_skips_generated_on_fallback() -> None:
    generated = Track("de", "German", True, False)
    manual = Track("es", "Spanish", False, True)
    catalog = Catalog([generated, manual])
    chosen = fetch.select_transcript(catalog, None, True, False)
    assert chosen is manual
    assert catalog.calls == [("manual", ["en"])]


def test_select_rejects_both_excludes() -> None:
    with pytest.raises(ValueError, match="only one"):
        fetch.select_transcript(HitCatalog(), None, True, True)


def test_format_text_single_video_has_no_heading() -> None:
    text = fetch.format_text(
        [Fetched("jNQXAC9IVRw", [Snippet("hello"), Snippet("there")])]
    )
    assert text == "hello\nthere"


def test_format_text_multiple_videos_have_headings() -> None:
    text = fetch.format_text(
        [
            Fetched("jNQXAC9IVRw", [Snippet("one")]),
            Fetched("dQw4w9WgXcQ", [Snippet("two")]),
        ]
    )
    assert text == "# jNQXAC9IVRw\none\n\n# dQw4w9WgXcQ\ntwo"


def test_format_json_includes_metadata() -> None:
    payload = json.loads(
        fetch.format_fetched(
            [Fetched("jNQXAC9IVRw", [Snippet("hello", 1.5, 2.0)], generated=True)],
            "json",
        )
    )
    assert payload == [
        {
            "video_id": "jNQXAC9IVRw",
            "language": "English",
            "language_code": "en",
            "is_generated": True,
            "snippets": [{"text": "hello", "start": 1.5, "duration": 2.0}],
        }
    ]


def test_format_list_is_tab_separated() -> None:
    table = fetch.format_list(
        [
            Track("en", "English", False, False),
            Track("de", "German", True, True),
        ]
    )
    assert table == (
        "code\tlanguage\tkind\ttranslatable\n"
        "en\tEnglish\tmanual\tno\n"
        "de\tGerman\tgenerated\tyes"
    )


class GenericProxy:
    def __init__(self, http_url: str | None = None, https_url: str | None = None) -> None:
        self.http_url = http_url
        self.https_url = https_url


class WebshareProxy:
    def __init__(
        self,
        proxy_username: str,
        proxy_password: str,
        filter_ip_locations: list[str] | None = None,
    ) -> None:
        self.proxy_username = proxy_username
        self.proxy_password = proxy_password
        self.filter_ip_locations = filter_ip_locations


def test_build_proxy_prefers_webshare(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("YOUTUBE_TRANSCRIPT_WEBSHARE_USERNAME", "user")
    monkeypatch.setenv("YOUTUBE_TRANSCRIPT_WEBSHARE_PASSWORD", "secret")
    monkeypatch.setenv("YOUTUBE_TRANSCRIPT_HTTP_PROXY", "http://proxy.example")
    args = fetch.parse_args(["jNQXAC9IVRw", "--webshare-filter", "de", "us"])
    proxy = fetch.build_proxy(args, GenericProxy, WebshareProxy)
    assert isinstance(proxy, WebshareProxy)
    assert proxy.proxy_username == "user"
    assert proxy.proxy_password == "secret"
    assert proxy.filter_ip_locations == ["de", "us"]


def test_build_proxy_generic_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YOUTUBE_TRANSCRIPT_WEBSHARE_USERNAME", raising=False)
    monkeypatch.delenv("YOUTUBE_TRANSCRIPT_WEBSHARE_PASSWORD", raising=False)
    monkeypatch.setenv("YOUTUBE_TRANSCRIPT_HTTPS_PROXY", "http://proxy.example:8080")
    args = fetch.parse_args(["jNQXAC9IVRw"])
    proxy = fetch.build_proxy(args, GenericProxy, WebshareProxy)
    assert isinstance(proxy, GenericProxy)
    assert proxy.http_url is None
    assert proxy.https_url == "http://proxy.example:8080"


def test_build_proxy_requires_both_webshare_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("YOUTUBE_TRANSCRIPT_WEBSHARE_PASSWORD", raising=False)
    monkeypatch.setenv("YOUTUBE_TRANSCRIPT_WEBSHARE_USERNAME", "user")
    args = fetch.parse_args(["jNQXAC9IVRw"])
    with pytest.raises(ValueError, match="both a username and a password"):
        fetch.build_proxy(args, GenericProxy, WebshareProxy)


def test_main_rejects_a_non_youtube_url(capsys: pytest.CaptureFixture[str]) -> None:
    code = fetch.main(["https://example.com/watch?v=jNQXAC9IVRw"])
    assert code == 1
    assert "not a YouTube video URL or id" in capsys.readouterr().err


def test_main_rejects_both_exclude_flags(capsys: pytest.CaptureFixture[str]) -> None:
    code = fetch.main(
        ["jNQXAC9IVRw", "--exclude-generated", "--exclude-manually-created"]
    )
    assert code == 1
    assert "only one" in capsys.readouterr().err
