#!/usr/bin/env python3
"""Fetch a Spotify podcast transcript from an episode URL or id."""

from __future__ import annotations

import argparse
import json
import os
import pprint
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

_EPISODE_ID = re.compile(r"^[A-Za-z0-9]{22}$")

INSTALL_MESSAGE = """\
spotifyscraper is not available.

Install the CLI and the browser used for Spotify login:

  uv tool install "spotifyscraper[browser,cli]"
  ~/.local/share/uv/tools/spotifyscraper/bin/playwright install chromium

spotifyscraper must be on PATH. uv installs it to ~/.local/bin.
"""

LOGIN_HINT = (
    "Opening Spotify in the browser. Log in there. Do not click Log out. "
    "This command waits until the session cookie appears, then continues."
)


class InstallError(Exception):
    """Raised when spotifyscraper cannot be imported."""


def is_episode_id(value: str) -> bool:
    return _EPISODE_ID.fullmatch(value) is not None


def extract_episode_id(value: str) -> str:
    raw = value.strip()
    if is_episode_id(raw):
        return raw
    if raw.lower().startswith("spotify:"):
        parts = raw.split(":")
        kind = parts[1].lower() if len(parts) > 1 else ""
        candidate = parts[-1]
        if kind == "episode" and is_episode_id(candidate):
            return candidate
        raise ValueError(f"not a Spotify podcast episode URL or id: {value}")

    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = parsed.netloc.lower().split("@")[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    if host not in {"open.spotify.com", "spotify.com"}:
        raise ValueError(f"not a Spotify podcast episode URL or id: {value}")
    parts = [part for part in parsed.path.split("/") if part]
    if "episode" not in parts:
        raise ValueError(f"not a Spotify podcast episode URL or id: {value}")
    index = parts.index("episode")
    if index + 1 < len(parts) and is_episode_id(parts[index + 1]):
        return parts[index + 1]
    raise ValueError(f"not a Spotify podcast episode URL or id: {value}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="fetch_transcript.py",
        description="Fetch a Spotify podcast transcript from an episode URL or id.",
    )
    parser.add_argument(
        "episodes",
        nargs="+",
        help="Spotify episode URL, URI, or 22-character episode id",
    )
    parser.add_argument(
        "--format",
        default="text",
        choices=("text", "json", "pretty"),
        help="Output format. Default: text",
    )
    parser.add_argument(
        "--no-login",
        action="store_true",
        help="Fail when the saved Spotify session is missing or rejected",
    )
    return parser.parse_args(argv)


def transcript_payload(episode_id: str, transcript: object) -> dict[str, object]:
    lines = [
        {"start_ms": line.start_ms, "text": line.text}
        for line in transcript.lines  # type: ignore[attr-defined]
    ]
    return {
        "episode_id": episode_id,
        "language": transcript.language,  # type: ignore[attr-defined]
        "provider": transcript.provider,  # type: ignore[attr-defined]
        "is_auto_generated": transcript.is_auto_generated,  # type: ignore[attr-defined]
        "lines": lines,
    }


def format_text(items: list[tuple[str, object]]) -> str:
    chunks: list[str] = []
    for episode_id, transcript in items:
        body = "\n".join(line.text for line in transcript.lines)  # type: ignore[attr-defined]
        if len(items) == 1:
            chunks.append(body)
        else:
            chunks.append(f"# {episode_id}\n{body}")
    return "\n\n".join(chunks)


def format_transcripts(items: list[tuple[str, object]], fmt: str) -> str:
    payloads = [transcript_payload(episode_id, transcript) for episode_id, transcript in items]
    if fmt == "json":
        return json.dumps(payloads, ensure_ascii=False, indent=2)
    if fmt == "pretty":
        return pprint.pformat(payloads)
    return format_text(items)


def status_line(episode_id: str, transcript: object) -> str:
    language = transcript.language or "unknown"  # type: ignore[attr-defined]
    return f"fetched {episode_id} language={language} lines={len(transcript.lines)}"  # type: ignore[attr-defined]


def find_cli() -> Path | None:
    found = shutil.which("spotifyscraper")
    if found:
        return Path(found)
    candidate = Path.home() / ".local" / "bin" / "spotifyscraper"
    if candidate.is_file():
        return candidate
    return None


def shebang_python(cli: Path) -> Path | None:
    try:
        first = cli.read_text(encoding="utf-8").splitlines()[0]
    except (OSError, UnicodeError):
        return None
    if not first.startswith("#!"):
        return None
    rest = first[2:].strip()
    if rest.startswith("/usr/bin/env "):
        name = rest.split(maxsplit=1)[1].strip()
        resolved = shutil.which(name)
        return Path(resolved) if resolved else None
    executable = Path(rest.split()[0])
    if executable.is_file():
        return executable
    return None


def reexec_with_tool_python() -> None:
    cli = find_cli()
    if cli is None:
        return
    python = shebang_python(cli)
    if python is None:
        return
    if python.resolve() == Path(sys.executable).resolve():
        return
    script = str(Path(__file__).resolve())
    os.execv(str(python), [str(python), script, *sys.argv[1:]])


def load_library() -> object:
    try:
        import spotify_scraper
    except ImportError:
        reexec_with_tool_python()
        raise InstallError(INSTALL_MESSAGE) from None
    return spotify_scraper


def open_login(library: object, *, reuse: bool) -> None:
    client_cls = library.SpotifyClient  # type: ignore[attr-defined]
    info = client_cls.session_info()
    if reuse and info.valid:
        return
    if info.valid:
        reason = "Spotify rejected the saved session"
    else:
        reason = info.reason or "no saved Spotify session"
    print(f"spotify session unusable ({reason}). {LOGIN_HINT}", file=sys.stderr)
    try:
        with client_cls() as client:
            client.login(reuse=reuse, timeout=600)
    except ImportError as exc:
        raise InstallError(
            f"{exc}\n\n{INSTALL_MESSAGE}"
        ) from exc


def fetch_saved(library: object, episode_id: str) -> object:
    client_cls = library.SpotifyClient  # type: ignore[attr-defined]
    with client_cls.from_saved_session() as client:
        return client.get_transcript(episode_id)


def write_stdout(text: str) -> None:
    if not text:
        return
    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")


def _session_error(exc: Exception) -> int:
    print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
    return 4


def fetch_one(library: object, episode_id: str, *, allow_login: bool) -> object:
    try:
        return fetch_saved(library, episode_id)
    except library.AuthenticationError:  # type: ignore[attr-defined]
        if not allow_login:
            raise
        print(f"{episode_id}: saved session was rejected. {LOGIN_HINT}", file=sys.stderr)
        open_login(library, reuse=False)
        return fetch_saved(library, episode_id)


def collect_transcripts(
    library: object,
    episode_ids: list[str],
    *,
    allow_login: bool,
) -> tuple[list[tuple[str, object]], int]:
    if allow_login:
        open_login(library, reuse=True)
    fetched: list[tuple[str, object]] = []
    failures = 0
    for episode_id in episode_ids:
        try:
            transcript = fetch_one(library, episode_id, allow_login=allow_login)
        except library.AuthenticationError as exc:  # type: ignore[attr-defined]
            print(f"{episode_id}: AuthenticationError: {exc}", file=sys.stderr)
            failures += 1
            continue
        except library.NotFoundError as exc:  # type: ignore[attr-defined]
            print(f"{episode_id}: NotFoundError: {exc}", file=sys.stderr)
            failures += 1
            continue
        except library.SessionError as exc:  # type: ignore[attr-defined]
            print(f"{episode_id}: SessionError: {exc}", file=sys.stderr)
            failures += 1
            continue
        fetched.append((episode_id, transcript))
        print(status_line(episode_id, transcript), file=sys.stderr)
    return fetched, failures


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        episode_ids = [extract_episode_id(value) for value in args.episodes]
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    library: object | None = None
    try:
        library = load_library()
        fetched, failures = collect_transcripts(
            library,
            episode_ids,
            allow_login=not args.no_login,
        )
    except InstallError as exc:
        print(exc, file=sys.stderr)
        return 1
    except Exception as exc:
        if type(exc).__name__ in {"SessionError", "AuthenticationError"}:
            return _session_error(exc)
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if fetched:
        write_stdout(format_transcripts(fetched, args.format))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
