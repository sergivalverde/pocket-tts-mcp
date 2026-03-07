# pocket-tts-mcp

MCP server for local text-to-speech using [Pocket TTS](https://github.com/kyutai-labs/pocket-tts) (Kyutai, 100M params).

Runs entirely on-device. No API keys, no cloud. Generates ~2.5 minutes of audio in ~20 seconds on Apple Silicon.

## Features

- **Single speaker** — 8 built-in voices (alba, marius, javert, etc.)
- **Two-speaker conversations** — tag scripts with `[S1]`/`[S2]`
- **30 emotional styles** — `[S1:happy]`, `[S2:sarcastic]`, etc.
- **Voice cloning** — point to a ~5s WAV reference
- **MP3 or WAV output**

## Install

### Claude Code

```bash
claude mcp add pocket-tts -- uvx --from /path/to/pocket-tts-mcp pocket-tts-mcp
```

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

### From PyPI (once published)

```bash
uvx pocket-tts-mcp
```

## Tools

| Tool | Description |
|------|-------------|
| `generate_speech` | Single-speaker TTS. Pass text and output path. |
| `generate_conversation` | Two-speaker TTS with `[S1]`/`[S2]` tags. |
| `list_voices` | Show available built-in voices. |
| `list_styles` | Show emotional/delivery styles for conversation scripts. |

## Requirements

- Python 3.11+
- ffmpeg (for audio concatenation and MP3 encoding)
- ~500MB disk for Pocket TTS model (downloaded on first run)

## Example

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
