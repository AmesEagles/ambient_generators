# Stillwater — Ambient Music Generator

Stillwater is a dependency-free Python ambient synthesizer. Choose a mood, key,
tempo, and time signature to generate an endless sequence of evolving
four-bar sections. Each generated song follows a repeating verse, chorus,
verse, chorus, bridge, and final chorus form, with a defined lead melody and a
beat that changes with each section. New sections are crossfaded into a single
live audio stream to avoid the pauses caused by restarting the audio player.
Export saves the continuous session generated so far, or composes a complete
song when playback has not started yet.

## Run

```bash
python3 ambient_generator.py
```

Tkinter is included with most Python installations. Seamless playback uses
`aplay`, `paplay`, or `ffplay` and requires one of them to be on `PATH`. On
Linux, install `alsa-utils` (for `aplay`) or PulseAudio's `paplay` if neither
player is already present. WAV export does not require an audio player.

## Controls

- **Mood** selects the tonal character and its matching harmony and synth sound.
- **Surprise me** picks a random mood and starts generating.
- **Choose a new random mood every section** changes the style as each new
  four-bar phrase begins.
- **Key**, **tempo**, and **time signature** set the musical foundation.
- **Use vocal synthesizer** adds the supplied singing-voice instrument. Choose
  melody or chord harmony and enter custom lyrics; leaving lyrics blank creates
  short, mood-themed lyrics for the song. Vocals perform the verse sections
  and return for the final chorus, with instrumental sections between. Each
  sung phrase contains at least three words. **Vocals only** removes all
  instruments and percussion and keeps the voice singing through every section.
- **Instrumentals** opens a list of synth patches and percussion options.
  Selecting patches replaces the mood's default synth timbres without changing
  its chords or progression.
- **Export session WAV** saves all audio streamed during the current playback
  session. Before playback, it composes a complete verse/chorus/bridge cycle.

## Music and sound design

The built-in mood database contains twelve styles with suggested tempo ranges,
major/minor/modal scales, curated progressions, mood-specific chord colors
(triads, sevenths, ninths, sixths, and suspended voicings), and distinct
instrument and rhythm choices. Chord changes follow each arrangement's harmonic
rhythm: some sections hold two chords across the phrase, while others move
through three, four, five, six, or eight changes, including syncopated
half-bar changes. Its instrument library includes
warm analog, soft strings, choir, dark drone, crystal, bass, bell, flute,
chime, tape keys, mallets, tines, plucks, pizzicato, and water-drop tones.
Sine, triangle, saw, square, and glass-like wavetables combine with slow
envelopes, stereo spread, detuning, quiet bass, airy layers, subtle pulses,
and feedback echoes.

Chord colors are voiced diatonically from the selected mood's scale instead of
forcing unrelated fixed major/minor intervals onto each chord. Lead notes favor
the active chord tones, and held notes cross a chord change only when their
pitch is shared by the next chord.

Rhythmic accompaniment is arranged independently of the held chord pads.
Every generated section includes a defined, scale- and chord-aware lead motif.
The verse presents it, the chorus adds answering offbeat notes and a stronger
beat, and the bridge thins the phrase and rhythm before the final chorus
returns. Lead motifs use varied note lengths, and held tones resolve at chord
changes unless the pitch belongs to the next chord.

Every style has a clear synthesized kick and backbeat, with hi-hats, soft snares,
and occasional fills varied by mood and song section. Offbeat instruments add
chord-tone responses around the main melody; their sound and activity vary
across moods. Chord duration, melody, percussion density, and instrument
intensity change between verse, chorus, and bridge. Everything is synthesized
locally without sample packs or third-party Python audio libraries.

The vocal instrument uses the attached source's procedural phoneme, vowel-formant,
and glottal synthesis engine. Its separate demonstration GUI is not used. Rendered
word-and-note combinations are cached so repeated lyric phrases do not repeat
the expensive voice synthesis work. Enable Vocal prominence to raise the voice
and duck accompaniment while each word is sung. Instrument selections preserve
the chosen mood's harmony; Vocals only takes priority over instrumental settings.
