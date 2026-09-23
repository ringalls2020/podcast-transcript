#!/usr/bin/env python3
"""Fetch a YouTube transcript from a URL or video id."""

from __future__ import annotations

import argparse
import json
import os
import pprint
import re
import shutil
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol
from urllib.parse import parse_qs, urlparse

_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_PATH_MARKERS = ("shorts", "embed", "live", "v")

INSTALL_MESSAGE = """\
youtube-transcript-api is not available.

Install the CLI, then rerun this script:

  uv tool install youtube-transcript-api

If uv is missing, use either:

  pipx install youtube-transcript-api
  python3 -m pip install --user youtube-transcript-api

youtube_transcript_api must be on PATH. uv installs it to ~/.local/bin.
"""


class InstallError(Exception):
    """Raised when youtube-transcript-api cannot be imported."""


class TranscriptListLike(Protocol):
    def find_transcript(self, language_codes: list[str]) -> object: ...

    def find_generated_transcript(self, language_codes: list[str]) -> object: ...

    def find_manually_created_transcript(self, language_codes: list[str]) -> object: ...

    def __iter__(self) -> Iterator[object]: ...


class TranscriptApi(Protocol):
    def list(self, video_id: str) -> TranscriptListLike: ...


def is_video_id(value: str) -> bool:
    return _VIDEO_ID.fullmatch(value) is not None


def youtube_host(netloc: str) -> str:
    host = netloc.lower().split("@")[-1].split(":")[0]
    if host.startswith("www."):
        return host[4:]
    return host


def is_youtube_host(host: str) -> bool:
    return (
        host == "youtu.be"
        or host == "youtube.com"
        or host == "youtube-nocookie.com"
        or host.endswith(".youtube.com")
        or host.endswith(".youtube-nocookie.com")
    )


def extract_video_id(value: str) -> str:
    raw = value.strip()
    if is_video_id(raw):
        return raw

    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = youtube_host(parsed.netloc)
    if not is_youtube_host(host):
        raise ValueError(f"not a YouTube video URL or id: {value}")

    if host == "youtu.be":
        candidate = parsed.path.strip("/").split("/", 1)[0]
        if is_video_id(candidate):
            return candidate
        raise ValueError(f"not a YouTube video URL or id: {value}")

    parts = [part for part in parsed.path.split("/") if part]
    for marker in _PATH_MARKERS:
        if marker not in parts:
            continue
        index = parts.index(marker)
        if index + 1 < len(parts) and is_video_id(parts[index + 1]):
            return parts[index + 1]

    video_ids = parse_qs(parsed.query).get("v", [])
    if video_ids and is_video_id(video_ids[0]):
        return video_ids[0]
    raise ValueError(f"not a YouTube video URL or id: {value}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="fetch_transcript.py",
        description="Fetch a YouTube transcript from a video URL or id.",
    )
    parser.add_argument(
        "videos",
        nargs="+",
        help="YouTube URL or 11-character video id",
    )
    parser.add_argument(
        "--languages",
        nargs="+",
        default=None,
        metavar="CODE",
        help="Language codes to try, in order. Example: --languages es en",
    )
    parser.add_argument(
        "--format",
        default="text",
        choices=("text", "json", "pretty", "srt", "webvtt"),
        help="Output format. Default: text",
    )
    parser.add_argument(
        "--list",
        dest="list_transcripts",
        action="store_true",
        help="List caption tracks instead of fetching one",
    )
    parser.add_argument(
        "--translate",
        default=None,
        metavar="CODE",
        help="Translate the selected track to this language code",
    )
    parser.add_argument("--exclude-generated", action="store_true")
    parser.add_argument("--exclude-manually-created", action="store_true")
    parser.add_argument("--webshare-proxy-username", default=None)
    parser.add_argument("--webshare-proxy-password", default=None)
    parser.add_argument(
        "--webshare-filter",
        nargs="+",
        default=None,
        metavar="CC",
        help="Webshare country codes, for example: de us",
    )
    parser.add_argument("--http-proxy", default=None)
    parser.add_argument("--https-proxy", default=None)
    return parser.parse_args(argv)


def select_transcript(
    transcript_list: TranscriptListLike,
    languages: list[str] | None,
    exclude_generated: bool,
    exclude_manual: bool,
) -> object:
    if exclude_generated and exclude_manual:
        raise ValueError(
            "pass only one of --exclude-generated and --exclude-manually-created"
        )

    codes = list(languages) if languages else ["en"]
    try:
        if exclude_generated:
            return transcript_list.find_manually_created_transcript(codes)
        if exclude_manual:
            return transcript_list.find_generated_transcript(codes)
        return transcript_list.find_transcript(codes)
    except Exception:
        if languages:
            raise
        for transcript in transcript_list:
            generated = bool(getattr(transcript, "is_generated", False))
            if exclude_generated and generated:
                continue
            if exclude_manual and not generated:
                continue
            return transcript
        raise


def transcript_payload(fetched: object) -> dict[str, object]:
    return {
        "video_id": fetched.video_id,  # type: ignore[attr-defined]
        "language": fetched.language,  # type: ignore[attr-defined]
        "language_code": fetched.language_code,  # type: ignore[attr-defined]
        "is_generated": fetched.is_generated,  # type: ignore[attr-defined]
        "snippets": fetched.to_raw_data(),  # type: ignore[attr-defined]
    }


def format_text(fetched_list: list[object]) -> str:
    chunks: list[str] = []
    for fetched in fetched_list:
        body = "\n".join(snippet.text for snippet in fetched)  # type: ignore[attr-defined]
        video_id = fetched.video_id  # type: ignore[attr-defined]
        if len(fetched_list) == 1:
            chunks.append(body)
        else:
            chunks.append(f"# {video_id}\n{body}")
    return "\n\n".join(chunks)


