"""MCP server for local text-to-speech using Pocket TTS."""

import json
import os

from mcp.server.fastmcp import FastMCP

from . import engine

mcp = FastMCP(
    "pocket-tts",
    instructions="Local text-to-speech using Pocket TTS (Kyutai, 100M params). "
    "Generates speech from text with multiple voices, emotional styles, "
    "and two-speaker conversation support. Runs entirely on-device.",
)


@mcp.tool()
def generate_speech(
    text: str,
    output_path: str,
    voice: str = "alba",
    voice_ref: str = "",
    temperature: float = 0.9,
) -> str:
    """Generate single-speaker audio from text.

    Args:
        text: The text to convert to speech. For best results, keep under 2000 words.
        output_path: Absolute path where to save the audio file (.mp3 or .wav).
        voice: Built-in voice name. Options: alba, marius, javert, jean, fantine, cosette, eponine, azelma.
        voice_ref: Optional absolute path to a ~5 second WAV file for voice cloning. Overrides the voice parameter.
        temperature: Controls voice variation (0.0=deterministic, 1.5=very varied). Default 0.9.
    """
    result = engine.generate_speech(
        text=text,
        output_path=output_path,
        voice=voice,
        voice_ref=voice_ref or None,
        temperature=temperature,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def generate_conversation(
    text: str,
    output_path: str,
    voice1: str = "alba",
    voice2: str = "azelma",
    voice_ref1: str = "",
    voice_ref2: str = "",
    temperature1: float = 0.9,
    temperature2: float = 0.9,
) -> str:
    """Generate two-speaker conversation audio from a tagged script.

    The text must use [S1] and [S2] tags to mark speaker turns.
    Optionally use [S1:style] or [S2:style] for emotional variation.

    Example script:
        [S1]
        So I've been reading about this new framework.
        [S2:awe]
        Wait, really? Tell me more.
        [S1:calm]
        The core idea is surprisingly simple.

    Args:
        text: Conversation script with [S1]/[S2] speaker tags.
        output_path: Absolute path where to save the audio file (.mp3 or .wav).
        voice1: Built-in voice for speaker 1. Default: alba.
        voice2: Built-in voice for speaker 2. Default: azelma.
        voice_ref1: Optional WAV path for S1 voice cloning.
        voice_ref2: Optional WAV path for S2 voice cloning.
        temperature1: Temperature for speaker 1 (default 0.9).
        temperature2: Temperature for speaker 2 (default 0.9).
    """
    result = engine.generate_conversation(
        text=text,
        output_path=output_path,
        voice1=voice1,
        voice2=voice2,
        voice_ref1=voice_ref1 or None,
        voice_ref2=voice_ref2 or None,
        temperature1=temperature1,
        temperature2=temperature2,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def list_voices() -> str:
    """List all available built-in voices and their descriptions."""
    voices = {
        "alba": "Female, clear narrator (default S1)",
        "azelma": "Female (default S2)",
        "marius": "Male",
        "javert": "Male",
        "jean": "Male",
        "fantine": "Female",
        "cosette": "Female",
        "eponine": "Female",
    }
    return json.dumps(voices, indent=2)


@mcp.tool()
def list_styles() -> str:
    """List all available emotional/delivery styles for per-turn voice switching.

    Use these with [S1:style] or [S2:style] tags in conversation scripts.
    Styles change the voice timbre via cloning — they're different reference
    recordings. Use sparingly for emotional emphasis.
    """
    styles = engine.get_available_styles()
    groups = {
        "alba-mackenna (delivery)": {},
        "expresso-ex03 (emotions)": {},
        "expresso-ex04 (emotions)": {},
        "expresso-ex01 (delivery)": {},
    }
    for name, available in styles.items():
        if name in ("casual", "announcer", "merchant", "a-moment-by"):
            groups["alba-mackenna (delivery)"][name] = available
        elif name.startswith("ex04-"):
            groups["expresso-ex04 (emotions)"][name] = available
        elif name in ("default", "enunciated", "fast", "projected", "whisper"):
            groups["expresso-ex01 (delivery)"][name] = available
        else:
            groups["expresso-ex03 (emotions)"][name] = available

    return json.dumps(groups, indent=2)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
