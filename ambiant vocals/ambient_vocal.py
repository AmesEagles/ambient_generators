"""A small, dependency-free ambient music generator with a Tkinter interface."""

from __future__ import annotations

import math
import os
import random
import vocal_engine
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import wave
from array import array
from queue import Empty, Full, Queue
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk
import re

from vocal_engine import SAMPLE_RATE as VOCAL_SAMPLE_RATE, synthesize as synthesize_vocal


SAMPLE_RATE = 16_000
VOCAL_ENABLED_SECTIONS = (0, 2, 5)
SECTION_BARS = 4
MAX_VOICE_DETUNE = 0.004
SONG_FORM = ("Verse", "Chorus", "Verse", "Chorus", "Bridge", "Final Chorus")
DEFAULT_LYRICS = {
    "Dreamy": ("Drift beneath the quiet sky", "Soft light carries us home", "We float where the stars glow"),
    "Peaceful": ("Morning moves across the lake", "Gentle light is finding us", "Rest here in the open air"),
    "Melancholic": ("Fading lights remember us", "Footsteps echo through the rain", "Still your song remains with me"),
    "Hopeful": ("We rise into the open light", "Every road can lead us home", "Together we begin again"),
    "Mysterious": ("Shadows turn beneath the moon", "Quiet doors are opening", "Follow where the blue lights go"),
    "Warm": ("Golden hours fill the room", "Easy roads are winding home", "Stay beside me through the night"),
    "Cosmic": ("Silver rivers cross the sky", "Orbit where the new stars rise", "We are moving through the blue"),
    "Dark": ("Low clouds cover distant roads", "Hear the thunder in the deep", "Keep a spark beneath the stone"),
    "Nostalgic": ("Old photographs remember", "Summer hums across the years", "Somewhere we are young again"),
    "Tense": ("Every signal pulls us close", "Hear the current underneath", "Hold the line until it breaks"),
    "Radiant": ("We awaken in the light", "Bright horizons call us on", "Every color opens wide"),
    "Weightless": ("Slowly turning through the blue", "No horizon holding us", "We are weightless in the glow"),
}
KEYS = {
    "C": 0, "C#": 1, "D": 2, "Eb": 3, "E": 4, "F": 5,
    "F#": 6, "G": 7, "Ab": 8, "A": 9, "Bb": 10, "B": 11,
}
SCALES = {
    "major": (0, 2, 4, 5, 7, 9, 11),
    "natural minor": (0, 2, 3, 5, 7, 8, 10),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "lydian": (0, 2, 4, 6, 7, 9, 11),
    "mixolydian": (0, 2, 4, 5, 7, 9, 10),
}

# Progressions are scale degrees: each chord takes its notes from the selected scale.
# Profiles also act as a compact sound-design database for the ambient instruments.
MOODS = {
    "Dreamy": {
        "scale": "major", "tempo": (58, 76), "progressions": ((1, 5, 6, 4), (1, 3, 4, 4), (6, 4, 1, 5), (1, 4, 6, 3), (4, 1, 5, 6)),
        "pad": 0.28, "bass": 0.10, "melody": 0.075, "brightness": 0.22, "detune": 0.010,
        "attack": 1.8, "release": 2.2, "echo": 0.23, "pulse": 0.025,
        "patches": ("soft_strings", "rounded_sub", "glass_bell", "airy_chime"), "texture": 0.035,
        "rhythm_patches": ("soft_mallet", "bell_tree", "soft_flute"),
        "rhythm_patterns": ((0.5, 1.5, 2.5, 3.5), (1.5, 3.5), (0.5, 2.5)),
        "rhythm_probability": 0.72,
        "description": "soft, floating pads with distant bell tones",
    },
    "Peaceful": {
        "scale": "major", "tempo": (54, 70), "progressions": ((1, 4, 1, 5), (1, 5, 4, 1), (4, 1, 5, 1), (1, 6, 4, 5), (4, 6, 1, 5)),
        "pad": 0.30, "bass": 0.11, "melody": 0.055, "brightness": 0.16, "detune": 0.006,
        "attack": 2.2, "release": 2.6, "echo": 0.18, "pulse": 0.012,
        "patches": ("warm_analog", "rounded_sub", "soft_flute", "air_choir"), "texture": 0.045,
        "rhythm_patches": ("tape_keys", "soft_mallet", "soft_flute"),
        "rhythm_patterns": ((1.5, 3.5), (0.5, 2.5), (1.5,)),
        "rhythm_probability": 0.42,
        "description": "warm, slow-moving pads and a gentle low foundation",
    },
    "Melancholic": {
        "scale": "natural minor", "tempo": (58, 78), "progressions": ((1, 6, 3, 7), (1, 4, 6, 5), (6, 4, 1, 5), (1, 3, 6, 4), (4, 1, 7, 6)),
        "pad": 0.29, "bass": 0.12, "melody": 0.085, "brightness": 0.19, "detune": 0.009,
        "attack": 1.5, "release": 2.0, "echo": 0.24, "pulse": 0.018,
        "patches": ("hollow_choir", "analog_bass", "glass_bell", "slow_strings"), "texture": 0.030,
        "rhythm_patches": ("dusty_pluck", "pizzicato", "tape_keys"),
        "rhythm_patterns": ((1.5, 3.5), (0.5, 2.5, 3.5), (1.5,)),
        "rhythm_probability": 0.52,
        "description": "wistful minor chords, dark pads, and a sparse lead",
    },
    "Hopeful": {
        "scale": "major", "tempo": (66, 88), "progressions": ((1, 5, 4, 1), (1, 4, 6, 5), (4, 5, 1, 6), (1, 6, 2, 5), (4, 1, 3, 5)),
        "pad": 0.25, "bass": 0.12, "melody": 0.095, "brightness": 0.28, "detune": 0.007,
        "attack": 1.1, "release": 1.8, "echo": 0.16, "pulse": 0.035,
        "patches": ("soft_strings", "mellow_bass", "soft_flute", "air_choir"), "texture": 0.040,
        "rhythm_patches": ("wooden_tine", "soft_mallet", "pizzicato"),
        "rhythm_patterns": ((0.5, 1.5, 2.5, 3.5), (0.5, 2.5), (1.5, 2.5, 3.5)),
        "rhythm_probability": 0.78,
        "description": "open major harmonies with a softly rising melody",
    },
    "Mysterious": {
        "scale": "dorian", "tempo": (56, 76), "progressions": ((1, 4, 2, 1), (1, 7, 4, 1), (2, 1, 6, 4), (1, 3, 4, 2), (4, 2, 1, 7)),
        "pad": 0.28, "bass": 0.14, "melody": 0.060, "brightness": 0.14, "detune": 0.012,
        "attack": 2.0, "release": 2.4, "echo": 0.30, "pulse": 0.020,
        "patches": ("dark_drone", "rounded_sub", "muted_pluck", "air_choir"), "texture": 0.050,
        "rhythm_patches": ("water_drop", "dusty_pluck", "bell_tree"),
        "rhythm_patterns": ((1.5,), (0.5, 3.5), (2.5,)),
        "rhythm_probability": 0.55,
        "description": "hushed modal pads, deep bass, and long echoes",
    },
    "Warm": {
        "scale": "mixolydian", "tempo": (60, 82), "progressions": ((1, 7, 4, 1), (1, 4, 7, 1), (4, 1, 7, 4), (1, 4, 5, 7), (4, 5, 1, 7)),
        "pad": 0.30, "bass": 0.15, "melody": 0.065, "brightness": 0.20, "detune": 0.005,
        "attack": 1.5, "release": 2.0, "echo": 0.15, "pulse": 0.028,
        "patches": ("warm_analog", "analog_bass", "soft_flute", "slow_strings"), "texture": 0.035,
        "rhythm_patches": ("tape_keys", "wooden_tine", "pizzicato"),
        "rhythm_patterns": ((0.5, 2.5, 3.5), (1.5, 3.5), (0.5, 1.5, 2.5, 3.5)),
        "rhythm_probability": 0.68,
        "description": "rounded analog-style pads with a mellow bass line",
    },
    "Cosmic": {
        "scale": "lydian", "tempo": (62, 82), "progressions": ((1, 2, 5, 1), (1, 5, 2, 4), (4, 2, 1, 5), (1, 4, 2, 5), (2, 5, 1, 4)),
        "pad": 0.27, "bass": 0.09, "melody": 0.080, "brightness": 0.31, "detune": 0.013,
        "attack": 2.0, "release": 2.5, "echo": 0.32, "pulse": 0.022,
        "patches": ("crystal_pad", "rounded_sub", "airy_chime", "air_choir"), "texture": 0.060,
        "rhythm_patches": ("bell_tree", "soft_mallet", "water_drop"),
        "rhythm_patterns": ((0.5, 1.5, 2.5, 3.5), (1.5, 2.5), (0.5, 3.5)),
        "rhythm_probability": 0.70,
        "description": "shimmering high tones over wide, airy synth pads",
    },
    "Dark": {
        "scale": "natural minor", "tempo": (52, 72), "progressions": ((1, 7, 6, 1), (1, 4, 7, 6), (6, 7, 1, 1), (1, 6, 4, 7), (4, 1, 6, 7)),
        "pad": 0.30, "bass": 0.16, "melody": 0.045, "brightness": 0.11, "detune": 0.008,
        "attack": 2.1, "release": 2.6, "echo": 0.26, "pulse": 0.014,
        "patches": ("dark_drone", "rounded_sub", "muted_pluck", "slow_strings"), "texture": 0.025,
        "rhythm_patches": ("water_drop", "dusty_pluck", "muted_pluck"),
        "rhythm_patterns": ((1.5, 3.5), (2.5,), (0.5, 3.5)),
        "rhythm_probability": 0.36,
        "description": "low, shadowy drones with restrained upper notes",
    },
    "Nostalgic": {
        "scale": "natural minor", "tempo": (58, 78), "progressions": ((1, 6, 3, 7), (4, 1, 6, 5), (1, 4, 6, 3), (6, 4, 1, 5), (1, 3, 7, 4)),
        "pad": 0.27, "bass": 0.12, "melody": 0.090, "brightness": 0.21, "detune": 0.009,
        "attack": 1.7, "release": 2.2, "echo": 0.21, "pulse": 0.018,
        "patches": ("soft_strings", "mellow_bass", "glass_bell", "air_choir"), "texture": 0.035,
        "rhythm_patches": ("tape_keys", "pizzicato", "soft_mallet"),
        "rhythm_patterns": ((0.5, 2.5, 3.5), (1.5, 3.5), (0.5, 1.5, 2.5, 3.5)),
        "rhythm_probability": 0.63,
        "description": "tape-warm strings and tender, wistful melodies",
    },
    "Tense": {
        "scale": "dorian", "tempo": (60, 84), "progressions": ((1, 2, 4, 1), (1, 4, 7, 2), (6, 2, 1, 4), (1, 7, 2, 4), (4, 1, 6, 2)),
        "pad": 0.26, "bass": 0.16, "melody": 0.055, "brightness": 0.17, "detune": 0.016,
        "attack": 1.3, "release": 1.8, "echo": 0.22, "pulse": 0.032,
        "patches": ("hollow_choir", "analog_bass", "muted_pluck", "slow_strings"), "texture": 0.030,
        "rhythm_patches": ("dusty_pluck", "wooden_tine", "water_drop"),
        "rhythm_patterns": ((0.5, 1.5, 2.5, 3.5), (1.5, 3.5), (0.5, 2.5, 3.5)),
        "rhythm_probability": 0.82,
        "description": "unsettled modal harmonies with a restrained pulsing low end",
    },
    "Radiant": {
        "scale": "lydian", "tempo": (68, 90), "progressions": ((1, 2, 5, 4), (1, 5, 2, 1), (4, 1, 2, 5), (1, 4, 5, 2), (2, 1, 5, 4)),
        "pad": 0.25, "bass": 0.10, "melody": 0.085, "brightness": 0.32, "detune": 0.010,
        "attack": 1.4, "release": 2.1, "echo": 0.24, "pulse": 0.024,
        "patches": ("crystal_pad", "rounded_sub", "airy_chime", "air_choir"), "texture": 0.055,
        "rhythm_patches": ("bell_tree", "wooden_tine", "water_drop"),
        "rhythm_patterns": ((0.5, 1.5, 2.5, 3.5), (0.5, 2.5), (1.5, 2.5, 3.5)),
        "rhythm_probability": 0.86,
        "description": "bright, open chords and sparkling high synths",
    },
    "Weightless": {
        "scale": "major", "tempo": (48, 66), "progressions": ((1, 3, 6, 4), (4, 1, 2, 5), (1, 4, 3, 6), (6, 4, 1, 5), (1, 2, 4, 6)),
        "pad": 0.31, "bass": 0.075, "melody": 0.065, "brightness": 0.24, "detune": 0.018,
        "attack": 2.5, "release": 3.0, "echo": 0.36, "pulse": 0.006,
        "patches": ("air_choir", "rounded_sub", "soft_flute", "slow_strings"), "texture": 0.065,
        "rhythm_patches": ("soft_mallet", "bell_tree", "water_drop"),
        "rhythm_patterns": ((1.5, 3.5), (2.5,), (0.5, 3.5)),
        "rhythm_probability": 0.35,
        "description": "slow-blooming choir pads and long, cloudlike echoes",
    },
}

