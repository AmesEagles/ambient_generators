"""A small, dependency-free singing voice synthesizer with a Tkinter GUI.

The voice is a synthetic source-filter model; pronunciation remains an
approximation rather than natural speech.
"""

import math
import os
import platform
import random
import hashlib
import shutil
import struct
import subprocess
import tempfile
import threading
import wave
from dataclasses import dataclass
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


SAMPLE_RATE = 22050
VOWEL_FORMANTS = {
    "ae": (700, 1700, 2600, 3400, 4300),
    "ah": (750, 1100, 2500, 3400, 4300),
    "eh": (530, 1840, 2480, 3500, 4400),
    "ee": (270, 2290, 3010, 3600, 4500),
    "ih": (390, 1990, 2550, 3500, 4400),
    "aw": (570, 850, 2400, 3300, 4200),
    "oh": (490, 900, 2400, 3300, 4200),
    "oo": (300, 870, 2240, 3300, 4200),
    "u_short": (400, 1350, 2400, 3400, 4300),
    "uh": (600, 1170, 2400, 3400, 4300),
    "er": (500, 1350, 1690, 3300, 4200),
    "ə": (500, 1500, 2500, 3400, 4300),
}
VOWEL_CHOICES = {
    "Text vowels": None,
    "a (cat)": "ae",
    "ah (father)": "ah",
    "e (bed)": "eh",
    "ee (see)": "ee",
    "i (sit)": "ih",
    "aw (law)": "aw",
    "o (go)": "oh",
    "oo (moon)": "oo",
    "u (book)": "u_short",
    "uh (cup)": "uh",
}
VOWEL_MAP = {"a": "ae", "e": "eh", "i": "ih", "o": "oh", "u": "uh", "y": "ee"}
DIPHTHONGS = {
    "ai": ("ah", "ee"), "ay": ("ah", "ee"),
    "ea": ("ee", "ee"), "ei": ("ee", "ee"),
    "oa": ("oh", "oo"), "oe": ("oh", "oo"),
    "oi": ("aw", "ee"), "oy": ("aw", "ee"),
    "ou": ("ah", "oo"), "ow": ("ah", "oo"),
}
CONSONANT_DIGRAPHS = {
    "sh": "sh", "ch": "ch", "th": "th", "ph": "f", "ng": "ng",
    "wh": "w", "qu": "kw", "ck": "k", "tch": "ch", "dge": "j",
    "tion": "shən",
}
VOICED_TH_WORDS = {
    "the", "this", "that", "these", "those", "they", "their", "there",
    "then", "than", "them", "thus", "though",
}
FINAL_E_WORDS = {"be", "he", "she", "me", "we", "the"}
SHORT_OO_WORDS = {
    "book", "cook", "foot", "good", "hood", "look", "stood", "took",
    "wood", "wool", "could", "should", "would",
}
ARPABET = {
    "AA": ("vowel", "ah"), "AE": ("vowel", "ae"), "AH": ("vowel", "uh"),
    "AO": ("vowel", "aw"), "AW": ("vowel", ("ah", "oo")),
    "AY": ("vowel", ("ah", "ee")), "EH": ("vowel", "eh"),
    "ER": ("vowel", "er"), "EY": ("vowel", ("eh", "ee")),
    "IH": ("vowel", "ih"), "IY": ("vowel", "ee"),
    "OW": ("vowel", ("oh", "oo")), "OY": ("vowel", ("aw", "ee")),
    "UH": ("vowel", "u_short"), "UW": ("vowel", "oo"),
    "B": ("consonant", "b"), "CH": ("consonant", "ch"),
    "D": ("consonant", "d"), "DH": ("consonant", "dh"),
    "F": ("consonant", "f"), "G": ("consonant", "g"),
    "HH": ("consonant", "h"), "JH": ("consonant", "j"),
    "K": ("consonant", "k"), "L": ("consonant", "l"),
    "M": ("consonant", "m"), "N": ("consonant", "n"),
    "NG": ("consonant", "ng"), "P": ("consonant", "p"),
    "R": ("consonant", "r"), "S": ("consonant", "s"),
    "SH": ("consonant", "sh"), "T": ("consonant", "t"),
    "TH": ("consonant", "th"), "V": ("consonant", "v"),
    "W": ("consonant", "w"), "Y": ("consonant", "y"),
    "Z": ("consonant", "z"), "ZH": ("consonant", "zh"),
}
PRONUNCIATION_DICTIONARY = {
    "a": ("AH0",), "about": ("AH0", "B", "AW1", "T"),
    "beautiful": ("B", "Y", "UW1", "T", "AH0", "F", "AH0", "L"),
    "can": ("K", "AE1", "N"), "clearly": ("K", "L", "IH1", "R", "L", "IY0"),
    "fox": ("F", "AA1", "K", "S"), "from": ("F", "R", "AH1", "M"),
    "hello": ("HH", "AH0", "L", "OW1"),
    "how": ("HH", "AW1"), "i": ("AY1",), "is": ("IH1", "Z"),
    "keep": ("K", "IY1", "P"), "love": ("L", "AH1", "V"),
    "music": ("M", "Y", "UW1", "Z", "IH0", "K"),
    "night": ("N", "AY1", "T"), "quick": ("K", "W", "IH1", "K"),
    "sing": ("S", "IH1", "NG"), "singing": ("S", "IH1", "NG", "IH0", "NG"),
    "the": ("DH", "AH0"), "through": ("TH", "R", "UW1"),
    "voice": ("V", "OY1", "S"), "world": ("W", "ER1", "L", "D"),
    "brown": ("B", "R", "AW1", "N"), "dog": ("D", "AO1", "G"),
    "jumps": ("JH", "AH1", "M", "P", "S"),
    "lazy": ("L", "EY1", "Z", "IY0"), "over": ("OW1", "V", "ER0"),
}
NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
NOTES = [f"{NOTE_NAMES[n % 12]}{n // 12 - 1}" for n in range(36, 85)]
NOTE_TO_MIDI = {name: number for number, name in zip(range(36, 85), NOTES)}


