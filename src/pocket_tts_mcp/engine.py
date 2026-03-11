"""Core TTS engine using Pocket TTS (Kyutai, 100M params, fast local inference)."""

import os
import re
import shutil
import subprocess
import tempfile
import time

import numpy as np
import scipy.io.wavfile

SAMPLE_RATE = 24000

# Built-in voices
BUILTIN_VOICES = ["alba", "marius", "javert", "jean", "fantine", "cosette", "eponine", "azelma"]
DEFAULT_VOICE_S1 = "alba"
DEFAULT_VOICE_S2 = "azelma"
DEFAULT_TEMP = 0.9

# Pause durations (seconds)
PAUSE_SENTENCE = 0.55
PAUSE_PARAGRAPH = 1.0
PAUSE_TURN = 0.4
PAUSE_LEAD = 0.5
PAUSE_TRAIL = 0.4

# Voice styles directory (bundled with package)
VOICES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voices")

# Style registry: style_name -> relative path under VOICES_DIR
VOICE_STYLES = {
    # Alba MacKenna - same person, different delivery
    "casual": "alba-mackenna/casual.wav",
    "announcer": "alba-mackenna/announcer.wav",
    "merchant": "alba-mackenna/merchant.wav",
    "a-moment-by": "alba-mackenna/a-moment-by.wav",
    # Expresso ex03 - emotional range
    "angry": "expresso-ex03/angry.wav",
    "awe": "expresso-ex03/awe.wav",
    "calm": "expresso-ex03/calm.wav",
    "confused": "expresso-ex03/confused.wav",
    "desire": "expresso-ex03/desire.wav",
    "happy": "expresso-ex03/happy.wav",
    "laughing": "expresso-ex03/laughing.wav",
    "sarcastic": "expresso-ex03/sarcastic.wav",
    "sleepy": "expresso-ex03/sleepy.wav",
    # Expresso ex04 - second speaker emotional range
    "ex04-angry": "expresso-ex04/angry.wav",
    "ex04-awe": "expresso-ex04/awe.wav",
    "ex04-bored": "expresso-ex04/bored.wav",
    "ex04-calm": "expresso-ex04/calm.wav",
    "ex04-confused": "expresso-ex04/confused.wav",
    "ex04-desire": "expresso-ex04/desire.wav",
    "ex04-enunciated": "expresso-ex04/enunciated.wav",
    "ex04-fearful": "expresso-ex04/fearful.wav",
    "ex04-happy": "expresso-ex04/happy.wav",
    "ex04-laughing": "expresso-ex04/laughing.wav",
    "ex04-narration": "expresso-ex04/narration.wav",
    "ex04-sarcastic": "expresso-ex04/sarcastic.wav",
    # Podcast - cloned voices for two-speaker conversations
    "podcast-s1": "podcast/s1.wav",
    "podcast-s2": "podcast/s2.wav",
    "sergi": "podcast/sergi.wav",
    # Expresso ex01 - delivery styles
    "default": "expresso-ex01/default.wav",
    "enunciated": "expresso-ex01/enunciated.wav",
    "fast": "expresso-ex01/fast.wav",
    "projected": "expresso-ex01/projected.wav",
    "whisper": "expresso-ex01/whisper.wav",
}


def resolve_voice_style(style_name: str) -> str | None:
    """Resolve a style name to a local WAV path, or None if not found."""
    if style_name in VOICE_STYLES:
        path = os.path.join(VOICES_DIR, VOICE_STYLES[style_name])
        if os.path.exists(path):
            return path
    return None


def get_available_styles() -> dict[str, bool]:
    """Return all styles with availability status."""
    result = {}
    for name, rel_path in sorted(VOICE_STYLES.items()):
        full = os.path.join(VOICES_DIR, rel_path)
        result[name] = os.path.exists(full)
    return result


def split_into_chunks(text: str, max_chars: int = 300) -> list[tuple[str, bool]]:
    """Split text into chunks. Returns list of (text, is_paragraph_end) tuples."""
    paragraphs = re.split(r'\n\s*\n', text.strip())
    chunks = []

    for para_idx, paragraph in enumerate(paragraphs):
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        sentences = re.split(r'(?<=[.!?])\s+', paragraph)
        current = ""

        for sentence in sentences:
            if len(sentence) > max_chars:
                clause_parts = re.split(r'(?<=[,;:])\s+', sentence)
                for part in clause_parts:
                    if len(current) + len(part) + 1 > max_chars and current:
                        chunks.append((current.strip(), False))
                        current = part
                    else:
                        current = f"{current} {part}".strip() if current else part
            elif len(current) + len(sentence) + 1 > max_chars and current:
                chunks.append((current.strip(), False))
                current = sentence
            else:
                current = f"{current} {sentence}".strip() if current else sentence

        if current:
            is_last_para = (para_idx == len(paragraphs) - 1)
            chunks.append((current.strip(), not is_last_para))

    return chunks


