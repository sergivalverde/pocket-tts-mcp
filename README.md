# pocket-tts-mcp

MCP server for local text-to-speech using [Pocket TTS](https://github.com/kyutai-labs/pocket-tts) (Kyutai, 100M params).

Runs entirely on-device. No API keys, no cloud. Generates ~2.5 minutes of audio in ~20 seconds on Apple Silicon.

## Quick Start (Claude Code)

```bash
claude mcp add pocket-tts -- uvx --from git+https://github.com/sergivalverde/pocket-tts-mcp pocket-tts-mcp
```

Or from a local clone:

```bash
git clone https://github.com/sergivalverde/pocket-tts-mcp.git
claude mcp add pocket-tts -- uvx --from ./pocket-tts-mcp pocket-tts-mcp
```

That's it. The tools are now available in your Claude Code session.

### Prerequisites

- Python 3.11+
- ffmpeg (`brew install ffmpeg`)
- ~500MB disk for the Pocket TTS model (downloaded on first run)

## Tools

| Tool | Description |
|------|-------------|
| `generate_speech` | Single-speaker TTS. Pass text and an output path (.mp3 or .wav). |
| `generate_conversation` | Two-speaker TTS with `[S1]`/`[S2]` tags and optional per-turn styles. |
| `list_voices` | Show available built-in voices. |
| `list_styles` | Show emotional/delivery styles including bundled podcast clones. |

## Features

- **8 built-in voices** — alba, marius, javert, jean, fantine, cosette, eponine, azelma
- **Two-speaker conversations** — tag scripts with `[S1]`/`[S2]`
- **30+ styles** — emotional (`happy`, `sarcastic`, `calm`) and delivery (`whisper`, `fast`, `enunciated`)
- **Podcast voices** — bundled cloned voices (`podcast-s1`, `podcast-s2`) for natural-sounding dialogues
- **Voice cloning** — point `voice_ref` to any ~5s WAV to clone a voice
- **MP3 or WAV output**

## Example

### Single speaker

```
Generate speech from this text and save to /tmp/output.mp3
```

### Two-speaker conversation

```
[S1]
So I've been reading about this compound engineering thing.

[S2:awe]
Wait, they really have all their code written by AI?

[S1:calm]
Yeah, and the system gets smarter over time.

[S2:sarcastic]
Oh great, so eventually the developers won't even need to show up.
```

### Using podcast voices

Use the bundled podcast clones as styles:

```
[S1:podcast-s1]
Welcome back to the show. Today we're covering something wild.

[S2:podcast-s2]
I've been looking forward to this one. Let's get into it.
```

## Other Integrations

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "pocket-tts": {
      "command": "uvx",
      "args": ["--from", "/path/to/pocket-tts-mcp", "pocket-tts-mcp"]
    }
  }
}
```

## License

MIT