@dataclass
class Phoneme:
    """Scheduled phoneme plus the voice and performance controls used to render it."""

    identity: str
    category: str
    duration: float
    start: float = 0.0
    end: float = 0.0
    target_pitch: float = 0.0
    intensity: float = 1.0
    formants: tuple = ()
    voiced: bool = False
    breathiness: float = 0.0
    tension: float = 0.5
    transition: float = 0.0


class PhonemeParser:
    """Pronunciation dictionary with spelling-based fallback for unknown words."""

    @staticmethod
    def parse(text, vowel_override=None, phoneme_override=None):
        if phoneme_override and phoneme_override.strip():
            units = []
            for symbol in phoneme_override.upper().split():
                base_symbol = symbol.rstrip("012")
                if base_symbol not in ARPABET:
                    raise ValueError(f"Unsupported ARPAbet phoneme: {symbol}")
                kind, sound = ARPABET[base_symbol]
                units.append((kind, (vowel_override or sound)
                              if kind == "vowel" else sound))
            return units
        return split_phonemes(text, vowel_override)


class PhonemeTiming:
    """Assign short consonant gestures and sustained vowel nuclei."""

    @staticmethod
    def plan(units, vowel_duration, target_pitch, voice_model):
        events = []
        cursor = 0.0
        for kind, value in units:
            if kind == "break":
                duration = float(value)
                identity = "pause"
            elif kind == "vowel":
                duration = vowel_duration
                identity = value
            else:
                identity = value
                duration = voice_model.consonant_duration(value, vowel_duration)
            category = kind
            formants = ()
            voiced = kind == "vowel"
            if kind == "vowel":
                vowel_name = value[0] if isinstance(value, tuple) else value
                formants = VOWEL_FORMANTS.get(vowel_name, VOWEL_FORMANTS["ə"])
            elif kind == "consonant":
                voiced = value in {"b", "d", "g", "v", "z", "j", "dh",
                                   "m", "n", "ng", "l", "r", "w", "y"}
            event = Phoneme(
                identity=identity,
                category=category,
                duration=duration,
                start=cursor,
                end=cursor + duration,
                target_pitch=target_pitch,
                intensity=voice_model.intensity,
                formants=formants,
                voiced=voiced,
                breathiness=voice_model.breathiness,
                tension=voice_model.tension,
            )
            events.append(event)
            cursor = event.end
        for index, event in enumerate(events[:-1]):
            following = events[index + 1]
            if event.voiced and following.voiced:
                event.transition = min(
                    0.006, event.duration * 0.12, following.duration * 0.12
                )
        return events


@dataclass(frozen=True)
class VoiceModel:
    """Voice identity settings, kept separate from note/performance settings."""

    formant_scale: float
    intensity: float = 1.0
    breathiness: float = 0.001
    tension: float = 0.5
    vocal_weight: float = 0.5
    vibrato_rate: float = 5.2

    @classmethod
    def preset(cls, name):
        if name == "Female":
            return cls(formant_scale=1.12)
        return cls(formant_scale=0.92)

    @staticmethod
    def consonant_duration(sound, vowel_duration):
        if sound in {"s", "f", "h", "sh", "th", "dh", "v", "z", "ch", "j", "zh"}:
            return min(0.10, max(0.065, vowel_duration * 0.30))
        if sound in {"p", "b", "t", "d", "k", "g"}:
            return min(0.075, max(0.045, vowel_duration * 0.24))
        if sound in {"m", "n", "ng", "l", "r", "w", "y"}:
            return min(0.085, max(0.05, vowel_duration * 0.28))
        return min(0.07, max(0.05, vowel_duration * 0.25))