ARRANGEMENTS = {
    "Dreamy": {
        "lead_role": "sparse",
        "melody_motifs": (((0.5, 0, 2.5), (2.0, 2, 1.5)), ((1.5, 4, 2.0), (3.0, 2, 1.0))),
        "chord_rhythms": ((2, 2), (1, 1, 1, 1), (1.5, 0.5, 1, 1), (0.5, 0.5, 1, 1, 1)),
        "chord_colors": ("triad", "sixth", "add9", "seventh"),
        "percussion_probability": 0,
        "percussion_gain": 0.05,
    },
    "Peaceful": {
        "lead_role": "harmony",
        "melody_motifs": (((1.5, 2, 2.0),), ((0.5, 4, 2.5),)),
        "chord_rhythms": ((2, 2), (1.5, 1.5, 1), (1, 1, 1, 1)),
        "chord_colors": ("triad", "sixth", "add9", "seventh"),
        "percussion_probability": 0,
        "percussion_gain": 0.05,
    },
    "Melancholic": {
        "lead_role": "melody",
        "melody_motifs": (((0.5, 0, 2.5), (2.0, 2, 1.5), (3.0, 4, 1.0)),
                          ((1.0, 4, 2.5), (3.0, 2, 1.0))),
        "chord_rhythms": ((2, 2), (1, 1, 1, 1), (0.5, 1.5, 1, 1), (0.5, 0.5, 1, 1, 1)),
        "chord_colors": ("triad", "seventh", "ninth", "sus2"),
        "percussion_probability": 0.16,
        "percussion_gain": 0.055,
        "percussion_patterns": (((0, "kick"), (2, "soft_snare")), ((0, "kick"), (1.5, "hat"), (2.5, "soft_snare"))),
    },
    "Hopeful": {
        "lead_role": "melody",
        "melody_motifs": (((0.5, 0, 1.5), (1.5, 2, 1.0), (2.5, 4, 1.5), (3.5, 2, 1.5)),
                          ((0, 4, 1.5), (1.5, 2, 1.5), (2.5, 5, 2.0))),
        "chord_rhythms": ((1, 1, 1, 1), (0.5, 0.5, 1, 1, 1), (0.5, 0.5, 0.5, 0.5, 1, 1),
                          (0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)),
        "chord_colors": ("triad", "sixth", "add9", "seventh"),
        "percussion_probability": 0.42,
        "percussion_gain": 0.08,
        "percussion_patterns": (((0, "kick"), (1, "hat"), (2, "soft_snare"), (3, "hat")),
                                ((0, "kick"), (1.5, "hat"), (2.5, "hat"), (3.5, "hat"))),
    },
    "Mysterious": {
        "lead_role": "sparse",
        "melody_motifs": (((1.5, 0, 2.5),), ((0.5, 4, 2.0), (3.0, 1, 1.0))),
        "chord_rhythms": ((2, 2), (1, 1, 1, 1), (1.5, 0.5, 2), (0.5, 1.5, 1, 1)),
        "chord_colors": ("triad", "sus2", "seventh", "add9"),
        "percussion_probability": 0.12,
        "percussion_gain": 0.045,
        "percussion_patterns": (((0, "low_tom"), (2.5, "hat")),),
    },
    "Warm": {
        "lead_role": "harmony",
        "melody_motifs": (((0.5, 2, 2), (2.5, 4, 1.5)), ((1.5, 4, 2.0),)),
        "chord_rhythms": ((1, 1, 1, 1), (0.5, 0.5, 1, 1, 1), (1.5, 1.5, 1)),
        "chord_colors": ("triad", "sixth", "sus2", "seventh"),
        "percussion_probability": 0.34,
        "percussion_gain": 0.07,
        "percussion_patterns": (((0, "kick"), (2, "soft_snare"), (3, "hat")), ((0, "kick"), (1.5, "hat"), (2, "soft_snare"))),
    },
    "Cosmic": {
        "lead_role": "melody",
        "melody_motifs": (((0.5, 0, 2.0), (1.5, 2, 1.0), (2.5, 4, 2.0), (3.5, 6, 1.5)),
                          ((1.0, 4, 2.5), (2.5, 6, 1.5))),
        "chord_rhythms": ((2, 2), (1, 1, 1, 1), (0.5, 1.5, 1, 1), (1.5, 0.5, 0.5, 1.5)),
        "chord_colors": ("seventh", "sus2", "add9", "ninth"),
        "percussion_probability": 0.24,
        "percussion_gain": 0.035,
        "percussion_patterns": (((0, "soft_kick"), (1.5, "hat"), (3, "hat")),),
    },
    "Dark": {
        "lead_role": "sparse",
        "melody_motifs": (((1.5, 0, 3.0),), ((0.5, 4, 2.5),)),
        "chord_rhythms": ((2, 2), (1.5, 1.5, 1), (1, 1, 1, 1)),
        "chord_colors": ("triad", "power", "sus2", "seventh"),
        "percussion_probability": 0.28,
        "percussion_gain": 0.07,
        "percussion_patterns": (((0, "low_tom"), (2, "kick")), ((0, "kick"), (3, "low_tom"))),
    },
    "Nostalgic": {
        "lead_role": "melody",
        "melody_motifs": (((0.5, 0, 2.5), (2.0, 2, 1.0), (3.0, 4, 2.0)),
                          ((1.0, 4, 2.0), (2.5, 2, 1.0), (3.5, 0, 1.5))),
        "chord_rhythms": ((1, 1, 1, 1), (2, 2), (0.5, 0.5, 1, 1, 1)),
        "chord_colors": ("triad", "seventh", "sixth", "add9"),
        "percussion_probability": 0.30,
        "percussion_gain": 0.065,
        "percussion_patterns": (((0, "kick"), (2, "soft_snare")), ((0, "kick"), (1.5, "hat"), (2, "soft_snare"), (3.5, "hat"))),
    },
    "Tense": {
        "lead_role": "melody",
        "melody_motifs": (((0.5, 0, 1.0), (1.0, 1, 1.0), (2.5, 4, 1.5), (3.0, 2, 1.0)),
                          ((1.5, 4, 1.0), (2.0, 3, 1.0), (3.5, 0, 1.5))),
        "chord_rhythms": ((1, 1, 1, 1), (0.5, 0.5, 1, 1, 1), (0.5, 0.5, 0.5, 0.5, 1, 1),
                          (0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)),
        "chord_colors": ("sus2", "triad", "seventh", "sixth"),
        "percussion_probability": 0.60,
        "percussion_gain": 0.085,
        "percussion_patterns": (((0, "kick"), (1.5, "hat"), (2, "soft_snare"), (3.5, "hat")),
                                ((0, "kick"), (1, "hat"), (2.5, "kick"), (3, "soft_snare"))),
    },
    "Radiant": {
        "lead_role": "melody",
        "melody_motifs": (((0.5, 0, 1.5), (1.5, 2, 1.5), (2.5, 4, 1.5), (3.5, 6, 2.0)),
                          ((0, 4, 1.5), (1.5, 5, 1.0), (2.5, 6, 2.0))),
        "chord_rhythms": ((1, 1, 1, 1), (0.5, 0.5, 1, 1, 1), (0.5, 0.5, 0.5, 0.5, 1, 1),
                          (0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)),
        "chord_colors": ("seventh", "sixth", "sus2", "ninth"),
        "percussion_probability": 0.32,
        "percussion_gain": 0.04,
        "percussion_patterns": (((0, "soft_kick"), (1.5, "hat"), (2.5, "hat")),),
    },
    "Weightless": {
        "lead_role": "harmony",
        "melody_motifs": (((1.5, 0, 3.0),), ((0.5, 4, 2.5),)),
        "chord_rhythms": ((2, 2), (1.5, 1.5, 1), (1, 1, 1, 1)),
        "chord_colors": ("triad", "sixth", "add9", "seventh"),
        "percussion_probability": 0,
        "percussion_gain": 0.03,
    },
}