def format_fetched(fetched_list: list[object], fmt: str) -> str:
    if fmt == "json":
        payloads = [transcript_payload(item) for item in fetched_list]
        return json.dumps(payloads, ensure_ascii=False, indent=2)
    if fmt == "text":
        return format_text(fetched_list)
    if fmt == "pretty":
        return pprint.pformat([transcript_payload(item) for item in fetched_list])

    from youtube_transcript_api.formatters import FormatterLoader

    return FormatterLoader().load(fmt).format_transcripts(fetched_list)


def format_list(transcript_list: TranscriptListLike) -> str:
    rows = ["code\tlanguage\tkind\ttranslatable"]
    for transcript in transcript_list:
        kind = "generated" if transcript.is_generated else "manual"  # type: ignore[attr-defined]
        translatable = "yes" if transcript.is_translatable else "no"  # type: ignore[attr-defined]
        rows.append(
            f"{transcript.language_code}\t{transcript.language}\t{kind}\t{translatable}"  # type: ignore[attr-defined]
        )
    return "\n".join(rows)


def render_lists(items: list[tuple[str, str]]) -> str:
    if len(items) == 1:
        return items[0][1]
    return "\n\n".join(f"# {video_id}\n{body}" for video_id, body in items)


def status_line(fetched: object) -> str:
    kind = "generated" if fetched.is_generated else "manual"  # type: ignore[attr-defined]
    return (
        f"fetched {fetched.video_id} "  # type: ignore[attr-defined]
        f"language={fetched.language_code} "  # type: ignore[attr-defined]
        f"kind={kind} "
        f"lines={len(fetched)}"  # type: ignore[arg-type]
    )


def find_cli() -> Path | None:
    found = shutil.which("youtube_transcript_api")
    if found:
        return Path(found)
    candidate = Path.home() / ".local" / "bin" / "youtube_transcript_api"
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


def load_library() -> tuple[type, type, type]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api.proxies import (
            GenericProxyConfig,
            WebshareProxyConfig,
        )
    except ImportError:
        reexec_with_tool_python()
        raise InstallError(INSTALL_MESSAGE) from None
    return YouTubeTranscriptApi, GenericProxyConfig, WebshareProxyConfig


def _env_or_flag(flag: str | None, env_name: str) -> str | None:
    value = flag or os.environ.get(env_name)
    if value:
        return value
    return None


def build_proxy(
    args: argparse.Namespace,
    generic_cls: type,
    webshare_cls: type,
) -> object | None:
    username = _env_or_flag(
        args.webshare_proxy_username,
        "YOUTUBE_TRANSCRIPT_WEBSHARE_USERNAME",
    )
    password = _env_or_flag(
        args.webshare_proxy_password,
        "YOUTUBE_TRANSCRIPT_WEBSHARE_PASSWORD",
    )
    if args.webshare_filter and not (username and password):
        raise ValueError("--webshare-filter requires Webshare username and password")
    if username or password:
        if not username or not password:
            raise ValueError(
                "Webshare proxy needs both a username and a password "
                "(flags or YOUTUBE_TRANSCRIPT_WEBSHARE_USERNAME and "
                "YOUTUBE_TRANSCRIPT_WEBSHARE_PASSWORD)"
            )
        return webshare_cls(
            proxy_username=username,
            proxy_password=password,
            filter_ip_locations=args.webshare_filter,
        )

    http_url = _env_or_flag(args.http_proxy, "YOUTUBE_TRANSCRIPT_HTTP_PROXY")
    https_url = _env_or_flag(args.https_proxy, "YOUTUBE_TRANSCRIPT_HTTPS_PROXY")
    if http_url or https_url:
        return generic_cls(http_url=http_url, https_url=https_url)
    return None


def fetch_video(
    api: TranscriptApi,
    video_id: str,
    args: argparse.Namespace,
) -> tuple[str, object]:
    transcript_list = api.list(video_id)
    if args.list_transcripts:
        return ("list", format_list(transcript_list))

    transcript = select_transcript(
        transcript_list,
        args.languages,
        args.exclude_generated,
        args.exclude_manually_created,
    )
    if args.translate:
        transcript = transcript.translate(args.translate)  # type: ignore[attr-defined]
    return ("fetch", transcript.fetch())  # type: ignore[attr-defined]


def write_stdout(text: str) -> None:
    if not text:
        return
    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")


def run_videos(api: TranscriptApi, video_ids: list[str], args: argparse.Namespace) -> int:
    failures = 0
    fetched: list[object] = []
    listed: list[tuple[str, str]] = []
    for video_id in video_ids:
        try:
            outcome, value = fetch_video(api, video_id, args)
        except Exception as exc:
            failures += 1
            print(f"{video_id}: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        if outcome == "list":
            listed.append((video_id, str(value)))
            print(f"listed {video_id}", file=sys.stderr)
        else:
            fetched.append(value)
            print(status_line(value), file=sys.stderr)

    if args.list_transcripts and listed:
        write_stdout(render_lists(listed))
    elif fetched:
        write_stdout(format_fetched(fetched, args.format))
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        video_ids = [extract_video_id(value) for value in args.videos]
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    if args.exclude_generated and args.exclude_manually_created:
        print(
            "pass only one of --exclude-generated and --exclude-manually-created",
            file=sys.stderr,
        )
        return 1
    try:
        api_cls, generic_cls, webshare_cls = load_library()
        proxy = build_proxy(args, generic_cls, webshare_cls)
    except (InstallError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    api = api_cls(proxy_config=proxy)
    return run_videos(api, video_ids, args)


if __name__ == "__main__":
    raise SystemExit(main())