class PerformanceEngine:
    """Plan phoneme events and render them through the procedural voice backend."""

    def render(self, text, midi_note, voice_name, vowel_override, vibrato_depth,
               vibrato_rate, vowel_duration, phoneme_override=None,
               humanization=0.35):
        voice_model = VoiceModel.preset(voice_name)
        units = PhonemeParser.parse(text, vowel_override, phoneme_override)
        events = PhonemeTiming.plan(
            units, vowel_duration, midi_note, voice_model
        )
        human_model = HumanPerformanceModel(
            humanization=humanization,
            seed=_stable_seed(text, midi_note, voice_name, phoneme_override)
        )
        return AudioRenderer(voice_model).render(
            events, midi_note, vibrato_depth, vibrato_rate,
            human_model=human_model,
        )


class AudioRenderer:
    """Render scheduled phonemes and concatenate their PCM samples."""

    def __init__(self, voice_model):
        self.voice_model = voice_model

    def render(self, events, midi_note, vibrato_depth, vibrato_rate,
               human_model=None):
        human_model = human_model or HumanPerformanceModel()
        base_frequency = 440.0 * 2 ** ((midi_note - 69) / 12.0)
        samples = []
        for index, event in enumerate(events):
            offset = len(samples)
            event_seed = human_model.seed_for_event(index)
            if event.category == "vowel":
                segment = _render_voiced_vowel(
                    event.identity, event.duration, base_frequency,
                    vibrato_depth, vibrato_rate, self.voice_model.formant_scale,
                    offset, humanization=human_model.humanization, seed=event_seed,
                    vocal_weight=self.voice_model.vocal_weight,
                    breathiness=self.voice_model.breathiness,
                    tension=self.voice_model.tension
                )
            elif event.category == "consonant":
                segment = _render_consonant(
                    event.identity, event.duration, base_frequency,
                    vibrato_depth, vibrato_rate, offset,
                    seed=event_seed, humanization=human_model.humanization
                )
            else:
                segment = [0.0] * int(SAMPLE_RATE * event.duration)
            transition = events[index - 1].transition if index else 0.0
            _append_phoneme(samples, segment, transition)
        peak = max((abs(sample) for sample in samples), default=0.0)
        if peak:
            samples = [sample * (0.92 / peak) for sample in samples]
        return samples


@dataclass(frozen=True)
class HumanPerformanceModel:
    """Correlated, deterministic singer variation shared across a phrase."""

    humanization: float = 0.35
    seed: int = 0

    def seed_for_event(self, index):
        if self.humanization <= 0:
            return 0
        return self.seed + index * 7919