for mood_name, arrangement in ARRANGEMENTS.items():
    MOODS[mood_name].update(arrangement)

ROMAN = ("I", "ii", "iii", "IV", "V", "vi", "vii°")
CHORD_VOICINGS = {
    "triad": (0, 2, 4), "seventh": (0, 2, 4, 6), "ninth": (0, 2, 4, 6, 8),
    "add9": (0, 2, 4, 8), "sixth": (0, 2, 4, 5), "sus2": (0, 1, 4),
    "sus4": (0, 3, 4), "power": (0, 4),
}
SINE_TABLE_SIZE = 2048


def _make_wavetable(waveform: str) -> tuple[float, ...]:
    if waveform == "sine":
        harmonics = ((1, 1.0),)
    elif waveform == "triangle":
        harmonics = tuple((n, (1 if n % 4 == 1 else -1) / (n * n))
                          for n in range(1, 16, 2))
    elif waveform == "saw":
        harmonics = tuple((n, (-1 if n % 2 == 0 else 1) / n) for n in range(1, 16))
    elif waveform == "square":
        harmonics = tuple((n, 1 / n) for n in range(1, 16, 2))
    else:
        harmonics = ((1, 1.0), (2, 0.34), (3, 0.16), (4, 0.09), (5, 0.05))
    samples = [
        sum(amplitude * math.sin(2 * math.pi * harmonic * i / SINE_TABLE_SIZE)
            for harmonic, amplitude in harmonics)
        for i in range(SINE_TABLE_SIZE)
    ]
    peak = max(abs(sample) for sample in samples)
    return tuple(sample / peak for sample in samples)


WAVETABLES = {
    name: _make_wavetable(name) for name in ("sine", "triangle", "saw", "square", "glass")
}
SINE_TABLE = WAVETABLES["sine"]

SYNTH_LIBRARY = {
    "warm_analog": {"wave": "saw", "brightness": 0.28, "detune": 0.011},
    "soft_strings": {"wave": "triangle", "brightness": 0.30, "detune": 0.008},
    "hollow_choir": {"wave": "triangle", "brightness": 0.22, "detune": 0.015},
    "dark_drone": {"wave": "sine", "brightness": 0.06, "detune": 0.007},
    "crystal_pad": {"wave": "glass", "brightness": 0.42, "detune": 0.013},
    "rounded_sub": {"wave": "sine", "brightness": 0.08, "detune": 0.002},
    "analog_bass": {"wave": "triangle", "brightness": 0.22, "detune": 0.003},
    "mellow_bass": {"wave": "saw", "brightness": 0.16, "detune": 0.002},
    "glass_bell": {"wave": "glass", "brightness": 0.68, "detune": 0.004},
    "soft_flute": {"wave": "sine", "brightness": 0.22, "detune": 0.006},
    "airy_chime": {"wave": "glass", "brightness": 0.54, "detune": 0.012},
    "muted_pluck": {"wave": "square", "brightness": 0.18, "detune": 0.001},
    "air_choir": {"wave": "triangle", "brightness": 0.20, "detune": 0.017},
    "slow_strings": {"wave": "saw", "brightness": 0.19, "detune": 0.014},
    "tape_keys": {"wave": "triangle", "brightness": 0.37, "detune": 0.006},
    "soft_mallet": {"wave": "glass", "brightness": 0.72, "detune": 0.002},
    "wooden_tine": {"wave": "square", "brightness": 0.32, "detune": 0.001},
    "dusty_pluck": {"wave": "saw", "brightness": 0.42, "detune": 0.003},
    "bell_tree": {"wave": "glass", "brightness": 0.86, "detune": 0.009},
    "pizzicato": {"wave": "triangle", "brightness": 0.56, "detune": 0.004},
    "water_drop": {"wave": "sine", "brightness": 0.48, "detune": 0.018},
}


@dataclass(frozen=True)
class Settings:
    mood: str
    key: str
    tempo: int
    numerator: int
    denominator: int
    vocal_enabled: bool = False
    vocal_role: str = "melody"
    lyrics: str = ""
    vocal_prominent: bool = False
    vocals_only: bool = False
    instrument_override: tuple[str, ...] | None = None
    instrumental_percussion: bool = True


def scale_frequency(key: str, scale: tuple[int, ...], degree: int, octave: int) -> float:
    """Return a scale tone frequency; degrees may extend beyond one octave."""
    octave_shift, index = divmod(degree, len(scale))
    midi = 12 * (octave + 1) + KEYS[key] + scale[index] + 12 * octave_shift
    return 440.0 * 2 ** ((midi - 69) / 12)


@lru_cache(maxsize=512)
def _vocal_word_pcm(word: str, midi_note: int, vowel_duration_ms: int) -> bytes:
    samples = synthesize_vocal(
        word, midi_note, "Female", None, 0.08, 5.2,
        vowel_duration_ms / 1000, humanization=0.12
    )
    source = array("h")
    ratio = VOCAL_SAMPLE_RATE / SAMPLE_RATE
    output_frames = max(1, round(len(samples) / ratio))
    for frame in range(output_frames):
        source_position = frame * ratio
        index = int(source_position)
        fraction = source_position - index
        first = samples[min(index, len(samples) - 1)]
        second = samples[min(index + 1, len(samples) - 1)]
        source.append(max(-32768, min(32767, round((first + (second - first) * fraction) * 32767))))
    if sys.byteorder != "little":
        source.byteswap()
    return source.tobytes()


def _lyrics_for_section(lyrics: str, section_index: int,
                        vocals_only: bool = False) -> list[str]:
    verse_index = {0: 0, 2: 1, 5: 2}.get(section_index % len(SONG_FORM))
    if verse_index is None and not vocals_only:
        return []
    lines = [line.strip() for line in lyrics.splitlines() if line.strip()]
    if not lines:
        return []
    if vocals_only:
        verse_index = section_index % len(lines)
    if len(lines) > 1:
        text = lines[verse_index % len(lines)]
    else:
        words = lines[0].split()
        if vocals_only:
            text = lines[0]
        else:
            start = round(verse_index * len(words) / 3)
            end = round((verse_index + 1) * len(words) / 3)
            text = " ".join(words[start:end])
            if not text:
                text = lines[0]
    words = re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?", text)
    if words:
        words.extend(words[index % len(words)] for index in range(3 - len(words)))
    return words


