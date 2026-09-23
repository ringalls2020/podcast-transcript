"""Unit tests for Spotify episode ids, formatting, and login gating."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "spotify-transcript" / "scripts" / "fetch_transcript.py"
EPISODE = "07gKzPFkbvGF0cHoeG7ARS"


def load_module():
    spec = importlib.util.spec_from_file_location("spotify_fetch_transcript", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fetch = load_module()


class Line:
    def __init__(self, text: str, start_ms: int) -> None:
        self.text = text
        self.start_ms = start_ms


class Transcript:
    def __init__(self, lines: list[Line], language: str | None = "en") -> None:
        self.lines = lines
        self.language = language
        self.provider = "spotify"
        self.is_auto_generated = False


class Info:
    def __init__(self, valid: bool, reason: str | None = None) -> None:
        self.valid = valid
        self.reason = reason


class AuthError(Exception):
    pass


class MissingError(Exception):
    pass


class SessionProblem(Exception):
    pass


class FakeClient:
    def __init__(self, library: "FakeLib") -> None:
        self.library = library

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def login(self, *, reuse: bool, timeout: float = 600) -> None:
        self.library.login_calls.append(reuse)
        self.library.info = Info(True)
        self.library.login_timeout = timeout

    def get_transcript(self, episode_id: str) -> Transcript:
        self.library.fetch_calls.append(episode_id)
        if self.library.reject_next:
            self.library.reject_next = False
            raise AuthError("rejected")
        if episode_id in self.library.missing:
            raise MissingError("no transcript")
        return Transcript([Line("hello there", 1500)])


class FakeClientClass:
    def __init__(self, library: "FakeLib") -> None:
        self.library = library

    def __call__(self) -> FakeClient:
        return FakeClient(self.library)

    def session_info(self) -> Info:
        return self.library.info

    def from_saved_session(self) -> FakeClient:
        if not self.library.info.valid:
            raise SessionProblem("no saved session")
        return FakeClient(self.library)


class FakeLib:
    def __init__(self, valid: bool = True) -> None:
        self.info = Info(valid, None if valid else "expired")
        self.login_calls: list[bool] = []
        self.fetch_calls: list[str] = []
        self.reject_next = False
        self.missing: set[str] = set()
        self.SpotifyClient = FakeClientClass(self)
        self.AuthenticationError = AuthError
        self.NotFoundError = MissingError
        self.SessionError = SessionProblem


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (EPISODE, EPISODE),
        (f"  {EPISODE}  ", EPISODE),
        (f"https://open.spotify.com/episode/{EPISODE}", EPISODE),
        (f"https://open.spotify.com/episode/{EPISODE}?si=abc", EPISODE),
        (f"https://open.spotify.com/intl-en/episode/{EPISODE}", EPISODE),
        (f"https://open.spotify.com/embed/episode/{EPISODE}", EPISODE),
        (f"spotify:episode:{EPISODE}", EPISODE),
        (f"open.spotify.com/episode/{EPISODE}", EPISODE),
    ],
)
def test_extract_episode_id(value: str, expected: str) -> None:
    assert fetch.extract_episode_id(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        f"https://open.spotify.com/track/{EPISODE}",
        f"https://open.spotify.com/show/{EPISODE}",
        f"spotify:track:{EPISODE}",
        "https://example.com/episode/" + EPISODE,
        "not-an-episode",
        EPISODE[:-1],
    ],
)
def test_extract_episode_id_rejects(value: str) -> None:
    with pytest.raises(ValueError, match="not a Spotify podcast episode"):
        fetch.extract_episode_id(value)


def test_format_text_and_json() -> None:
    transcript = Transcript([Line("hello", 0), Line("there", 1200)])
    assert fetch.format_text([(EPISODE, transcript)]) == "hello\nthere"
    payload = json.loads(fetch.format_transcripts([(EPISODE, transcript)], "json"))
    assert payload[0]["episode_id"] == EPISODE
    assert payload[0]["lines"] == [
        {"start_ms": 0, "text": "hello"},
        {"start_ms": 1200, "text": "there"},
    ]


def test_open_login_skips_a_valid_session() -> None:
    library = FakeLib(valid=True)
    fetch.open_login(library, reuse=True)
    assert library.login_calls == []


def test_open_login_opens_browser_when_expired(capsys: pytest.CaptureFixture[str]) -> None:
    library = FakeLib(valid=False)
    fetch.open_login(library, reuse=True)
    assert library.login_calls == [True]
    assert "Opening Spotify in the browser" in capsys.readouterr().err


def test_rejected_session_logs_in_once_and_retries(
    capsys: pytest.CaptureFixture[str],
) -> None:
    library = FakeLib(valid=True)
    library.reject_next = True
    fetched, failures = fetch.collect_transcripts(library, [EPISODE], allow_login=True)
    assert failures == 0
    assert fetched[0][0] == EPISODE
    assert library.login_calls == [False]
    assert library.fetch_calls == [EPISODE, EPISODE]
    assert "saved session was rejected" in capsys.readouterr().err


def test_no_login_does_not_open_a_browser(capsys: pytest.CaptureFixture[str]) -> None:
    library = FakeLib(valid=False)
    fetched, failures = fetch.collect_transcripts(
        library, [EPISODE], allow_login=False
    )
    assert fetched == []
    assert failures == 1
    assert library.login_calls == []
    assert "SessionError" in capsys.readouterr().err


def test_missing_transcript_is_a_failure(capsys: pytest.CaptureFixture[str]) -> None:
    library = FakeLib(valid=True)
    library.missing.add(EPISODE)
    fetched, failures = fetch.collect_transcripts(library, [EPISODE], allow_login=True)
    assert fetched == []
    assert failures == 1
    assert "NotFoundError" in capsys.readouterr().err


def test_main_rejects_a_track_url(capsys: pytest.CaptureFixture[str]) -> None:
    code = fetch.main([f"https://open.spotify.com/track/{EPISODE}"])
    assert code == 1
    assert "not a Spotify podcast episode" in capsys.readouterr().err


@pytest.mark.parametrize(
    "value",
    [
        "https://open.spotify.com/episode/too-short",
        "spotify:episode:too-short",
        EPISODE + "x",
    ],
)
def test_extract_rejects_bad_id_shape(value: str) -> None:
    with pytest.raises(ValueError, match="not a Spotify podcast episode"):
        fetch.extract_episode_id(value)


def test_expired_session_logs_in_once_then_fetches() -> None:
    library = FakeLib(valid=False)
    fetched, failures = fetch.collect_transcripts(library, [EPISODE], allow_login=True)
    assert failures == 0
    assert fetched[0][0] == EPISODE
    assert library.login_calls == [True]
    assert library.login_timeout == 600
    assert library.fetch_calls == [EPISODE]


def test_auth_failure_after_retry_does_not_loop() -> None:
    library = FakeLib(valid=True)

    def always_reject(episode_id: str) -> Transcript:
        library.fetch_calls.append(episode_id)
        raise AuthError("rejected")

    library.SpotifyClient.from_saved_session = lambda: _ClientWith(always_reject, library)  # type: ignore[method-assign]
    fetched, failures = fetch.collect_transcripts(library, [EPISODE], allow_login=True)
    assert fetched == []
    assert failures == 1
    assert library.login_calls == [False]
    assert library.fetch_calls == [EPISODE, EPISODE]


class _ClientWith:
    def __init__(self, get_transcript, library: FakeLib) -> None:
        self._get = get_transcript
        self.library = library

    def __enter__(self) -> "_ClientWith":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def login(self, *, reuse: bool, timeout: float = 600) -> None:
        self.library.login_calls.append(reuse)
        self.library.login_timeout = timeout
        self.library.info = Info(True)

    def get_transcript(self, episode_id: str) -> Transcript:
        return self._get(episode_id)


def test_main_no_login_does_not_open_browser_on_auth_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    library = FakeLib(valid=True)
    library.reject_next = True
    monkeypatch.setattr(fetch, "load_library", lambda: library)
    code = fetch.main(["--no-login", f"https://open.spotify.com/episode/{EPISODE}"])
    assert code == 1
    assert library.login_calls == []
    err = capsys.readouterr().err
    assert "AuthenticationError" in err


def test_not_found_still_fetches_the_next_episode(
    capsys: pytest.CaptureFixture[str],
) -> None:
    library = FakeLib(valid=True)
    library.missing.add(EPISODE)
    other = "A" * 22
    fetched, failures = fetch.collect_transcripts(
        library, [EPISODE, other], allow_login=True
    )
    assert failures == 1
    assert [item[0] for item in fetched] == [other]
    assert library.login_calls == []
    text = fetch.format_text(fetched)
    assert text == "hello there"
    assert "NotFoundError" in capsys.readouterr().err


def test_two_episode_text_has_headings() -> None:
    other = "B" * 22
    text = fetch.format_text(
        [
            (EPISODE, Transcript([Line("one", 0)])),
            (other, Transcript([Line("two", 1)])),
        ]
    )
    assert text == f"# {EPISODE}\none\n\n# {other}\ntwo"


def test_login_import_error_becomes_install_instructions() -> None:
    library = FakeLib(valid=False)

    class Broken:
        def __enter__(self) -> "Broken":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def login(self, *, reuse: bool, timeout: float = 600) -> None:
            raise ImportError("playwright is not installed")

    library.SpotifyClient = type(  # type: ignore[assignment]
        "Client",
        (),
        {
            "session_info": staticmethod(lambda: Info(False, "expired")),
            "__call__": lambda self: Broken(),
        },
    )()
    with pytest.raises(fetch.InstallError, match="playwright install chromium"):
        fetch.open_login(library, reuse=True)
