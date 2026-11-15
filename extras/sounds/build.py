"""Builds Bastion's alarm sounds (synthesized, no third-party audio).

    python3 extras/sounds/build.py      (needs ffmpeg with libmp3lame)

Output: custom_components/bastion/frontend/sounds/*.mp3
"""

from __future__ import annotations

import math
from pathlib import Path
import struct
import subprocess
import tempfile
import wave

RATE = 44100
OUT = Path(__file__).resolve().parents[2] / "custom_components" / "bastion" / "frontend" / "sounds"


def tone(freq, seconds, *, harmonics=(1.0,), decay=0.0, volume=0.8):
    """Samples of a tone; freq may be a function of time for sweeps."""
    n = int(RATE * seconds)
    out = []
    phase = 0.0
    for i in range(n):
        t = i / RATE
        f = freq(t) if callable(freq) else freq
        phase += 2 * math.pi * f / RATE
        s = sum(a * math.sin(phase * (k * 2 + 1)) / (k * 2 + 1) for k, a in enumerate(harmonics))
        env = math.exp(-decay * t) if decay else 1.0
        fade = min(1.0, i / (RATE * 0.005), (n - i) / (RATE * 0.005))
        out.append(s * env * fade * volume)
    peak = max(1e-9, max(abs(x) for x in out))
    return [x / peak * volume for x in out]


def silence(seconds):
    return [0.0] * int(RATE * seconds)


def siren():
    # Wailing siren: 1.5 s up, 1.5 s down, twice; odd harmonics for a harsh, loud timbre.
    half = 1.5
    sweep = lambda t: 650 + 750 * (t / half if t < half else 2 - t / half)  # noqa: E731
    cycle = tone(sweep, 2 * half, harmonics=(1.0, 0.45, 0.25, 0.12), volume=0.95)
    return cycle * 2


def entry():
    # Urgent double beep every second: entry delay running.
    beep = tone(2800, 0.11, harmonics=(1.0, 0.3), volume=0.9)
    second = beep + silence(0.07) + beep
    return (second + silence(1.0 - len(second) / RATE)) * 10


def exit_():
    # Calm single beep every second: exit delay running.
    beep = tone(2000, 0.14, harmonics=(1.0, 0.2), volume=0.75)
    return (beep + silence(1.0 - len(beep) / RATE)) * 10


def chime(notes):
    out = []
    for f in notes:
        out += (
            tone(f, 0.55, harmonics=(1.0, 0.15, 0.05), decay=5.5, volume=0.7)[: int(RATE * 0.22)]
            if f != notes[-1]
            else tone(f, 0.9, harmonics=(1.0, 0.15, 0.05), decay=4.0, volume=0.7)
        )
    return silence(0.1) + out + silence(0.2)


SOUNDS = {
    "siren": siren,
    "entry": entry,
    "exit": exit_,
    "armed": lambda: chime([1046.5, 1318.5, 1568.0]),  # C6 E6 G6, rising
    "disarmed": lambda: chime([1568.0, 1046.5]),  # G6 C6, falling
}


def write_mp3(name, samples):
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / f"{name}.wav"
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32000)) for s in samples))
        OUT.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(wav),
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "96k",
                "-ac",
                "1",
                "-map_metadata",
                "-1",
                str(OUT / f"{name}.mp3"),
            ],
            check=True,
        )


if __name__ == "__main__":
    for name, build in SOUNDS.items():
        write_mp3(name, build())
        print(name, (OUT / f"{name}.mp3").stat().st_size)