def _mix_vocal_phrase(left: list[float], right: list[float], settings: Settings,
                      section_index: int, bar_duration: float, beats_per_bar: float,
                      chord_events: list[tuple[float, float, list[float]]],
                      melody_events: tuple[tuple[float, int, float], ...],
                      form_level: float) -> None:
    if not (settings.vocal_enabled or settings.vocals_only):
        return
    words = _lyrics_for_section(settings.lyrics, section_index, settings.vocals_only)
    if not words:
        return
    beat_seconds = bar_duration / beats_per_bar
    beats_in_section = SECTION_BARS * beats_per_bar
    def chord_at(bar: float) -> list[float]:
        for start, end, chord in chord_events:
            if start <= bar < end or math.isclose(bar, start):
                return chord
        return chord_events[-1][2]

    # Leave breath between phrases and anchor every word to the section's chord rhythm.
    spacing = beats_in_section / len(words)
    for index, word in enumerate(words):
        beat_position = index * spacing + min(0.12, spacing * 0.12)
        bar_position = beat_position / beats_per_bar
        chord = chord_at(bar_position)
        motif_event = melody_events[index % len(melody_events)]
        tone_index = (motif_event[1] + index // max(1, len(melody_events))) % len(chord)
        if settings.vocal_role == "harmony":
            tone_index = (tone_index + 1) % len(chord)
        frequency = chord[tone_index] * 2
        midi_note = round(69 + 12 * math.log2(frequency / 440))
        start = int(beat_position * beat_seconds * SAMPLE_RATE)
        next_start = int(min(beats_in_section, (index + 1) * spacing) * beat_seconds * SAMPLE_RATE)
        slot_seconds = max(0.14, (next_start - start) / SAMPLE_RATE * 0.88)
        units = vocal_engine.PhonemeParser.parse(word)
        vowels = sum(kind == "vowel" for kind, _ in units)
        consonants = max(0, len(units) - vowels)
        estimated_units = max(1.0, vowels * 1.35 + consonants * 0.68)
        vowel_duration_ms = round(max(55, min(145, slot_seconds / estimated_units * 1000)))
        voice = _vocal_word_pcm(word, midi_note, vowel_duration_ms)
        samples = array("h")
        samples.frombytes(voice)
        if sys.byteorder != "little":
            samples.byteswap()
        frames = min(len(samples), len(left) - start, max(1, int(slot_seconds * SAMPLE_RATE)))
        if frames <= 0:
            continue
        gain = (0.12 if settings.vocal_role == "melody" else 0.09) * form_level
        if settings.vocal_prominent:
            gain = 0.82 * form_level
        pan = 0.0 if settings.vocal_role == "melody" else 0.16
        left_gain = gain * math.sqrt((1 - pan) * 0.5)
        right_gain = gain * math.sqrt((1 + pan) * 0.5)
        duck_frames = max(1, int(0.04 * SAMPLE_RATE))
        release_frames = max(1, int(0.12 * SAMPLE_RATE))
        for frame in range(frames):
            envelope = min(1.0, (frames - frame) / max(1, int(0.035 * SAMPLE_RATE)))
            sample = samples[frame] / 32768 * envelope
            if settings.vocal_prominent:
                attack = min(1.0, (frame + 1) / duck_frames)
                release = min(1.0, (frames - frame) / release_frames)
                duck_gain = 1.0 - 0.78 * min(attack, release)
                left[start + frame] *= duck_gain
                right[start + frame] *= duck_gain
            left[start + frame] += sample * left_gain
            right[start + frame] += sample * right_gain


def _instrument_table(waveform: str, brightness: float) -> tuple[float, ...]:
    table = WAVETABLES[waveform]
    return tuple(SINE_TABLE[i] * (1 - brightness) + table[i] * brightness
                 for i in range(SINE_TABLE_SIZE))


def _add_note(left: list[float], right: list[float], start: int, duration: int,
              frequency: float, gain: float, pan: float, attack: float, release: float,
              brightness: float, detune: float, waveform: str = "sine") -> None:
    end = min(start + duration, len(left))
    if end <= start:
        return
    attack_samples = max(1, int(attack * SAMPLE_RATE))
    release_samples = max(1, int(release * SAMPLE_RATE))
    table = _instrument_table(waveform, brightness)
    phase = 0.0
    phase_detuned = 0.0
    step = frequency * SINE_TABLE_SIZE / SAMPLE_RATE
    step_detuned = step * (1 + detune)
    left_gain = gain * math.sqrt((1 - pan) * 0.5)
    right_gain = gain * math.sqrt((1 + pan) * 0.5)
    for position in range(start, end):
        elapsed = position - start
        remaining = end - position
        env = min(1.0, elapsed / attack_samples)
        env *= min(1.0, remaining / release_samples)
        phase_index = int(phase)
        detuned_index = int(phase_detuned)
        phase_fraction = phase - phase_index
        detuned_fraction = phase_detuned - detuned_index
        sample = (
            (table[phase_index] * (1 - phase_fraction) +
             table[(phase_index + 1) % SINE_TABLE_SIZE] * phase_fraction) * 0.72 +
            (table[detuned_index] * (1 - detuned_fraction) +
             table[(detuned_index + 1) % SINE_TABLE_SIZE] * detuned_fraction) * 0.28
        ) * env
        left[position] += sample * left_gain
        right[position] += sample * right_gain
        phase += step
        phase_detuned += step_detuned
        if phase >= SINE_TABLE_SIZE:
            phase -= SINE_TABLE_SIZE
        if phase_detuned >= SINE_TABLE_SIZE:
            phase_detuned -= SINE_TABLE_SIZE


def _chord_notes(key: str, scale: tuple[int, ...], degree: int, color: str) -> list[float]:
    return [scale_frequency(key, scale, degree + interval, 4)
            for interval in CHORD_VOICINGS[color]]


def _progression_for_length(progression: tuple[int, ...], length: int) -> tuple[int, ...]:
    if length == len(progression):
        return progression
    if length < len(progression):
        return tuple(progression[round(index * (len(progression) - 1) / max(1, length - 1))]
                     for index in range(length))
    result = []
    for index in range(length):
        position = index * (len(progression) - 1) / max(1, length - 1)
        lower = int(position)
        fraction = position - lower
        if lower >= len(progression) - 1 or fraction >= 0.5:
            result.append(progression[min(lower + (fraction >= 0.5), len(progression) - 1)])
        else:
            current = progression[lower]
            following = progression[lower + 1]
            forward = (following - current) % 7
            backward = (current - following) % 7
            result.append((current + (1 if forward <= backward else -1) - 1) % 7 + 1
                          if current != following else current)
    varied = []
    for degree in result:
        if varied and degree == varied[-1]:
            degree = degree % 7 + 1
            if len(varied) > 1 and degree == varied[-2]:
                degree = degree % 7 + 1
        varied.append(degree)
    return tuple(varied)


def _add_percussion(left: list[float], right: list[float], start: int,
                    kind: str, gain: float, rng: random.Random, pan: float = 0) -> None:
    durations = {"kick": 0.24, "soft_kick": 0.18, "low_tom": 0.30,
                 "soft_snare": 0.16, "hat": 0.075}
    duration = min(int(durations[kind] * SAMPLE_RATE), len(left) - start)
    if duration <= 0:
        return
    left_gain = gain * math.sqrt((1 - pan) * 0.5)
    right_gain = gain * math.sqrt((1 + pan) * 0.5)
    phase = 0.0
    previous_noise = 0.0
    for index in range(duration):
        progress = index / duration
        if kind in ("kick", "soft_kick", "low_tom"):
            start_frequency = {"kick": 95, "soft_kick": 72, "low_tom": 125}[kind]
            frequency = start_frequency * (1 - 0.72 * progress)
            phase += 2 * math.pi * frequency / SAMPLE_RATE
            envelope = (1 - progress) ** (3.0 if kind != "low_tom" else 2.1)
            sample = math.sin(phase) * envelope
        else:
            noise = rng.uniform(-1, 1)
            highpassed = noise - previous_noise * (0.78 if kind == "hat" else 0.35)
            previous_noise = noise
            envelope = (1 - progress) ** (10 if kind == "hat" else 3.3)
            sample = highpassed * envelope
            if kind == "soft_snare":
                sample += math.sin(phase + index * 0.08) * envelope * 0.25
        left[start + index] += sample * left_gain
        right[start + index] += sample * right_gain


def generate_section(settings: Settings, rng: random.Random | None = None,
                     section_index: int = 0) -> tuple[bytes, str]:
    """Render a four-bar section with mood-specific harmony, lead, and rhythm."""
    rng = rng or random.Random()
    mood = MOODS[settings.mood]
    form = SONG_FORM[section_index % len(SONG_FORM)]
    if (settings.vocal_enabled or settings.vocals_only) and not settings.lyrics.strip():
        settings = Settings(
            settings.mood, settings.key, settings.tempo, settings.numerator,
            settings.denominator, True, settings.vocal_role,
            "\n".join(rng.sample(DEFAULT_LYRICS[settings.mood], 3)),
            settings.vocal_prominent, settings.vocals_only,
            settings.instrument_override, settings.instrumental_percussion
        )
    form_level = {"Verse": 0.82, "Chorus": 1.08, "Bridge": 0.64, "Final Chorus": 1.22}[form]
    scale = SCALES[mood["scale"]]
    beats_per_bar = settings.numerator * 4 / settings.denominator
    seconds_per_beat = 60 / settings.tempo
    bar_duration = beats_per_bar * seconds_per_beat
    total_samples = int(SECTION_BARS * bar_duration * SAMPLE_RATE) + int(1.5 * SAMPLE_RATE)
    left = [0.0] * total_samples
    right = [0.0] * total_samples
    patch_names = settings.instrument_override
    if settings.vocals_only:
        patch_names = ()
    elif patch_names is None:
        patch_names = mood["patches"]

    def patch_at(index: int) -> dict[str, float | str] | None:
        return SYNTH_LIBRARY[patch_names[index % len(patch_names)]] if patch_names else None

    pad_patch, bass_patch, lead_patch, texture_patch = (patch_at(index) for index in range(4))
    rhythm_enabled = bool(patch_names) and rng.random() < mood["rhythm_probability"]
    rhythm_choices = (settings.instrument_override if settings.instrument_override is not None
                      else mood["rhythm_patches"])
    rhythm_patch = SYNTH_LIBRARY[rng.choice(rhythm_choices)] if rhythm_enabled else None
    rhythm_pattern = rng.choice(mood["rhythm_patterns"]) if rhythm_enabled else ()
    progression_source = rng.choice(mood["progressions"])
    chord_rhythm = rng.choice(mood["chord_rhythms"])
    progression = _progression_for_length(progression_source, len(chord_rhythm))
    chord_events: list[tuple[float, float, list[float]]] = []
    chords = []
    bar_position = 0.0
    pan_positions = (-0.72, -0.36, 0.0, 0.36, 0.72)

    for event_index, (degree_number, duration_bars) in enumerate(zip(progression, chord_rhythm)):
        degree = degree_number - 1
        start = int(bar_position * bar_duration * SAMPLE_RATE)
        duration = int(duration_bars * bar_duration * SAMPLE_RATE)
        color = rng.choice(mood["chord_colors"])
        chord = _chord_notes(settings.key, scale, degree, color)
        chord_events.append((bar_position, bar_position + duration_bars, chord))
        roman = ROMAN[degree] if degree < len(ROMAN) else f"degree {degree_number}"
        chords.append(f"{roman} ({color})")
        if pad_patch:
            for voice, frequency in enumerate(chord):
                _add_note(left, right, start, duration, frequency,
                          mood["pad"] / (1 + voice * 0.25), pan_positions[voice % len(pan_positions)],
                          mood["attack"], mood["release"],
                          min(1, pad_patch["brightness"] + mood["brightness"] * 0.45),
                          min(MAX_VOICE_DETUNE, mood["detune"] + pad_patch["detune"]), pad_patch["wave"])
        root = scale_frequency(settings.key, scale, degree, 2)
        if bass_patch:
            _add_note(left, right, start, duration, root, mood["bass"], -0.08,
                      mood["attack"] * 0.75, mood["release"],
                      min(1, bass_patch["brightness"] + mood["brightness"] * 0.24),
                      min(MAX_VOICE_DETUNE, bass_patch["detune"]), bass_patch["wave"])
        if texture_patch and mood["texture"] and (event_index == 0 or rng.random() < 0.7):
            texture_frequency = chord[rng.randrange(len(chord))] * 2
            _add_note(left, right, start, duration, texture_frequency, mood["texture"],
                      rng.uniform(-0.8, 0.8), mood["attack"] * 1.6, mood["release"] * 1.2,
                      min(1, texture_patch["brightness"] + mood["brightness"] * 0.30),
                      min(MAX_VOICE_DETUNE, texture_patch["detune"]), texture_patch["wave"])
        bar_position += duration_bars

    def harmony_event_at(bar: float) -> tuple[list[float], float]:
        for start, end, chord in chord_events:
            if start <= bar < end or math.isclose(bar, start):
                return chord, end
        return chord_events[-1][2], chord_events[-1][1]

    lead_role = mood["lead_role"]
    motif = rng.choice(mood["melody_motifs"])
    melody_events = list(motif)
    if form in ("Chorus", "Final Chorus"):
        for beat, degree_offset, _ in motif:
            answer_beat = beat + 0.5
            if answer_beat < beats_per_bar:
                melody_events.append((answer_beat, (degree_offset + 1) % 4, 0.5))
    if form == "Bridge":
        melody_events = [(beat, degree, hold * 1.35) for beat, degree, hold in melody_events
                         if int(beat * 2) % 2 == 0]
    melody_events.sort()
    for bar in range(SECTION_BARS) if lead_patch and not settings.vocals_only else ():
        bar_start = int(bar * bar_duration * SAMPLE_RATE)
        contour_shift = (0, 1, 0, -1)[bar]
        for note_index, (beat, degree_offset, hold_beats) in enumerate(melody_events):
            if beat >= beats_per_bar:
                continue
            position = bar + beat / beats_per_bar
            chord, chord_end = harmony_event_at(position)
            note_start = bar_start + int(beat * seconds_per_beat * SAMPLE_RATE)
            note_duration = int(hold_beats * seconds_per_beat * SAMPLE_RATE)
            chord_tone_index = (degree_offset + contour_shift + bar // 2) % len(chord)
            frequency = chord[chord_tone_index] * 2
            role_gain = {"melody": 1.0, "harmony": 0.72, "sparse": 0.9, "none": 1.0}[lead_role]
            gain = mood["melody"] * role_gain * form_level * (
                1.0 if form in ("Chorus", "Final Chorus") else 0.88)
            chord_end_samples = int(chord_end * bar_duration * SAMPLE_RATE)
            while note_start + note_duration > chord_end_samples:
                next_chord, next_end = harmony_event_at(chord_end / (bar_duration * SAMPLE_RATE) + 1e-8)
                if next_end <= chord_end:
                    break
                pitch_class = round(69 + 12 * math.log2(frequency / 440)) % 12
                shared = any(
                    round(69 + 12 * math.log2(tone / 440)) % 12 == pitch_class
                    for tone in next_chord
                )
                if not shared:
                    note_duration = max(1, chord_end_samples - note_start)
                    break
                chord_end_samples = int(next_end * bar_duration * SAMPLE_RATE)
            _add_note(left, right, note_start, note_duration, frequency, gain,
                      (-0.55, 0.10, 0.55, -0.10)[(bar + note_index) % 4],
                      0.035 if lead_role == "melody" else mood["attack"] * 0.30,
                      max(0.20, seconds_per_beat * 0.45),
                      lead_patch["brightness"],
                      min(MAX_VOICE_DETUNE, lead_patch["detune"] + mood["detune"] * 0.35),
                      lead_patch["wave"])

    if rhythm_patch and not settings.vocals_only:
        for bar in range(SECTION_BARS):
            bar_start = int(bar * bar_duration * SAMPLE_RATE)
            for hit, beat in enumerate(rhythm_pattern):
                if beat >= beats_per_bar or rng.random() > 0.88:
                    continue
                chord, _ = harmony_event_at(bar + beat / beats_per_bar)
                rhythm_start = bar_start + int(beat * seconds_per_beat * SAMPLE_RATE)
                tone = chord[(bar + hit) % len(chord)]
                octave = 2 if rhythm_patch["wave"] in ("sine", "triangle") else 1
                note_duration = int(seconds_per_beat * rng.uniform(0.12, 0.27) * SAMPLE_RATE)
                gain = mood["melody"] * (0.32 if lead_role == "melody" else 0.58)
                _add_note(left, right, rhythm_start, note_duration, tone * (2 ** octave),
                          gain, rng.uniform(-0.82, 0.82), 0.008,
                          min(0.20, seconds_per_beat * 0.20),
                          rhythm_patch["brightness"],
                          min(MAX_VOICE_DETUNE, rhythm_patch["detune"]),
                          rhythm_patch["wave"])

    snare_beats = (1, 3) if beats_per_bar >= 4 else ((1.5,) if settings.numerator == 6 else (2,))
    hat_step = 0.5 if form in ("Chorus", "Final Chorus") else (1.5 if form == "Bridge" else 1.0)
    kick_kind = "soft_kick" if mood["percussion_gain"] < 0.055 else "kick"
    percussion_enabled = not settings.vocals_only and (
        settings.instrument_override is None or settings.instrumental_percussion)
    for bar in range(SECTION_BARS) if percussion_enabled else ():
        drum_events = [(0, kick_kind)]
        if (form in ("Chorus", "Final Chorus") and beats_per_bar >= 3
                and rng.random() < mood["percussion_probability"]):
            drum_events.append((2 if beats_per_bar >= 4 else beats_per_bar - 1, kick_kind))
        for beat in snare_beats:
            if beat < beats_per_bar and (form != "Bridge" or bar % 2 == 1):
                drum_events.append((beat, "soft_snare"))
        beat = 0.5 if settings.numerator == 6 and settings.denominator == 8 else 0.0
        while beat < beats_per_bar:
            if (beat % hat_step == 0 or math.isclose(beat % hat_step, 0)) and rng.random() < (
                    0.92 if form in ("Chorus", "Final Chorus") else 0.74):
                drum_events.append((beat, "hat"))
            beat += 0.5
        if form in ("Chorus", "Final Chorus") and bar == SECTION_BARS - 1:
            if rng.random() < mood["percussion_probability"]:
                drum_events.append((max(0, beats_per_bar - 0.5), "low_tom"))
        fills = mood.get("percussion_patterns", ())
        if form == "Final Chorus" and bar == SECTION_BARS - 1 and fills and rng.random() < mood[
                "percussion_probability"]:
            for fill_beat, fill_kind in rng.choice(fills):
                if fill_beat < beats_per_bar and (fill_beat, fill_kind) not in drum_events:
                    drum_events.append((fill_beat, fill_kind))
        for beat, kind in drum_events:
            if beat >= beats_per_bar:
                continue
            start = int((bar * beats_per_bar + beat) * seconds_per_beat * SAMPLE_RATE)
            level = mood["percussion_gain"] * form_level
            if kind == "hat":
                level *= 0.48
            elif kind == "soft_snare":
                level *= 0.72
            _add_percussion(left, right, start, kind, level, rng,
                            rng.uniform(-0.18, 0.18) if kind in ("hat", "soft_snare") else 0)

    # A quiet pulse marks the first beat, but stays behind the sustained synths.
    if mood["pulse"] and not settings.vocals_only and settings.instrument_override is None:
        for bar in range(SECTION_BARS):
            start = int(bar * bar_duration * SAMPLE_RATE)
            chord, _ = harmony_event_at(float(bar))
            root = chord[0] / 4
            _add_note(left, right, start, int(0.8 * seconds_per_beat * SAMPLE_RATE),
                      root * 2, mood["pulse"], 0, 0.04, 0.4, 0.04, 0)

    # Two short feedback taps lend the pad a spacious tail without external effects.
    if not settings.vocals_only:
        delay = int(min(0.48, bar_duration * 0.22) * SAMPLE_RATE)
        echo = mood["echo"]
        for i in range(delay, total_samples):
            left[i] += left[i - delay] * echo
            right[i] += right[i - delay] * echo * 0.94
        second_delay = delay * 2
        if second_delay < total_samples:
            for i in range(second_delay, total_samples):
                left[i] += left[i - second_delay] * echo * 0.32
                right[i] += right[i - second_delay] * echo * 0.32

    _mix_vocal_phrase(
        left, right, settings, section_index, bar_duration, beats_per_bar,
        chord_events, melody_events, form_level
    )

    peak = max(max(abs(sample) for sample in left), max(abs(sample) for sample in right), 1e-9)
    scale_out = min(1.0, 0.88 / peak)
    pcm = bytearray(total_samples * 4)
    offset = 0
    for l_sample, r_sample in zip(left, right):
        struct.pack_into("<hh", pcm, offset,
                         int(max(-1, min(1, l_sample * scale_out)) * 32767),
                         int(max(-1, min(1, r_sample * scale_out)) * 32767))
        offset += 4
    return bytes(pcm), f"{form}: " + "  -  ".join(chords)


def generate_song(settings: Settings, rng: random.Random | None = None) -> tuple[bytes, str]:
    """Render one complete verse/chorus/bridge cycle for a standalone export."""
    rng = rng or random.Random()
    if (settings.vocal_enabled or settings.vocals_only) and not settings.lyrics.strip():
        settings = Settings(settings.mood, settings.key, settings.tempo,
                            settings.numerator, settings.denominator,
                            True, settings.vocal_role,
                            "\n".join(rng.sample(DEFAULT_LYRICS[settings.mood], 3)),
                            settings.vocal_prominent, settings.vocals_only,
                            settings.instrument_override, settings.instrumental_percussion)
    beats_per_bar = settings.numerator * 4 / settings.denominator
    bar_frames = int(SECTION_BARS * beats_per_bar * 60 / settings.tempo * SAMPLE_RATE)
    fade_bytes = int(0.35 * SAMPLE_RATE) * 4
    audio = b""
    labels = []
    final_tail = b""
    for section_index in range(len(SONG_FORM)):
        pcm, label = generate_section(settings, rng, section_index)
        section = pcm[:bar_frames * 4]
        labels.append(label)
        if section_index == len(SONG_FORM) - 1:
            final_tail = pcm[bar_frames * 4:]
        if not audio:
            audio = section
            continue
        overlap = min(fade_bytes, len(audio), len(section))
        audio = audio[:-overlap] + _blend_pcm(audio[-overlap:], section[:overlap]) + section[overlap:]
    audio += final_tail
    return audio, " | ".join(labels)


def write_wav(path: str | Path, pcm: bytes) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(pcm)


def write_wav_from_file(path: str | Path, pcm_path: str | Path) -> None:
    fade_bytes = int(0.15 * SAMPLE_RATE) * 4
    with open(pcm_path, "rb") as pcm, wave.open(str(path), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        tail = b""
        while block := pcm.read(256 * 1024):
            pending = tail + block
            if len(pending) <= fade_bytes:
                tail = pending
                continue
            safe_bytes = len(pending) - fade_bytes
            safe_bytes -= safe_bytes % 4
            output.writeframesraw(pending[:safe_bytes])
            tail = pending[safe_bytes:]
        if tail:
            samples = array("h")
            samples.frombytes(tail)
            if sys.byteorder != "little":
                samples.byteswap()
            frames = len(samples) // 2
            for frame in range(frames):
                gain = 1 - (frame + 1) / frames
                samples[frame * 2] = round(samples[frame * 2] * gain)
                samples[frame * 2 + 1] = round(samples[frame * 2 + 1] * gain)
            if sys.byteorder != "little":
                samples.byteswap()
            output.writeframesraw(samples.tobytes())


def _stream_player_command() -> list[str] | None:
    if shutil.which("aplay"):
        return ["aplay", "-q", "-t", "raw", "-f", "S16_LE", "-r", str(SAMPLE_RATE), "-c", "2", "-"]
    if shutil.which("paplay"):
        return ["paplay", "--raw", "--format=s16le", f"--rate={SAMPLE_RATE}", "--channels=2", "-"]
    if shutil.which("ffplay"):
        return ["ffplay", "-nodisp", "-loglevel", "error", "-f", "s16le",
                "-ar", str(SAMPLE_RATE), "-ac", "2", "-i", "pipe:0"]
    return None


def _blend_pcm(previous: bytes, following: bytes) -> bytes:
    left = array("h")
    right = array("h")
    left.frombytes(previous)
    right.frombytes(following)
    if sys.byteorder != "little":
        left.byteswap()
        right.byteswap()
    if len(left) != len(right) or len(left) % 2:
        raise ValueError("Crossfade audio must contain matching stereo PCM frames.")
    frames = len(left) // 2
    output = array("h")
    for frame in range(frames):
        blend = 0.5 - 0.5 * math.cos(math.pi * (frame + 1) / (frames + 1))
        for channel in (0, 1):
            sample = left[frame * 2 + channel] * (1 - blend) + right[frame * 2 + channel] * blend
            output.append(max(-32768, min(32767, round(sample))))
    if sys.byteorder != "little":
        output.byteswap()
    return output.tobytes()


class AmbientGeneratorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Stillwater — Ambient Music Generator")
        self.root.geometry("760x800")
        self.root.minsize(680, 600)
        self.root.configure(bg="#111820")
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.producer: threading.Thread | None = None
        self.player: subprocess.Popen | None = None
        self.recording_path: str | None = None
        self.record_lock = threading.Lock()
        self.session_frames = 0
        self.playing = False
        self.mood_var = tk.StringVar(value="Dreamy")
        self.key_var = tk.StringVar(value="C")
        self.tempo_var = tk.IntVar(value=68)
        self.meter_var = tk.StringVar(value="4/4")
        self.random_each_var = tk.BooleanVar(value=False)
        self.random_each = False
        self.vocal_enabled_var = tk.BooleanVar(value=False)
        self.vocal_melody_var = tk.BooleanVar(value=True)
        self.vocal_harmony_var = tk.BooleanVar(value=False)
        self.vocal_prominent_var = tk.BooleanVar(value=False)
        self.vocals_only_var = tk.BooleanVar(value=False)
        self.instrumental_var = tk.BooleanVar(value=False)
        self.instrumental_percussion_var = tk.BooleanVar(value=True)
        self.instrument_vars = {
            name: tk.BooleanVar(value=False) for name in SYNTH_LIBRARY
        }
        self.status_var = tk.StringVar(value="Choose a mood and press Start.")
        self.chords_var = tk.StringVar(value="Verse and chorus sections will alternate as music unfolds.")
        self._style()
        self._build_ui()
        self._update_mood_description()

    def _style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#111820")
        style.configure("Card.TFrame", background="#1b2732")
        style.configure("TLabel", background="#111820", foreground="#e8edf2", font=("TkDefaultFont", 10))
        style.configure("Title.TLabel", font=("TkDefaultFont", 22, "bold"), foreground="#f3f6f8")
        style.configure("Sub.TLabel", foreground="#aab8c4")
        style.configure("Card.TLabel", background="#1b2732")
        style.configure("TButton", padding=(12, 8), font=("TkDefaultFont", 10, "bold"))
        style.configure("Accent.TButton", background="#58b4a9", foreground="#10191d")
        style.map("Accent.TButton", background=[("active", "#74cbbf")])
        style.configure("TCheckbutton", background="#1b2732", foreground="#dbe5ec")
        style.configure("TCombobox", padding=5)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=24)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="STILLWATER", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="An evolving ambient synthesizer", style="Sub.TLabel").pack(anchor="w", pady=(2, 18))

        card = ttk.Frame(outer, style="Card.TFrame", padding=18)
        card.pack(fill="x")
        ttk.Label(card, text="Set the atmosphere", style="Card.TLabel",
                  font=("TkDefaultFont", 13, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 14))
        ttk.Label(card, text="Mood", style="Card.TLabel").grid(row=1, column=0, sticky="w")
        mood_box = ttk.Combobox(card, textvariable=self.mood_var, values=tuple(MOODS), state="readonly", width=18)
        mood_box.grid(row=2, column=0, sticky="ew", padx=(0, 12))
        mood_box.bind("<<ComboboxSelected>>", lambda _event: self._update_mood_description())
        ttk.Button(card, text="Surprise me", command=self._surprise).grid(row=2, column=1, sticky="ew", padx=4)
        ttk.Label(card, text="Key", style="Card.TLabel").grid(row=1, column=2, sticky="w", padx=(10, 0))
        ttk.Combobox(card, textvariable=self.key_var, values=tuple(KEYS), state="readonly", width=8).grid(
            row=2, column=2, sticky="ew", padx=(10, 12))
        ttk.Label(card, text="Time signature", style="Card.TLabel").grid(row=1, column=3, sticky="w")
        ttk.Combobox(card, textvariable=self.meter_var, values=("4/4", "3/4", "6/8"),
                     state="readonly", width=10).grid(row=2, column=3, sticky="ew")
        ttk.Label(card, text="Tempo (quarter-note BPM)", style="Card.TLabel").grid(
            row=3, column=0, sticky="w", pady=(16, 0))
        ttk.Spinbox(card, from_=40, to=120, textvariable=self.tempo_var, width=8).grid(
            row=4, column=0, sticky="w", pady=(4, 0))
        ttk.Checkbutton(card, text="Choose a new random mood every section",
                        variable=self.random_each_var).grid(row=4, column=1, columnspan=3, sticky="w", pady=(4, 0))
        card.columnconfigure(0, weight=1)
        card.columnconfigure(1, weight=1)
        card.columnconfigure(2, weight=0)
        card.columnconfigure(3, weight=0)

        vocal_card = ttk.Frame(outer, style="Card.TFrame", padding=14)
        vocal_card.pack(fill="x", pady=(14, 0))
        ttk.Checkbutton(vocal_card, text="Use vocal synthesizer",
                        variable=self.vocal_enabled_var,
                        command=self._toggle_vocal_options).pack(anchor="w")
        self.vocal_options = ttk.Frame(vocal_card, style="Card.TFrame")
        self.vocal_melody_check = ttk.Checkbutton(
            self.vocal_options, text="Sing the melody",
            variable=self.vocal_melody_var, command=self._select_vocal_melody)
        self.vocal_melody_check.grid(row=0, column=0, sticky="w", padx=(0, 16), pady=(8, 4))
        self.vocal_harmony_check = ttk.Checkbutton(
            self.vocal_options, text="Sing chord harmony",
            variable=self.vocal_harmony_var, command=self._select_vocal_harmony)
        self.vocal_harmony_check.grid(row=0, column=1, sticky="w", pady=(8, 4))
        ttk.Checkbutton(
            self.vocal_options, text="Vocal prominence (vocals lead over instruments)",
            variable=self.vocal_prominent_var
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 6))
        ttk.Checkbutton(
            self.vocal_options, text="Vocals only (no instruments or percussion)",
            variable=self.vocals_only_var
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 6))
        ttk.Label(self.vocal_options, text="Custom lyrics (blank generates a short song-specific verse)",
                  style="Card.TLabel").grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 3))
        self.lyrics_text = tk.Text(self.vocal_options, height=3, wrap="word",
                                   bg="#111820", fg="#e8edf2", insertbackground="#e8edf2",
                                   relief="flat", padx=8, pady=6, font=("TkDefaultFont", 10))
        self.lyrics_text.grid(row=4, column=0, columnspan=2, sticky="ew")
        self.vocal_options.columnconfigure(0, weight=1)
        self.vocal_options.columnconfigure(1, weight=1)
        self.vocal_options.pack_forget()

        instrumental_card = ttk.Frame(outer, style="Card.TFrame", padding=14)
        instrumental_card.pack(fill="x", pady=(10, 0))
        ttk.Checkbutton(
            instrumental_card, text="Instrumentals (choose synths to override the mood's instruments)",
            variable=self.instrumental_var, command=self._toggle_instrument_options
        ).pack(anchor="w")
        self.instrument_options = ttk.Frame(instrumental_card, style="Card.TFrame")
        ttk.Label(
            self.instrument_options,
            text="Selected synths share the mood's chords and progression. Clear all to silence synth instruments.",
            style="Card.TLabel", wraplength=680
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(7, 5))
        for index, (name, variable) in enumerate(self.instrument_vars.items()):
            ttk.Checkbutton(
                self.instrument_options, text=name.replace("_", " ").title(),
                variable=variable
            ).grid(row=1 + index // 4, column=index % 4, sticky="w", padx=(0, 10), pady=2)
        percussion_row = 1 + (len(self.instrument_vars) + 3) // 4
        ttk.Checkbutton(
            self.instrument_options, text="Include percussion",
            variable=self.instrumental_percussion_var
        ).grid(row=percussion_row, column=0, columnspan=3, sticky="w", pady=(5, 2))
        for column in range(4):
            self.instrument_options.columnconfigure(column, weight=1)
        self.instrument_options.pack_forget()

        self.description = ttk.Label(outer, text="", style="Sub.TLabel", wraplength=680)
        self.description.pack(anchor="w", pady=(12, 18))
        controls = ttk.Frame(outer)
        controls.pack(fill="x")
        self.start_button = ttk.Button(controls, text="▶  Start generating", style="Accent.TButton",
                                       command=self.start)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(controls, text="■  Stop", command=self.stop, state="disabled")
        self.stop_button.pack(side="left", padx=8)
        ttk.Button(controls, text="Export session WAV…", command=self.export).pack(side="right")

        info = ttk.Frame(outer, style="Card.TFrame", padding=16)
        info.pack(fill="x", pady=(20, 0))
        ttk.Label(info, text="CURRENT SONG SECTION / HARMONY", style="Card.TLabel",
                  font=("TkDefaultFont", 9, "bold")).pack(anchor="w")
        ttk.Label(info, textvariable=self.chords_var, style="Card.TLabel",
                  font=("TkDefaultFont", 14, "bold"), foreground="#8fd2c7",
                  wraplength=680).pack(anchor="w", pady=(7, 12))
        self.status_label = ttk.Label(info, textvariable=self.status_var, style="Card.TLabel",
                                      wraplength=680, foreground="#aab8c4")
        self.status_label.pack(anchor="w")
        ttk.Label(outer, text="Every song has a melody and a changing verse / chorus / bridge arrangement. "
                  "The beat changes with each section; export captures the live session, or composes a full song before playback.",
                  style="Sub.TLabel", wraplength=680).pack(anchor="w", pady=(18, 0))
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _update_mood_description(self) -> None:
        mood = MOODS[self.mood_var.get()]
        low, high = mood["tempo"]
        self.description.configure(
            text=f"{mood['description'].capitalize()}. Suggested tempo: {low}–{high} BPM. "
                 f"Scale: {mood['scale']}."
        )
        if not self.playing:
            self.tempo_var.set(max(low, min(high, int(self.tempo_var.get()))))

    def _toggle_vocal_options(self) -> None:
        if self.vocal_enabled_var.get():
            self.vocal_options.pack(fill="x", pady=(2, 0))
        else:
            self.vocal_options.pack_forget()

    def _toggle_instrument_options(self) -> None:
        if self.instrumental_var.get():
            self.instrument_options.pack(fill="x", pady=(2, 0))
        else:
            self.instrument_options.pack_forget()

    def _select_vocal_melody(self) -> None:
        if self.vocal_melody_var.get():
            self.vocal_harmony_var.set(False)
        else:
            self.vocal_harmony_var.set(True)

    def _select_vocal_harmony(self) -> None:
        if self.vocal_harmony_var.get():
            self.vocal_melody_var.set(False)
        else:
            self.vocal_melody_var.set(True)

    def _surprise(self) -> None:
        self.mood_var.set(random.choice(tuple(MOODS)))
        self._update_mood_description()
        if not self.playing:
            self.start()

    def _settings(self, mood: str | None = None) -> Settings:
        try:
            tempo = int(self.tempo_var.get())
        except (ValueError, tk.TclError):
            raise ValueError("Tempo must be a whole number between 40 and 120 BPM.") from None
        if not 40 <= tempo <= 120:
            raise ValueError("Tempo must be between 40 and 120 BPM.")
        numerator, denominator = map(int, self.meter_var.get().split("/"))
        vocals_only = self.vocals_only_var.get()
        vocal_enabled = self.vocal_enabled_var.get() or vocals_only
        vocal_role = "harmony" if self.vocal_harmony_var.get() else "melody"
        lyrics = self.lyrics_text.get("1.0", "end").strip() if vocal_enabled else ""
        vocal_prominent = vocal_enabled and self.vocal_prominent_var.get()
        instrument_override = (
            tuple(name for name, variable in self.instrument_vars.items() if variable.get())
            if self.instrumental_var.get() else None
        )
        return Settings(mood or self.mood_var.get(), self.key_var.get(), tempo,
                        numerator, denominator, vocal_enabled, vocal_role, lyrics,
                        vocal_prominent, vocals_only, instrument_override,
                        self.instrumental_percussion_var.get())

    def start(self) -> None:
        if self.playing:
            return
        try:
            settings = self._settings()
        except ValueError as error:
            messagebox.showerror("Invalid setting", str(error), parent=self.root)
            return
        if _stream_player_command() is None:
            messagebox.showerror(
                "Audio playback unavailable",
                "Install aplay, paplay, or ffplay for continuous audio playback. WAV export remains available.",
                parent=self.root)
            return
        self._clear_recording()
        with tempfile.NamedTemporaryFile(prefix="stillwater-session-", suffix=".pcm", delete=False) as recording:
            self.recording_path = recording.name
        self.session_frames = 0
        self.stop_event.clear()
        self.playing = True
        self.random_each = self.random_each_var.get()
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status_var.set("Composing the first section…")
        self.worker = threading.Thread(target=self._play_loop, args=(settings,), daemon=True)
        self.worker.start()

    def _play_loop(self, initial: Settings) -> None:
        sections: Queue[tuple[bytes | None, str, str | None, str | None]] = Queue(maxsize=2)

        def compose_sections() -> None:
            rng = random.Random()
            section_index = 0
            song_lyrics = initial.lyrics
            try:
                while not self.stop_event.is_set():
                    mood = random.choice(tuple(MOODS)) if self.random_each else initial.mood
                    if ((initial.vocal_enabled or initial.vocals_only) and not initial.lyrics.strip()
                            and section_index % len(SONG_FORM) == 0):
                        song_lyrics = "\n".join(rng.sample(DEFAULT_LYRICS[mood], 3))
                    settings = Settings(
                        mood, initial.key, initial.tempo, initial.numerator,
                        initial.denominator, initial.vocal_enabled,
                        initial.vocal_role, initial.lyrics or song_lyrics,
                        initial.vocal_prominent, initial.vocals_only,
                        initial.instrument_override, initial.instrumental_percussion
                    )
                    pcm, chord_text = generate_section(settings, rng, section_index)
                    while not self.stop_event.is_set():
                        try:
                            sections.put((pcm, chord_text, None, mood), timeout=0.1)
                            section_index += 1
                            break
                        except Full:
                            continue
            except Exception as error:
                while not self.stop_event.is_set():
                    try:
                        sections.put((None, "", str(error), None), timeout=0.1)
                        break
                    except Full:
                        continue

        producer = threading.Thread(target=compose_sections, daemon=True)
        self.producer = producer
        producer.start()
        playback_error: Exception | None = None
        try:
            command = _stream_player_command()
            if command is None:
                raise RuntimeError("Install aplay, paplay, or ffplay for continuous audio playback.")
            self.player = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, bufsize=0)
            beats_per_bar = initial.numerator * 4 / initial.denominator
            bar_frames = int(SECTION_BARS * beats_per_bar * 60 / initial.tempo * SAMPLE_RATE)
            fade_frames = min(int(0.7 * SAMPLE_RATE), bar_frames // 5)
            bar_bytes = bar_frames * 4
            fade_bytes = fade_frames * 4
            split_bytes = bar_bytes - fade_bytes
            previous_tail: bytes | None = None
            while not self.stop_event.is_set():
                try:
                    pcm, chord_text, error, mood = sections.get(timeout=0.1)
                except Empty:
                    continue
                if error:
                    raise RuntimeError(error)
                if pcm is None:
                    continue
                if len(pcm) < bar_bytes:
                    raise RuntimeError("Generated audio section is shorter than its musical length.")
                if mood:
                    self.root.after(0, self._show_section_start, mood)
                self.root.after(0, self.chords_var.set, chord_text)
                current_tail = pcm[split_bytes:bar_bytes]
                if previous_tail is None:
                    if not self._emit_pcm(pcm[:split_bytes]):
                        break
                else:
                    crossfade = _blend_pcm(previous_tail, pcm[:fade_bytes])
                    if not self._emit_pcm(crossfade + pcm[fade_bytes:split_bytes]):
                        break
                previous_tail = current_tail
        except Exception as error:
            self.stop_event.set()
            playback_error = error
        finally:
            self.stop_event.set()
            producer.join()
            while not sections.empty():
                try:
                    sections.get_nowait()
                except Empty:
                    break
            if playback_error is None and self.player is not None and self.player.poll() is None:
                try:
                    if self.player.stdin is not None:
                        self.player.stdin.close()
                    self.player.wait(timeout=10)
                    if self.player.returncode != 0:
                        detail = self.player.stderr.read().decode(errors="replace").strip() if self.player.stderr else ""
                        playback_error = RuntimeError(
                            f"Audio player exited with code {self.player.returncode}. {detail}".strip())
                except (BrokenPipeError, OSError, subprocess.TimeoutExpired) as error:
                    self.player.terminate()
                    playback_error = RuntimeError(f"Could not finish the audio stream: {error}")
            elif self.player is not None and self.player.poll() is None:
                self.player.terminate()
            self.player = None
            if playback_error is not None:
                self.root.after(0, self._playback_error, str(playback_error))
            self.root.after(0, self._playback_finished)

    def _emit_pcm(self, pcm: bytes) -> bool:
        if self.player is None or self.player.stdin is None:
            raise RuntimeError("The audio stream is not open.")
        block_size = 16 * 1024
        for offset in range(0, len(pcm), block_size):
            if self.stop_event.is_set():
                return False
            block = pcm[offset:offset + block_size]
            if self.player.poll() is not None:
                detail = self.player.stderr.read().decode(errors="replace").strip() if self.player.stderr else ""
                raise RuntimeError(f"Audio player stopped unexpectedly. {detail}".strip())
            view = memoryview(block)
            while view:
                written = self.player.stdin.write(view)
                if not written:
                    raise BrokenPipeError("Audio player closed its input stream.")
                view = view[written:]
            with self.record_lock:
                if self.recording_path:
                    with open(self.recording_path, "ab") as recording:
                        recording.write(block)
                    self.session_frames += len(block) // 4
        return True

    def _show_section_start(self, mood: str) -> None:
        self.status_var.set(f"Generating a {mood.lower()} section…")
        self.description.configure(
            text=f"Now in {mood.lower()} mode — {MOODS[mood]['description']}. "
                 f"Scale: {MOODS[mood]['scale']}."
        )

    def stop(self) -> None:
        if not self.playing:
            return
        self.stop_event.set()
        self.status_var.set("Stopping playback…")

    def _playback_error(self, error: str) -> None:
        self.status_var.set("Generation or playback failed.")
        messagebox.showerror("Generation or playback failed", error, parent=self.root)

    def _playback_finished(self) -> None:
        self.playing = False
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        if self.status_var.get().startswith("Generation or playback failed"):
            return
        if self.stop_event.is_set():
            self.status_var.set("Stopped. Start again whenever you want.")
        else:
            self.status_var.set("Ready.")

    def export(self) -> None:
        try:
            settings = self._settings()
        except ValueError as error:
            messagebox.showerror("Invalid setting", str(error), parent=self.root)
            return
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Export generated session",
            defaultextension=".wav", filetypes=(("WAV audio", "*.wav"),))
        if not path:
            return
        with self.record_lock:
            has_session = bool(self.recording_path and self.session_frames)
            recording_path = self.recording_path
        if has_session and recording_path:
            self.status_var.set("Capturing the generated session for export…")
            self.record_lock.acquire()
            threading.Thread(
                target=self._export_session_worker,
                args=(path, recording_path), daemon=True).start()
        else:
            self.status_var.set("Composing a verse, chorus, and bridge…")
            threading.Thread(target=self._export_worker, args=(settings, path), daemon=True).start()

    def _export_worker(self, settings: Settings, path: str) -> None:
        try:
            pcm, chord_text = generate_song(settings)
            write_wav(path, pcm)
            self.root.after(0, self._export_finished, path, chord_text, False)
        except Exception as error:
            self.root.after(0, self._export_error, str(error))

    def _export_session_worker(self, path: str, recording_path: str) -> None:
        snapshot_path = ""
        lock_held = True
        try:
            with tempfile.NamedTemporaryFile(prefix="stillwater-export-", suffix=".pcm", delete=False) as snapshot:
                snapshot_path = snapshot.name
                with open(recording_path, "rb") as recording:
                    shutil.copyfileobj(recording, snapshot)
            self.record_lock.release()
            lock_held = False
            write_wav_from_file(path, snapshot_path)
            self.root.after(0, self._export_finished, path, "", True)
        except Exception as error:
            if lock_held:
                self.record_lock.release()
            self.root.after(0, self._export_error, str(error))
        finally:
            if snapshot_path:
                try:
                    os.unlink(snapshot_path)
                except FileNotFoundError:
                    pass

    def _export_error(self, error: str) -> None:
        self.status_var.set("Export failed.")
        messagebox.showerror("Export failed", error, parent=self.root)

    def _export_finished(self, path: str, chord_text: str, is_session: bool) -> None:
        if chord_text:
            self.chords_var.set(chord_text)
        description = "session so far" if is_session else "complete song"
        self.status_var.set(f"Exported {description}: {Path(path).name}")

    def _clear_recording(self) -> None:
        with self.record_lock:
            if self.recording_path:
                try:
                    os.unlink(self.recording_path)
                except FileNotFoundError:
                    pass
            self.recording_path = None
            self.session_frames = 0

    def _close(self) -> None:
        self.stop()
        self._wait_for_shutdown()

    def _wait_for_shutdown(self) -> None:
        active = any(thread is not None and thread.is_alive()
                     for thread in (self.worker, self.producer))
        if active:
            self.root.after(100, self._wait_for_shutdown)
        else:
            self._clear_recording()
            self.root.destroy()


def main() -> None:
    root = tk.Tk()
    AmbientGeneratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

