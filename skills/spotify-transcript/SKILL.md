---
name: spotify-transcript
description: >
  Fetch the transcript of a Spotify podcast episode from a URL, URI, or episode id.
  Use when the user asks to "get the Spotify transcript", "fetch this podcast transcript",
  "what does this episode say", pastes an open.spotify.com/episode link, or runs
  /spotify-transcript. Opens Spotify in the browser when the saved login session is
  missing or expired, waits for the user to log in, then continues the fetch.
license: MIT
compatibility: >
  Requires the spotifyscraper command on PATH
  (`uv tool install "spotifyscraper[browser,cli]"`) and Playwright Chromium for the
  one-time Spotify login. Needs a display and outbound network access to Spotify.
metadata:
  short-description: Fetch a Spotify podcast transcript
  version: "1.0.0"
---

# Spotify transcript

Fetch a podcast transcript with `scripts/fetch_transcript.py`, which sits beside this file. Pass an episode URL, a `spotify:episode:` URI, or a 22-character episode id. Stdout is the transcript. Stderr is status. The process exit code is the result.

Run the script by its absolute path. One command covers login and the fetch.

## Run

```bash
python3 <skill-dir>/scripts/fetch_transcript.py "<episode-url>"
```

`<skill-dir>` is the directory that contains this SKILL.md.

Default format is plain text, one caption line per row. When the user asked for the transcript, return stdout. When they asked for a summary, fetch first and summarize from stdout. Every quoted line comes from that stdout.

Read the stderr status line for the language and the line count.

| Ask | Command |
| --- | --- |
| spoken words | `python3 <skill-dir>/scripts/fetch_transcript.py "<episode-url>"` |
| timestamps | add `--format json` |

Pass several episode URLs in one command. Text output for more than one episode starts each transcript with `# <episode-id>`.

## Login

A valid saved Spotify session is reused with no browser. When the session is missing, expired, or rejected, the script opens Spotify in a browser window and waits.

Tell the user a browser window opened. They log in there. They must not click Log out. The script waits up to 10 minutes for the session cookie, then prints the transcript. Wait for that process to exit.

Do not ask the user to paste a cookie, token, or password into the chat. Do not read, print, or copy the saved session file.

`references/auth.md` owns the session storage path and the manual refresh command.

## Missing CLI

When stderr says `spotifyscraper is not available`, install the tool and the login browser, then run the same fetch once more:

```bash
uv tool install "spotifyscraper[browser,cli]"
~/.local/share/uv/tools/spotifyscraper/bin/playwright install chromium
```

`spotifyscraper` must be on `PATH`. uv installs it to `~/.local/bin`.

## Failures

Return the stderr line.

| stderr | Action |
| --- | --- |
| `not a Spotify podcast episode URL or id` | Ask for an `open.spotify.com/episode/` link |
| `NotFoundError` | This episode has no Spotify transcript. Stop |
| `AuthenticationError` after a login attempt | The login did not produce a usable session. Ask the user to log in again in the browser, then run the fetch once more |
| `ImportError` mentioning Playwright | Run the Playwright install command above, then run the fetch once more |

A show link, a track link, and a playlist link are not episodes.
