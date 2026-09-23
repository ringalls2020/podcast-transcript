---
name: youtube-transcript
description: >
  Fetch the transcript or captions of a YouTube video from a URL or 11-character
  video id. Use when the user asks to "get the transcript", "fetch the captions",
  "fetch the subtitles", "what does this video say", "transcribe this YouTube video",
  pastes a youtube.com, youtu.be, or YouTube Shorts link and wants the spoken words,
  or runs /youtube-transcript. Covers manual and auto-generated captions. No YouTube
  API key and no browser.
license: MIT
compatibility: >
  Requires youtube_transcript_api on PATH. Install with
  `uv tool install youtube-transcript-api`. Needs outbound network access to YouTube.
metadata:
  short-description: Fetch a YouTube transcript
  version: "1.0.0"
---

# YouTube transcript

Fetch captions with `scripts/fetch_transcript.py`, which sits beside this file. Pass a YouTube URL or an 11-character video id. Stdout is the transcript. Stderr is a one-line status. The process exit code is the result.

Run the script by its absolute path. `youtube_transcript_api` accepts only a video id and exits 0 when YouTube rejects the request, so use this script's exit code.

## Run

```bash
python3 <skill-dir>/scripts/fetch_transcript.py "<url-or-id>"
```

`<skill-dir>` is the directory that contains this SKILL.md.

Default format is plain text, one caption line per row. When the user asked for the transcript, return stdout. When they asked for a summary, fetch first and summarize from stdout. Every quoted line comes from that stdout.

Read the stderr status line for the language code and whether the track is `manual` or `generated`.

| Ask | Command |
| --- | --- |
| spoken words | `python3 <skill-dir>/scripts/fetch_transcript.py "<url>"` |
| timestamps | add `--format json` |
| caption file | add `--format srt` or `--format webvtt` |
| language order | add `--languages es en` |
| available tracks | add `--list` |
| translated captions | add `--translate de` |

Pass several URLs in one command. Text output for more than one video starts each transcript with `# <video-id>`.

With no `--languages` value, the script tries English and then the first remaining track. With `--languages`, it uses that order only.

When the video id starts with `-`, put `--` before it:

```bash
python3 <skill-dir>/scripts/fetch_transcript.py -- "-abc1234567"
```

## Missing CLI

When stderr says `youtube-transcript-api is not available`, install the CLI and run the same fetch once more:

```bash
uv tool install youtube-transcript-api
```

`youtube_transcript_api` must be on `PATH`. uv installs it to `~/.local/bin`. When `uv` is missing:

```bash
pipx install youtube-transcript-api
```

## Failures

Return the stderr line.

| stderr | Action |
| --- | --- |
| `not a YouTube video URL or id` | Ask for a watch URL, a youtu.be link, a Shorts URL, or an 11-character id |
| `IpBlocked` or `RequestBlocked` | Open `references/cli.md` and configure a proxy, then run the fetch once more. A second block ends the task |
| an age-restriction error | Report it. Cookie login in youtube-transcript-api is disabled upstream |
| any other exception | Report the exception name and message |

`--list` prints a tab-separated table: `code`, `language`, `kind` (`manual` or `generated`), `translatable` (`yes` or `no`). `--list` ignores `--format` and `--translate`.

## Proxy and extra flags

`references/cli.md` owns proxy environment variables, Webshare, generic proxies, exclude flags, and the JSON shape.
