<div align="center">

<img src="assets/hero.jpg" alt="A towering film frame in the dark, with light pouring out of it like a transcript" width="100%">

# youtube-transcript

**Paste a YouTube link. Get the words.**

A free agent skill for public captions. No API key. No browser. No credit meter.

[![MIT](https://img.shields.io/badge/license-MIT-111111?style=for-the-badge)](LICENSE)
[![API key](https://img.shields.io/badge/API%20key-none-111111?style=for-the-badge)](https://github.com/jdepoix/youtube-transcript-api)
[![command](https://img.shields.io/badge/command-%2Fyoutube--transcript-111111?style=for-the-badge)](skills/youtube-transcript/SKILL.md)

</div>

Hand an agent a video. It comes back with the transcript.

```text
Get the transcript for https://www.youtube.com/watch?v=jNQXAC9IVRw
```

```text
All right, so here we are, in front of the
elephants
the cool thing about these guys is that they
have really...
really really long trunks
and that's cool
```

That sample is the first video ever uploaded to YouTube. The skill fetched it from the public captions, on a laptop, with the command in this repo.

> [!TIP]
> Agents installing this skill: follow [Agent install](#agent-install) from top to bottom. Finish each verify command before the next step. The skill name is `youtube-transcript`. The slash command is `/youtube-transcript`.

## Install

Two commands. Then start a new agent session.

```bash
uv tool install youtube-transcript-api
npx -y skills add ringalls2020/youtube-transcript --skill youtube-transcript -g -y
```

The same install from the full URL:

```bash
npx -y skills add https://github.com/ringalls2020/youtube-transcript --skill youtube-transcript -g -y
```

`uv` missing? Use `pipx install youtube-transcript-api`. The command that must exist afterwards is `youtube_transcript_api`.

## Ask for any of these

| You say | You get |
| --- | --- |
| "Get the transcript for this URL" | The spoken words, one caption line at a time |
| "Give me timestamps" | JSON with `start` and `duration` in seconds |
| "Export captions" | An `.srt` or `.vtt` file |
| "What languages does this video have?" | A table of caption tracks |
| "Translate the captions to Spanish" | YouTube's own caption translation |
| `/youtube-transcript <url>` | The same fetch, from the slash command |

Paste a `youtube.com/watch` link, a `youtu.be` link, a Shorts link, or the 11-character video id. The agent extracts the id.

## What a fetch looks like

```bash
python3 skills/youtube-transcript/scripts/fetch_transcript.py \
  "https://www.youtube.com/watch?v=jNQXAC9IVRw"
```

Stdout is the transcript. Stderr is one status line:

```text
fetched jNQXAC9IVRw language=en kind=manual lines=6
```

| Flag | Result |
| --- | --- |
| *(none)* | Plain text |
| `--format json` | Text plus timestamps |
| `--format srt` | SubRip captions |
| `--format webvtt` | WebVTT captions |
| `--languages es en` | Try Spanish, then English |
| `--list` | Every available track |
| `--translate de` | Translate the chosen track to German |

Several URLs can go in one command. Text output for more than one video starts each transcript with `# <video-id>`.

## Where it runs

`npx skills` installs it for the agents it finds on the machine. These are the ones this repo is built against:

| Agent | Invoke it |
| --- | --- |
| Grok Build | `/youtube-transcript` |
| Claude Code | `/youtube-transcript` |
| Cursor | ask for the transcript |
| Codex | ask for the transcript |
| Gemini CLI | ask for the transcript |
| Cline, Warp, Zed | the skill in `~/.agents/skills` |

The procedure the agent follows is [`skills/youtube-transcript/SKILL.md`](skills/youtube-transcript/SKILL.md).

## What it will and will not do

| It will | It will not |
| --- | --- |
| Read manual and auto-generated captions | Download the video or the audio |
| Accept a URL or a video id | Search YouTube or list a channel |
| Run locally, with no account | Open private, members-only, or age-restricted videos |
| Translate a caption track YouTube already offers | Invent words that were not in the captions |

YouTube sometimes answers `IpBlocked` or `RequestBlocked`, mostly from cloud networks. The fetch script and the library still ran. Proxy setup is in [`skills/youtube-transcript/references/cli.md`](skills/youtube-transcript/references/cli.md).

## Agent install

### 1. Install the CLI

Install `youtube_transcript_api` so it is on `PATH` for every agent on the machine.

```bash
uv tool install youtube-transcript-api
```

Verify:

```bash
command -v youtube_transcript_api
youtube_transcript_api --version
```

Pass: the first command prints a path. The second prints `youtube_transcript_api, version` and a version number.

When `command -v` prints nothing and `uv tool install` succeeded, add `~/.local/bin` to `PATH` and open a new shell. uv puts the executable there.

When `uv` is missing, use the first command that exists:

```bash
pipx install youtube-transcript-api
python3 -m pip install --user youtube-transcript-api
```

The required command name is `youtube_transcript_api`.

### 2. Install the skill

Use one method. Source for both:

```text
ringalls2020/youtube-transcript
https://github.com/ringalls2020/youtube-transcript
```

#### Method A — skills CLI

Installs the skill for every agent the CLI detects on this machine.

```bash
npx -y skills add ringalls2020/youtube-transcript --skill youtube-transcript -g -y
```

One agent:

```bash
npx -y skills add ringalls2020/youtube-transcript --skill youtube-transcript -g -a grok -y
npx -y skills add ringalls2020/youtube-transcript --skill youtube-transcript -g -a claude-code -y
npx -y skills add ringalls2020/youtube-transcript --skill youtube-transcript -g -a cursor -y
npx -y skills add ringalls2020/youtube-transcript --skill youtube-transcript -g -a codex -y
npx -y skills add ringalls2020/youtube-transcript --skill youtube-transcript -g -a gemini-cli -y
```

Every agent the CLI knows about, including ones that are not installed:

```bash
npx -y skills add ringalls2020/youtube-transcript --skill youtube-transcript -g -a '*' -y
```

Pass: the command exits 0.

#### Method B — symlink

Use this when `npx` is unavailable. `<repo>` is the absolute path of a local clone. Create a parent directory only for an agent that is installed.

```bash
git clone https://github.com/ringalls2020/youtube-transcript.git
REPO="$PWD/youtube-transcript"
ln -sfn "$REPO/skills/youtube-transcript" "$HOME/.grok/skills/youtube-transcript"
ln -sfn "$REPO/skills/youtube-transcript" "$HOME/.claude/skills/youtube-transcript"
ln -sfn "$REPO/skills/youtube-transcript" "$HOME/.cursor/skills/youtube-transcript"
ln -sfn "$REPO/skills/youtube-transcript" "$HOME/.codex/skills/youtube-transcript"
ln -sfn "$REPO/skills/youtube-transcript" "$HOME/.gemini/skills/youtube-transcript"
ln -sfn "$REPO/skills/youtube-transcript" "$HOME/.agents/skills/youtube-transcript"
```

| Agent | Skill directory |
| --- | --- |
| Grok Build | `~/.grok/skills/youtube-transcript` |
| Claude Code | `~/.claude/skills/youtube-transcript` |
| Cursor | `~/.cursor/skills/youtube-transcript` |
| Codex | `~/.codex/skills/youtube-transcript` |
| Gemini CLI | `~/.gemini/skills/youtube-transcript` |
| Cline, Warp, Zed, and other consumers of `~/.agents/skills` | `~/.agents/skills/youtube-transcript` |

Other agents and their global skill paths are listed by `npx skills add --help` under supported agents. The folder to link is `skills/youtube-transcript`. The `name` in `SKILL.md` is `youtube-transcript` and matches that folder name.

Pass: `SKILL.md` exists at the destination.

```bash
test -f "$HOME/.grok/skills/youtube-transcript/SKILL.md"
test -f "$HOME/.claude/skills/youtube-transcript/SKILL.md"
test -f "$HOME/.agents/skills/youtube-transcript/SKILL.md"
```

Check the destinations for the agents installed on that machine. A missing agent directory is a skipped link, not a failed install.

### 3. Verify a fetch

From the repository root:

```bash
python3 skills/youtube-transcript/scripts/fetch_transcript.py "https://www.youtube.com/watch?v=jNQXAC9IVRw"
```

Pass: exit code 0. Stderr contains `fetched jNQXAC9IVRw`. Stdout contains `elephants`.

`IpBlocked` or `RequestBlocked` on stderr means the CLI and the script ran, and YouTube blocked this network. Configure a proxy from [`skills/youtube-transcript/references/cli.md`](skills/youtube-transcript/references/cli.md) and run the same command once more.

### 4. Load it in an agent

Start a new agent session so the skill list reloads. Ask:

```text
Get the transcript for https://www.youtube.com/watch?v=jNQXAC9IVRw
```

Or run `/youtube-transcript`.

Pass: the agent runs `skills/youtube-transcript/scripts/fetch_transcript.py` and returns the caption text from stdout.

## Repository layout

```text
skills/youtube-transcript/SKILL.md
skills/youtube-transcript/scripts/fetch_transcript.py
skills/youtube-transcript/references/cli.md
tests/test_fetch_transcript.py
```

## Tests

From the repository root:

```bash
uv run --with pytest python -m pytest
```

Pass: pytest exits 0.

## Uninstall

```bash
npx -y skills remove youtube-transcript -g -y
uv tool uninstall youtube-transcript-api
```

When the skill was linked by hand, remove those symlinks:

```bash
rm "$HOME/.grok/skills/youtube-transcript"
rm "$HOME/.claude/skills/youtube-transcript"
rm "$HOME/.cursor/skills/youtube-transcript"
rm "$HOME/.codex/skills/youtube-transcript"
rm "$HOME/.gemini/skills/youtube-transcript"
rm "$HOME/.agents/skills/youtube-transcript"
```

Remove a path only when it points at this skill.

## License

MIT. See [LICENSE](LICENSE).

Caption fetching is [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api) by jdepoix, also MIT. This repo is the agent skill and the URL-friendly script around that library.