def parse_conversation(text: str) -> list[tuple[str, str | None, str]]:
    """Parse [S1]/[S2]/[S1:style]/[S2:style] tagged text into turns.
    Returns list of (speaker, style_or_none, text) tuples."""
    turns = []
    pattern = re.compile(r'\[(S[12])(?::([a-zA-Z0-9_-]+))?\]\s*', re.MULTILINE)
    parts = pattern.split(text.strip())

    i = 1  # skip preamble
    while i < len(parts) - 2:
        speaker = parts[i]
        style = parts[i + 1]
        content = parts[i + 2].strip()
        if content:
            turns.append((speaker, style, content))
        i += 3

    return turns


def is_conversation(text: str) -> bool:
    """Check if text contains [S1]/[S2] conversation tags."""
    return bool(re.search(r'\[S[12](?::[a-zA-Z0-9_-]+)?\]', text))


def _generate_silence(filepath: str, duration_secs: float, sample_rate: int = SAMPLE_RATE):
    """Generate near-silent WAV using ffmpeg."""
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"anoisesrc=d={duration_secs}:c=white:r={sample_rate}:a=0.0001",
         "-ac", "1", "-c:a", "pcm_s16le", filepath],
        capture_output=True, check=True
    )


def _get_audio_duration(filepath: str) -> float:
    """Get duration of audio file in seconds using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", filepath],
            capture_output=True, text=True
        )
        return float(result.stdout.strip())
    except (ValueError, subprocess.CalledProcessError):
        return 0.0


def _apply_fade_in(audio_np: np.ndarray, sample_rate: int, fade_ms: int = 30) -> np.ndarray:
    """Apply fade-in to smooth silence-to-speech transition."""
    fade_samples = int(sample_rate * fade_ms / 1000)
    if len(audio_np) > fade_samples:
        fade_in = np.linspace(0, 1, fade_samples)
        audio_np[:fade_samples] = (audio_np[:fade_samples] * fade_in).astype(np.int16)
    return audio_np


def _to_int16(audio_np: np.ndarray) -> np.ndarray:
    """Convert audio array to int16."""
    if audio_np.dtype != np.int16:
        return (np.clip(audio_np, -1.0, 1.0) * 32767).astype(np.int16)
    return audio_np


def _concat_segments(segments: list[str], output_path: str, tmpdir: str):
    """Concatenate WAV segments into final output (MP3 or WAV)."""
    concat_list = os.path.join(tmpdir, "concat.txt")
    with open(concat_list, "w") as f:
        for seg in segments:
            f.write(f"file '{seg}'\n")

    wants_mp3 = output_path.lower().endswith(".mp3")
    if wants_mp3:
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
               "-i", concat_list, "-codec:a", "libmp3lame", "-q:a", "2", output_path]
    else:
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
               "-i", concat_list, "-c", "copy", output_path]

    subprocess.run(cmd, capture_output=True, check=True)


def generate_speech(
    text: str,
    output_path: str,
    voice: str = DEFAULT_VOICE_S1,
    voice_ref: str | None = None,
    temperature: float = DEFAULT_TEMP,
) -> dict:
    """Generate single-speaker audio.

    Args:
        text: Text to synthesize.
        output_path: Where to save the audio (.mp3 or .wav).
        voice: Built-in voice name (alba, marius, javert, etc.).
        voice_ref: Path to a ~5s WAV for voice cloning. Overrides voice.
        temperature: Generation temperature (0.0-1.5, default 0.9).

    Returns:
        Dict with output path, duration, chunk count, and generation time.
    """
    from pocket_tts import TTSModel

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    chunks = split_into_chunks(text)
    t0 = time.time()

    model = TTSModel.load_model(temp=temperature)

    if voice_ref and os.path.exists(voice_ref):
        voice_state = model.get_state_for_audio_prompt(voice_ref)
    else:
        voice_name = voice if voice in BUILTIN_VOICES else DEFAULT_VOICE_S1
        voice_state = model.get_state_for_audio_prompt(voice_name)

    tmpdir = tempfile.mkdtemp(prefix="tts_pocket_")
    segments = []

    short_pause = os.path.join(tmpdir, "short.wav")
    long_pause = os.path.join(tmpdir, "long.wav")
    lead_silence = os.path.join(tmpdir, "lead.wav")
    trail_silence = os.path.join(tmpdir, "trail.wav")
    _generate_silence(short_pause, PAUSE_SENTENCE, model.sample_rate)
    _generate_silence(long_pause, PAUSE_PARAGRAPH, model.sample_rate)
    _generate_silence(lead_silence, PAUSE_LEAD, model.sample_rate)
    _generate_silence(trail_silence, PAUSE_TRAIL, model.sample_rate)

    segments.append(lead_silence)

    for i, (chunk_text, is_para_end) in enumerate(chunks):
        audio = model.generate_audio(voice_state, chunk_text)
        audio_np = _apply_fade_in(_to_int16(audio.numpy()), model.sample_rate)

        seg_path = os.path.join(tmpdir, f"chunk_{i:03d}.wav")
        scipy.io.wavfile.write(seg_path, model.sample_rate, audio_np)
        segments.append(seg_path)

        if i < len(chunks) - 1:
            segments.append(long_pause if is_para_end else short_pause)

    segments.append(trail_silence)

    output_path = os.path.abspath(output_path)
    _concat_segments(segments, output_path, tmpdir)
    shutil.rmtree(tmpdir, ignore_errors=True)

    duration = _get_audio_duration(output_path)
    elapsed = time.time() - t0

    return {
        "output": output_path,
        "duration_seconds": round(duration, 1),
        "chunks": len(chunks),
        "generation_time_seconds": round(elapsed, 1),
    }


def generate_conversation(
    text: str,
    output_path: str,
    voice1: str = DEFAULT_VOICE_S1,
    voice2: str = DEFAULT_VOICE_S2,
    voice_ref1: str | None = None,
    voice_ref2: str | None = None,
    temperature1: float = DEFAULT_TEMP,
    temperature2: float = DEFAULT_TEMP,
) -> dict:
    """Generate two-speaker conversation audio.

    Text must contain [S1]/[S2] or [S1:style]/[S2:style] tags.

    Args:
        text: Conversation script with speaker tags.
        output_path: Where to save the audio (.mp3 or .wav).
        voice1/voice2: Built-in voice names for each speaker.
        voice_ref1/voice_ref2: WAV paths for voice cloning per speaker.
        temperature1/temperature2: Generation temperature per speaker.

    Returns:
        Dict with output path, duration, turn count, and generation time.
    """
    from pocket_tts import TTSModel

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    turns = parse_conversation(text)
    if not turns:
        raise ValueError("No [S1]/[S2] tags found in text")

    t0 = time.time()

    model1 = TTSModel.load_model(temp=temperature1)
    model2 = TTSModel.load_model(temp=temperature2)

    v1_name = voice1 if voice1 in BUILTIN_VOICES else DEFAULT_VOICE_S1
    v2_name = voice2 if voice2 in BUILTIN_VOICES else DEFAULT_VOICE_S2

    if voice_ref1 and os.path.exists(voice_ref1):
        default_state1 = model1.get_state_for_audio_prompt(voice_ref1)
    else:
        default_state1 = model1.get_state_for_audio_prompt(v1_name)

    if voice_ref2 and os.path.exists(voice_ref2):
        default_state2 = model2.get_state_for_audio_prompt(voice_ref2)
    else:
        default_state2 = model2.get_state_for_audio_prompt(v2_name)

    # Pre-cache voice states for styles used in script
    style_cache = {}
    for speaker, style, _ in turns:
        if style and (speaker, style) not in style_cache:
            model = model1 if speaker == "S1" else model2
            style_path = resolve_voice_style(style)
            if style_path:
                style_cache[(speaker, style)] = model.get_state_for_audio_prompt(style_path)

    tmpdir = tempfile.mkdtemp(prefix="tts_conv_")
    segments = []
    sr = model1.sample_rate

    turn_pause_path = os.path.join(tmpdir, "turn.wav")
    sentence_pause_path = os.path.join(tmpdir, "short.wav")
    lead_silence = os.path.join(tmpdir, "lead.wav")
    trail_silence = os.path.join(tmpdir, "trail.wav")
    _generate_silence(turn_pause_path, PAUSE_TURN, sr)
    _generate_silence(sentence_pause_path, PAUSE_SENTENCE, sr)
    _generate_silence(lead_silence, PAUSE_LEAD, sr)
    _generate_silence(trail_silence, PAUSE_TRAIL, sr)

    segments.append(lead_silence)
    chunk_idx = 0

    for t_idx, (speaker, style, turn_text) in enumerate(turns):
        model = model1 if speaker == "S1" else model2

        if style and (speaker, style) in style_cache:
            state = style_cache[(speaker, style)]
        else:
            state = default_state1 if speaker == "S1" else default_state2

        turn_chunks = split_into_chunks(turn_text)

        for c_idx, (chunk_text, _is_para_end) in enumerate(turn_chunks):
            audio = model.generate_audio(state, chunk_text)
            audio_np = _apply_fade_in(_to_int16(audio.numpy()), sr)

            seg_path = os.path.join(tmpdir, f"chunk_{chunk_idx:03d}.wav")
            scipy.io.wavfile.write(seg_path, sr, audio_np)
            segments.append(seg_path)
            chunk_idx += 1

            if c_idx < len(turn_chunks) - 1:
                segments.append(sentence_pause_path)

        if t_idx < len(turns) - 1:
            segments.append(turn_pause_path)

    segments.append(trail_silence)

    output_path = os.path.abspath(output_path)
    _concat_segments(segments, output_path, tmpdir)
    shutil.rmtree(tmpdir, ignore_errors=True)

    duration = _get_audio_duration(output_path)
    elapsed = time.time() - t0

    return {
        "output": output_path,
        "duration_seconds": round(duration, 1),
        "turns": len(turns),
        "chunks": chunk_idx,
        "generation_time_seconds": round(elapsed, 1),
    }
