# CLI details

`scripts/fetch_transcript.py` is the interface agents run. This file is the rest of the contract: proxies, track filters, and output shapes.

## Exclude a caption type

```bash
python3 scripts/fetch_transcript.py "<url>" --exclude-generated
python3 scripts/fetch_transcript.py "<url>" --exclude-manually-created
```

Pass only one of those flags. When both a manual track and a generated track match the requested language, the manual track is selected.

## Proxy

YouTube answers with `IpBlocked` or `RequestBlocked` from many cloud networks, and sometimes after repeated requests. Configure one proxy and rerun the same fetch once. A second block ends the task.

Webshare residential rotating proxies use a username and password:

```bash
export YOUTUBE_TRANSCRIPT_WEBSHARE_USERNAME="username"
export YOUTUBE_TRANSCRIPT_WEBSHARE_PASSWORD="password"
python3 scripts/fetch_transcript.py "<url>"
```

The same values can be flags:

```bash
python3 scripts/fetch_transcript.py "<url>" \
  --webshare-proxy-username "username" \
  --webshare-proxy-password "password"
```

Limit the Webshare IP pool to country codes with `--webshare-filter`. The filter requires both credentials:

```bash
python3 scripts/fetch_transcript.py "<url>" --webshare-filter de us
```

Webshare credentials take precedence over a generic proxy.

A generic HTTP or HTTPS proxy uses one URL for both schemes when the other is omitted:

```bash
export YOUTUBE_TRANSCRIPT_HTTP_PROXY="http://user:pass@proxy.example:8080"
export YOUTUBE_TRANSCRIPT_HTTPS_PROXY="http://user:pass@proxy.example:8080"
```

Flags: `--http-proxy`, `--https-proxy`.

Upstream proxy behavior is documented at <https://github.com/jdepoix/youtube-transcript-api>.

## Output shapes

`text` is caption lines separated by newlines. More than one video adds a `# <video-id>` heading before each transcript.

`json` is a list of objects:

```json
[
  {
    "video_id": "jNQXAC9IVRw",
    "language": "English",
    "language_code": "en",
    "is_generated": false,
    "snippets": [
      {"text": "hello", "start": 0.0, "duration": 1.5}
    ]
  }
]
```

`start` and `duration` are seconds. `pretty` prints those same objects with Python `pprint`. `srt` and `webvtt` are caption files from youtube-transcript-api.

`--list` ignores `--format` and `--translate`. Columns are `code`, `language`, `kind`, `translatable`.

## Video ids that start with a hyphen

```bash
python3 scripts/fetch_transcript.py -- "-abc1234567"
```