def split_phonemes(text, vowel_override):
    """Map common English spelling patterns to approximate phoneme units."""
    units = []
    current = []

    def append_word(word):
        dictionary_phones = PRONUNCIATION_DICTIONARY.get(word)
        if dictionary_phones:
            for phone in dictionary_phones:
                base_phone = phone.rstrip("012")
                kind, sound = ARPABET[base_phone]
                units.append((kind, vowel_override or sound if kind == "vowel" else sound))
            return
        if word == "father":
            units.extend((
                ("consonant", "f"), ("vowel", vowel_override or "ah"),
                ("consonant", "dh"), ("vowel", vowel_override or "ə"),
                ("consonant", "r"),
            ))
            return
        i = 0
        while i < len(word):
            if word[i] in "'’":
                i += 1
                continue
            # A final silent e is a useful spelling cue for many common words.
            if (word not in FINAL_E_WORDS and word[i] == "e"
                    and i == len(word) - 1 and i > 1
                    and word[i - 1] not in VOWEL_MAP):
                i += 1
                continue

            matched = False
            for spelling in ("tion", "tch", "dge"):
                if word.startswith(spelling, i):
                    if spelling == "tion":
                        units.extend((
                            ("consonant", "sh"),
                            ("vowel", vowel_override or "ə"),
                            ("consonant", "n"),
                        ))
                    else:
                        units.append(("consonant", CONSONANT_DIGRAPHS[spelling]))
                    i += len(spelling)
                    matched = True
                    break
            if matched:
                continue

            pair = word[i:i + 2]
            if pair in {"ah", "aw", "au", "uh"}:
                units.append(("vowel", vowel_override or {
                    "ah": "ah", "aw": "aw", "au": "aw", "uh": "uh",
                }[pair]))
                i += 2
                continue
            if pair in CONSONANT_DIGRAPHS:
                if pair == "qu":
                    units.extend((("consonant", "k"), ("consonant", "w")))
                elif pair == "th" and word in VOICED_TH_WORDS:
                    units.append(("consonant", "dh"))
                else:
                    units.append(("consonant", CONSONANT_DIGRAPHS[pair]))
                i += 2
                continue
            if pair in ("oo", "ee"):
                oo_sound = "u_short" if word in SHORT_OO_WORDS else "oo"
                units.append(("vowel", vowel_override or (oo_sound if pair == "oo" else "ee")))
                i += 2
                continue
            if pair in DIPHTHONGS:
                units.append(("vowel", vowel_override or DIPHTHONGS[pair]))
                i += 2
                continue

            char = word[i]
            if char in VOWEL_MAP:
                # Initial y is a consonant ("yes"); final y is a vowel ("my").
                if char == "y" and i == 0:
                    units.append(("consonant", "y"))
                else:
                    long_vowel = (
                        i + 2 == len(word) - 1
                        and word[-1] == "e"
                        and word[i + 1] not in VOWEL_MAP
                    )
                    if long_vowel and char in "aiou":
                        glide = {"a": ("ae", "ee"), "i": ("ah", "ee"),
                                 "o": ("oh", "oo"), "u": ("ee", "oo")}[char]
                        units.append(("vowel", vowel_override or glide))
                    elif char == "a" and i + 1 < len(word) and word[i + 1] == "r":
                        units.append(("vowel", vowel_override or "ah"))
                    elif (char == "a" and i + 2 < len(word)
                          and word[i + 1:i + 3] in {"ll", "lk", "lt"}):
                        units.append(("vowel", vowel_override or "aw"))
                    else:
                        units.append(("vowel", vowel_override or VOWEL_MAP[char]))
            else:
                sound = char
                if char == "c":
                    sound = "s" if i + 1 < len(word) and word[i + 1] in "eiy" else "k"
                elif char == "g" and i + 1 < len(word) and word[i + 1] in "eiy":
                    sound = "j"
                elif char == "x":
                    units.extend((("consonant", "k"), ("consonant", "s")))
                    i += 1
                    continue
                elif char == "q":
                    units.extend((("consonant", "k"), ("consonant", "w")))
                    i += 1
                    continue
                units.append(("consonant", sound))
            i += 1

    for char in text.lower():
        if char.isalpha() or char in "'’":
            current.append(char)
        else:
            if current:
                append_word("".join(current))
                current.clear()
            if char.isspace():
                pause = 0.11
            elif char in ",;:":
                pause = 0.24
            elif char in ".!?":
                pause = 0.36
            else:
                continue
            if units and units[-1][0] == "break":
                units[-1] = ("break", max(units[-1][1], pause))
            else:
                units.append(("break", pause))
    if current:
        append_word("".join(current))
    return units


