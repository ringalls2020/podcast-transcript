# Spotify login

`scripts/fetch_transcript.py` opens the browser itself when the saved session cannot be used. This file is the rest of the contract.

The session is an `sp_dc` cookie captured by [SpotifyScraper](https://github.com/AliAkhtari78/SpotifyScraper) from a browser window the user logs into. The script never accepts the cookie as an argument. The cookie is not printed.

## What the user does

1. The script prints `Opening Spotify in the browser` on stderr and opens a window.
2. The user signs in to Spotify in that window.
3. The user leaves the window alone. Clicking Log out invalidates the cookie that was just captured.
4. The script sees the cookie, closes the login wait, and fetches the transcript.

A later fetch reuses the saved session and does not open a browser. When Spotify rejects the cookie, the script opens the browser again and retries that episode once.

## Where the session lives

SpotifyScraper stores it in the per-user config directory. Override the directory with `SPOTIFYSCRAPER_CONFIG_DIR`. The file mode is owner-only. Do not commit it, copy it into the chat, or print it.

Check the session without revealing the cookie:

```bash
spotifyscraper session
```

Force a fresh browser login:

```bash
spotifyscraper login --no-reuse
```

Remove the local session:

```bash
spotifyscraper logout
```

## Install the login browser

```bash
uv tool install "spotifyscraper[browser,cli]"
~/.local/share/uv/tools/spotifyscraper/bin/playwright install chromium
```

`login()` needs a display. A machine with no screen cannot open the window.

## Output

`text` is caption lines separated by newlines. More than one episode adds a `# <episode-id>` heading before each transcript.

`json` is a list of objects:

```json
[
  {
    "episode_id": "07gKzPFkbvGF0cHoeG7ARS",
    "language": "en",
    "provider": null,
    "is_auto_generated": false,
    "lines": [
      {"start_ms": 0, "text": "hello"}
    ]
  }
]
```

`start_ms` is milliseconds from the start of the episode. `pretty` prints those same objects with Python `pprint`.

## Limits

Not every episode has a transcript. Those return `NotFoundError`.

This uses Spotify's web-player transcript endpoint with the user's own session. SpotifyScraper documents that use as personal and educational. The endpoint can change until that library updates.
