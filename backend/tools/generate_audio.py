"""Turns the call scripts into stereo audio using ElevenLabs.

Usage, from the backend folder:
  uv run python -m tools.generate_audio                  generate missing calls
  uv run python -m tools.generate_audio --call <id>      only this call
  uv run python -m tools.generate_audio --force          replace existing audio

This spends ElevenLabs credits, so existing audio is skipped unless --force is
used. It also saves word timings now, so that later stages never need to pay
to regenerate them.
"""

import argparse
import base64
import json
import sys
import wave
from array import array

import httpx

from app.calls import GENERATED_DIR, audio_path, load_scripts, timing_path
from app.config import settings

TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
END_SILENCE_SECONDS = 0.5


def synthesize(client: httpx.Client, text: str, voice_id: str) -> tuple[array, dict]:
    """Return one turn's mono 16-bit samples and its character timings."""
    response = client.post(
        TTS_URL.format(voice_id=voice_id),
        params={"output_format": f"pcm_{settings.audio_sample_rate}"},
        headers={"xi-api-key": settings.elevenlabs_api_key},
        json={"text": text, "model_id": settings.tts_model},
    )
    if response.status_code != 200:
        sys.exit(f"ElevenLabs error {response.status_code}: {response.text[:500]}")

    body = response.json()
    samples = array("h")
    samples.frombytes(base64.b64decode(body["audio_base64"]))
    return samples, body["alignment"]


def words_from_alignment(alignment: dict, offset: float) -> list[dict]:
    """Group character timings into words, shifted to call time by offset."""
    words = []
    current = None
    characters = zip(
        alignment["characters"],
        alignment["character_start_times_seconds"],
        alignment["character_end_times_seconds"],
    )
    for character, start, end in characters:
        if character.isspace():
            current = None
        elif current is None:
            current = {"word": character, "start": start + offset, "end": end + offset}
            words.append(current)
        else:
            current["word"] += character
            current["end"] = end + offset

    for word in words:
        word["start"] = round(word["start"], 3)
        word["end"] = round(word["end"], 3)
    return words


def generate_call(client: httpx.Client, script: dict) -> None:
    rate = settings.audio_sample_rate
    voices = {
        "caller": settings.tts_caller_voice_id,
        "user": settings.tts_user_voice_id,
    }

    # Place each turn on the timeline first. A negative gap makes a turn start
    # before the previous one ends, which is how interruptions are created.
    clips = []
    turns = []
    cursor = 0
    for turn in script["turns"]:
        samples, alignment = synthesize(client, turn["text"], voices[turn["speaker"]])
        gap_ms = turn.get("gap_ms", settings.tts_default_gap_ms) if clips else 0
        start = max(0, cursor + int(gap_ms * rate / 1000))
        end = start + len(samples)
        cursor = max(cursor, end)
        clips.append((turn["speaker"], start, samples))
        turns.append(
            {
                **turn,
                "start": round(start / rate, 3),
                "end": round(end / rate, 3),
                "words": words_from_alignment(alignment, start / rate),
            }
        )
        print(f"  {turn['speaker']:<6} {start / rate:6.1f}s  {turn['text'][:50]}")

    # Each speaker gets their own channel, then the two are interleaved.
    total = cursor + int(END_SILENCE_SECONDS * rate)
    channels = {"caller": array("h", bytes(total * 2)), "user": array("h", bytes(total * 2))}
    for speaker, start, samples in clips:
        channels[speaker][start : start + len(samples)] = samples

    stereo = array("h", bytes(total * 4))
    stereo[0::2] = channels["caller"]
    stereo[1::2] = channels["user"]

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    with wave.open(str(audio_path(script["id"])), "wb") as wav:
        wav.setnchannels(settings.audio_channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(stereo.tobytes())

    timing = {
        "id": script["id"],
        "title": script["title"],
        "label": script["label"],
        "duration_seconds": round(total / rate, 3),
        "sample_rate": rate,
        "channels": settings.audio_channels,
        "turns": turns,
    }
    timing_path(script["id"]).write_text(json.dumps(timing, indent=2) + "\n")
    print(f"  saved, {total / rate:.1f} seconds")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--call", help="only generate this call id")
    parser.add_argument("--force", action="store_true", help="replace existing audio")
    args = parser.parse_args()

    if not settings.elevenlabs_api_key:
        sys.exit("Set ELEVENLABS_API_KEY in backend/.env first.")

    scripts = load_scripts()
    if args.call:
        scripts = [script for script in scripts if script["id"] == args.call]
        if not scripts:
            sys.exit(f"No script with id {args.call}")

    with httpx.Client(timeout=120) as client:
        for script in scripts:
            if audio_path(script["id"]).exists() and not args.force:
                print(f"{script['id']}: already generated, skipping")
                continue
            print(f"{script['id']}:")
            generate_call(client, script)


if __name__ == "__main__":
    main()