def _stable_seed(*values):
    payload = "|".join(str(value) for value in values).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _glottal_source(count, base_frequency, vibrato_depth, vibrato_rate,
                    sample_offset, breathiness=0.0, humanization=0.35,
                    seed=0, tension=0.5, vocal_weight=0.5):
    """Generate cycle-varying glottal pulses, pitch behavior, and aspiration."""
    output = []
    phase = (sample_offset * base_frequency / SAMPLE_RATE) % 1.0
    rng = random.Random((seed if humanization > 0 else 0) + sample_offset + 479)
    pitch_jitter = 0.0
    drift = 0.0
    cycle_pitch_offset = 0.0
    open_quotient = 0.66
    closure_shape = 1.35
    cycle_gain = 1.0
    aspiration_state = 0.0
    vibrato_phase = rng.uniform(0, 2 * math.pi)
    vibrato_rate_state = vibrato_rate
    note_attack = min(0.045, max(0.008, count / SAMPLE_RATE * 0.16))
    note_release = min(0.035, max(0.008, count / SAMPLE_RATE * 0.12))
    humanization = max(0.0, min(1.0, humanization))
    for index in range(count):
        t = (sample_offset + index) / SAMPLE_RATE
        local_time = index / SAMPLE_RATE
        attack_progress = min(1.0, local_time / note_attack)
        release_progress = min(1.0, (count / SAMPLE_RATE - local_time) / note_release)
        envelope = min(attack_progress, release_progress)
        onset_offset = -0.12 * (1.0 - attack_progress) * humanization
        settle = 0.035 * math.exp(-local_time / 0.12) * humanization
        pitch_jitter = (
            0.992 * pitch_jitter
            + rng.uniform(-0.000045, 0.000045) * humanization
        )
        drift = (
            0.9994 * drift
            + rng.uniform(-0.0000045, 0.0000045) * humanization
        )

        # Slow vibrato onset and gradual, slightly irregular rate/depth changes.
        vibrato_onset = min(1.0, max(0.0, (local_time - 0.16) / 0.28))
        vibrato_onset = vibrato_onset * vibrato_onset * (3 - 2 * vibrato_onset)
        vibrato_rate_state = 0.999 * vibrato_rate_state + 0.001 * (
            vibrato_rate + rng.uniform(-0.12, 0.12) * humanization
        )
        vibrato_phase += 2 * math.pi * vibrato_rate_state / SAMPLE_RATE
        vibrato_shape = (
            math.sin(vibrato_phase)
            + 0.13 * math.sin(2 * vibrato_phase + 0.35)
            + 0.04 * math.sin(3 * vibrato_phase - 0.2)
        )
        vibrato_modulation = 1.0 + 0.09 * math.sin(2 * math.pi * 0.31 * local_time)
        vibrato = vibrato_depth * vibrato_onset * vibrato_modulation * vibrato_shape
        if release_progress < 1.0:
            vibrato *= release_progress

        frequency = base_frequency * 2 ** (
            (vibrato + onset_offset + settle + cycle_pitch_offset
             + (drift + pitch_jitter) * 12.0) / 12.0
        )
        advanced_phase = phase + frequency / SAMPLE_RATE
        cycle_crossed = advanced_phase >= 1.0
        phase = advanced_phase % 1.0

        if cycle_crossed:
            cycle_pitch_offset = rng.uniform(-0.008, 0.008) * humanization
            open_quotient = min(0.78, max(
                0.48,
                0.66 - 0.10 * (tension - 0.5)
                - 0.06 * (vocal_weight - 0.5)
                + rng.uniform(-0.018, 0.018) * humanization
            ))
            closure_shape = min(2.1, max(
                0.85,
                1.35 + 0.7 * (tension - 0.5)
                + rng.uniform(-0.12, 0.12) * humanization
            ))
            cycle_gain = min(1.08, max(
                0.92, 1.0 + rng.uniform(-0.025, 0.025) * humanization
            ))

        if phase < open_quotient:
            pulse = math.sin(math.pi * phase / open_quotient) ** closure_shape
        else:
            pulse = 0.0

        # Aspiration follows the vocal pulse and is strongest during soft onset/release.
        raw_noise = rng.uniform(-1.0, 1.0)
        aspiration_state += 0.20 * (raw_noise - aspiration_state)
        aspiration_level = breathiness * (
            1.0 + 1.8 * (1.0 - vocal_weight) + 0.8 * (1.0 - tension)
        )
        aspiration_level += 0.012 * humanization * (1.0 - envelope)
        noise = aspiration_state * aspiration_level
        phrase_dynamics = (
            0.92 + 0.08 * envelope
            + humanization * (
                0.012 * math.sin(2 * math.pi * 0.37 * local_time + 0.7)
                + 0.006 * math.sin(2 * math.pi * 0.83 * local_time + 1.3)
            )
        )
        output.append(
            (pulse * cycle_gain * phrase_dynamics * envelope) + noise
        )
    return output


def _apply_formants(source, centers, formant_scale=1.0, bandwidths=None, states=None):
    """Shape the voice with parallel vocal-tract resonators."""
    if bandwidths is None:
        bandwidths = (110, 145, 210, 340, 520)
    if states is None:
        states = [(0.0, 0.0)] * len(centers)
    next_states = []
    output = [0.0] * len(source)
    weights = (1.0, 0.82, 0.62, 0.34, 0.19)
    for center, bandwidth, weight, (y1, y2) in zip(
            centers, bandwidths, weights, states):
        center = min(SAMPLE_RATE * 0.47, center * formant_scale)
        radius = math.exp(-math.pi * bandwidth / SAMPLE_RATE)
        cosine = 2 * radius * math.cos(2 * math.pi * center / SAMPLE_RATE)
        radius_squared = radius * radius
        # Unit gain at resonance prevents the formant stack from collapsing
        # the voiced source and exposing its low-level breath noise.
        input_gain = (1 - radius) ** 2
        for index, sample in enumerate(source):
            value = input_gain * sample + cosine * y1 - radius_squared * y2
            output[index] += value * weight
            y2, y1 = y1, value
        next_states.append((y1, y2))
    return output, next_states


def _match_rms(samples, target):
    """Keep phoneme loudness balanced so noise consonants do not bury vowels."""
    rms = math.sqrt(sum(sample * sample for sample in samples) / max(1, len(samples)))
    if rms <= 1e-9:
        return samples
    gain = target / rms
    return [sample * gain for sample in samples]


def _render_voiced_vowel(vowel, duration, base_frequency, vibrato_depth,
                         vibrato_rate, formant_scale, sample_offset,
                         humanization=0.35, seed=0, vocal_weight=0.5,
                         breathiness=0.001, tension=0.5):
    """Synthesize vowel timbre by shaping a glottal pulse with vocal-tract resonances."""
    count = max(1, int(SAMPLE_RATE * duration))
    if isinstance(vowel, tuple) and isinstance(vowel[0], str):
        start_formants = VOWEL_FORMANTS[vowel[0]]
        end_formants = VOWEL_FORMANTS[vowel[1]]
    elif isinstance(vowel, tuple):
        start_formants = end_formants = vowel
    else:
        start_formants = end_formants = VOWEL_FORMANTS[vowel]
    source = _glottal_source(
        count, base_frequency, vibrato_depth, vibrato_rate, sample_offset,
        breathiness=breathiness, humanization=humanization, seed=seed,
        tension=tension, vocal_weight=vocal_weight
    )

    # Move formants gradually during diphthongs, preserving resonator state.
    output = []
    block_size = 48
    filter_states = None
    rng = random.Random((seed if humanization > 0 else 0) + 12289)
    formant_drift = [0.0, 0.0, 0.0, 0.0, 0.0]
    for start in range(0, count, block_size):
        end = min(count, start + block_size)
        blend = min(1.0, max(0.0, ((start + end) / (2 * count) - 0.12) / 0.76))
        centers_list = []
        for formant_index, (first, last) in enumerate(zip(start_formants, end_formants)):
            target = first + (last - first) * blend
            formant_drift[formant_index] = (
                0.985 * formant_drift[formant_index]
                + rng.uniform(-0.0015, 0.0015) * humanization
            )
            # Register affects the vocal configuration, not only the pitch oscillator.
            register_shift = max(-0.035, min(0.035, (base_frequency - 220) / 9000))
            modulation = (
                1.0 + formant_drift[formant_index]
                + register_shift * (0.7 if formant_index < 2 else 0.35)
            )
            centers_list.append(target * modulation)
        centers = tuple(centers_list)
        chunk, filter_states = _apply_formants(
            source[start:end], centers, formant_scale, states=filter_states
        )
        output.extend(chunk)

    # A short edge ramp avoids clicks but keeps consonants and vowel attacks crisp.
    for index in range(count):
        attack = min(1.0, index / (SAMPLE_RATE * 0.003))
        release = min(1.0, (count - 1 - index) / (SAMPLE_RATE * 0.008))
        output[index] *= min(attack, release)
    vowel_key = vowel[0] if isinstance(vowel, tuple) else vowel
    target_level = {
        "ae": 0.17, "ah": 0.17, "eh": 0.16, "ee": 0.15,
        "ih": 0.15, "aw": 0.16, "oh": 0.15, "oo": 0.14,
        "u_short": 0.14,
        "uh": 0.16, "er": 0.15, "ə": 0.14,
    }.get(vowel_key, 0.16)
    # Preserve the physical attack/release envelope; normalize only gently.
    output = _match_rms(output, target_level)
    return output


def _append_phoneme(output, segment, transition_seconds=0.0):
    """Join neighboring sounds with a short equal-power overlap."""
    overlap = min(
        int(SAMPLE_RATE * transition_seconds), len(output), len(segment)
    )
    if overlap:
        start = len(output) - overlap
        for index in range(overlap):
            amount = (index + 1) / (overlap + 1)
            output[start + index] = (
                output[start + index] * (1 - amount) + segment[index] * amount
            )
        output.extend(segment[overlap:])
    else:
        output.extend(segment)


def _render_consonant(sound, duration, base_frequency, vibrato_depth,
                      vibrato_rate, sample_offset, seed=0, humanization=0.35):
    """Give stops, fricatives, nasals, and approximants distinct sound cues."""
    count = max(1, int(SAMPLE_RATE * duration))
    voiced = {
        "b", "d", "g", "v", "z", "j", "dh", "zh", "m", "n", "ng",
        "l", "r", "w", "y",
    }
    stops = {"p", "b", "t", "d", "k", "g"}
    fricatives = {"s", "f", "h", "sh", "th", "dh", "zh", "v", "z"}
    affricates = {"ch", "j"}
    nasal_formants = {
        "m": (250, 1000, 2200), "n": (300, 1700, 2600),
        "ng": (300, 1200, 2200),
    }
    if sound in nasal_formants:
        output = _render_voiced_vowel(
            nasal_formants[sound], duration, base_frequency, vibrato_depth,
            vibrato_rate, 1.0, sample_offset, humanization=humanization,
            seed=seed
        )
        return _match_rms(output, 0.12)
    if sound in {"l", "r", "w", "y"}:
        formants = {
            "l": (400, 1200, 2800), "r": (350, 1100, 1600),
            "w": (300, 700, 2200), "y": (300, 2100, 3000),
        }[sound]
        segment = _render_voiced_vowel(
            formants, duration, base_frequency, vibrato_depth,
            vibrato_rate, 1.0, sample_offset, humanization=humanization,
            seed=seed
        )
        return _match_rms(segment, 0.10)

    output = []
    random_source = random.Random(seed + sample_offset + ord(sound[0]))
    previous_noise = 0.0
    low_noise = 0.0
    voiced_consonant = sound in voiced
    if sound in fricatives or sound in affricates or sound in stops:
        noise_source = [random_source.uniform(-1.0, 1.0) for _ in range(count)]
        if sound in {"s", "z", "sh", "zh", "th", "dh", "ch"}:
            cutoff = 0.16 if sound in {"s", "z"} else 0.07
            filtered_noise = []
            low = 0.0
            for value in noise_source:
                low += cutoff * (value - low)
                filtered_noise.append(value - low)
            noise_source = filtered_noise
    else:
        noise_source = []
    if voiced_consonant:
        voice_source = _glottal_source(
            count, base_frequency, vibrato_depth, vibrato_rate, sample_offset,
            breathiness=0.008, humanization=humanization, seed=seed
        )
    else:
        voice_source = []
    pulse = int(SAMPLE_RATE * (0.018 if sound in {"p", "b", "t", "d", "k", "g"} else 0.012))
    for index in range(count):
        noise = noise_source[index] if noise_source else random_source.uniform(-1.0, 1.0)
        low_noise += 0.12 * (noise - low_noise)
        high_noise = noise - previous_noise * 0.82
        previous_noise = noise
        if sound in stops:
            if index < count - pulse:
                sample = voice_source[index] * 0.06 if sound in {"b", "d", "g"} else 0.0
            else:
                envelope = (count - index) / max(1, pulse)
                sample = noise_source[index] * envelope * (
                    0.38 if sound in {"p", "t", "k"} else 0.2
                )
        elif sound in affricates:
            if index < count - pulse:
                sample = voice_source[index] * 0.06 if sound == "j" else 0.0
            else:
                sample = noise_source[index] * (0.3 if sound == "ch" else 0.18)
        elif sound in fricatives:
            if sound in {"s", "z"}:
                sample = high_noise * 0.29
            elif sound == "zh":
                sample = (noise - low_noise) * 0.20 + voice_source[index] * 0.045
            elif sound in {"sh", "ch"}:
                sample = (noise - low_noise) * 0.25
            elif sound == "dh":
                sample = noise * 0.07 + voice_source[index] * 0.045
            else:
                sample = noise * 0.14
            if sound in {"v", "z"}:
                sample += voice_source[index] * 0.06
        elif voiced_consonant:
            sample = voice_source[index] * 0.075
        else:
            sample = noise * 0.08
        if sound in stops:
            attack_seconds = 0.0008
            release_seconds = 0.003
        elif sound in fricatives or sound in affricates:
            attack_seconds = 0.0015
            release_seconds = 0.004
        else:
            attack_seconds = 0.003
            release_seconds = 0.006
        edge = min(1.0, index / (SAMPLE_RATE * attack_seconds),
                   (count - 1 - index) / (SAMPLE_RATE * release_seconds))
        output.append(sample * max(0.0, edge))
    if sound in fricatives or sound in affricates:
        target_level = 0.065
    elif sound in stops:
        target_level = 0.05
    elif voiced_consonant:
        target_level = 0.095
    else:
        target_level = 0.06
    return _match_rms(output, target_level)


def synthesize(text, midi_note, voice, vowel_override, vibrato_depth,
               vibrato_rate, vowel_duration, phoneme_override=None,
               humanization=0.35):
    """Render a phrase through pronunciation, timing, and synthesis stages."""
    if not text.strip():
        raise ValueError("Enter a word or phrase before singing.")
    return PerformanceEngine().render(
        text, midi_note, voice, vowel_override, vibrato_depth,
        vibrato_rate, vowel_duration, phoneme_override, humanization
    )


def write_wav(path, samples):
    with wave.open(path, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        pcm = bytearray()
        for sample in samples:
            pcm.extend(struct.pack("<h", int(max(-1.0, min(1.0, sample)) * 32767)))
        output.writeframes(pcm)


def playback_command(path):
    system = platform.system()
    if system == "Darwin":
        player = shutil.which("afplay")
        return [player, path] if player else None
    if system == "Windows":
        return "winsound"
    for executable in ("aplay", "paplay"):
        player = shutil.which(executable)
        if player:
            return [player, path]
    return None


class VocalSynthApp:
    def __init__(self, root):
        self.root = root
        root.title("Vocal Synthesizer")
        root.minsize(460, 520)
        self.status = tk.StringVar(value="Enter text, choose a note, then sing or save.")
        self.text = tk.StringVar(value="Hello")
        self.phonemes = tk.StringVar(value="")
        self.note = tk.StringVar(value="C4")
        self.voice = tk.StringVar(value="Female")
        self.vowel = tk.StringVar(value="Text vowels")
        self.depth = tk.DoubleVar(value=0.25)
        self.rate = tk.DoubleVar(value=5.0)
        self.duration = tk.DoubleVar(value=0.24)
        self.humanization = tk.DoubleVar(value=0.35)
        self._build_ui()

    def _build_ui(self):
        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Words to sing").grid(row=0, column=0, sticky="w", pady=6)
        ttk.Entry(frame, textvariable=self.text).grid(
            row=0, column=1, columnspan=2, sticky="ew", pady=6
        )
        ttk.Label(frame, text="ARPAbet override (optional)").grid(
            row=1, column=0, sticky="w", pady=6
        )
        ttk.Entry(frame, textvariable=self.phonemes).grid(
            row=1, column=1, columnspan=2, sticky="ew", pady=6
        )
        ttk.Label(frame, text="Note").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Combobox(frame, textvariable=self.note, values=NOTES, state="readonly",
                     width=10).grid(row=2, column=1, sticky="w", pady=6)
        ttk.Label(frame, text="Voice").grid(row=3, column=0, sticky="w", pady=6)
        ttk.Combobox(frame, textvariable=self.voice, values=("Female", "Male"),
                     state="readonly", width=10).grid(row=3, column=1, sticky="w", pady=6)
        ttk.Label(frame, text="Vowel").grid(row=4, column=0, sticky="w", pady=6)
        ttk.Combobox(frame, textvariable=self.vowel,
                     values=tuple(VOWEL_CHOICES),
                     state="readonly", width=18).grid(row=4, column=1, sticky="w", pady=6)

        self._add_scale(frame, 5, "Vibrato depth (semitones)", self.depth, 0, 2, 0.1)
        self._add_scale(frame, 6, "Vibrato rate (Hz)", self.rate, 2, 9, 0.1)
        self._add_scale(frame, 7, "Vowel duration (seconds)", self.duration, 0.12, 0.6, 0.01)
        self._add_scale(frame, 8, "Human variation", self.humanization, 0, 1, 0.05)

        buttons = ttk.Frame(frame)
        buttons.grid(row=9, column=0, columnspan=3, pady=(12, 8))
        ttk.Button(buttons, text="Sing", command=self.sing).pack(side="left", padx=5)
        ttk.Button(buttons, text="Save WAV...", command=self.save).pack(side="left", padx=5)
        ttk.Label(frame, textvariable=self.status, wraplength=390).grid(
            row=10, column=0, columnspan=3, sticky="w", pady=(8, 0)
        )
        ttk.Label(
            frame,
            text="Synthetic voice with approximate English pronunciation. Vowel choices distinguish sounds like a in cat and ah in father.",
            wraplength=390,
        ).grid(row=11, column=0, columnspan=3, sticky="w", pady=(10, 0))

    @staticmethod
    def _add_scale(parent, row, label, variable, start, end, resolution):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=6)
        scale = tk.Scale(
            parent, variable=variable, from_=start, to=end, resolution=resolution,
            orient="horizontal", showvalue=True, length=230
        )
        scale.grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)

    def _make_audio(self):
        vowel_override = VOWEL_CHOICES[self.vowel.get()]
        return synthesize(
            self.text.get(), NOTE_TO_MIDI[self.note.get()], self.voice.get(),
            vowel_override, self.depth.get(), self.rate.get(), self.duration.get(),
            self.phonemes.get(), self.humanization.get()
        )

    def sing(self):
        try:
            samples = self._make_audio()
        except (ValueError, KeyError) as error:
            messagebox.showerror("Cannot sing", str(error))
            return
        self.status.set("Preparing playback...")
        threading.Thread(target=self._play_audio, args=(samples,), daemon=True).start()

    def _play_audio(self, samples):
        path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temporary:
                path = temporary.name
            write_wav(path, samples)
            command = playback_command(path)
            if command is None:
                self.root.after(
                    0, lambda: self.status.set(
                        "No supported audio player found. Use Save WAV... to export the sound."
                    )
                )
                return
            if command == "winsound":
                import winsound
                winsound.PlaySound(path, winsound.SND_FILENAME)
            else:
                subprocess.run(command, check=True)
            self.root.after(0, lambda: self.status.set("Playback finished."))
        except (OSError, subprocess.CalledProcessError) as error:
            message = str(error)
            self.root.after(0, lambda: self.status.set(f"Playback failed: {message}"))
        finally:
            if path and os.path.exists(path):
                os.unlink(path)

    def save(self):
        path = filedialog.asksaveasfilename(
            title="Save synthesized voice",
            defaultextension=".wav",
            filetypes=(("WAV audio", "*.wav"),),
        )
        if not path:
            return
        try:
            write_wav(path, self._make_audio())
        except (OSError, ValueError, KeyError) as error:
            messagebox.showerror("Could not save audio", str(error))
            return
        self.status.set(f"Saved WAV: {path}")


def main():
    root = tk.Tk()
    VocalSynthApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

