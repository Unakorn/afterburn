# AFTERBURN

**Drop a song. Get a music-reactive MP4.**

## What it does

A rotating **prismatic core** with orbiting light rings. A **hyperspace tunnel** full of passing stardust. An intricate **kaleidoscope**, drifting **nebula clouds**, electric **vortex filaments**, and an endless **neon landscape**.

AFTERBURN analyzes bass, mids, treble, rhythm, and changes in the song. Sound drives the shapes, motion, brightness, and beat pulses. Scenes crossfade near detected hits and musical changes, with glow, light trails, color splitting, and bursts of glitch. A song-title overlay fades out during the opening six seconds.

Everything is generated locally. The same song file and settings produce the same visual variation; use `--seed` to try another.

## Start here

1. Extract the entire AFTERBURN folder from the ZIP before using it.
2. Drag one or more songs onto the launcher for your video shape.
3. Leave the window open while it renders. Your videos appear in **Rendered Videos**, beside the original song.

You can also double-click a launcher to choose songs in a file picker.

| Launcher | Video |
| --- | --- |
| **01 DROP SONG - Vertical.bat** | 1080 × 1920 · 9:16 · Shorts / TikTok / Reels |
| **02 DROP SONG - Widescreen.bat** | 1920 × 1080 · 16:9 · YouTube / TVs |
| **03 DROP SONG - Square.bat** | 1080 × 1080 · 1:1 · Square posts |
| **04 DROP SONG - Vertical 4K.bat** | 2160 × 3840 · 9:16 · Ultra quality |
| **05 DROP SONG - Widescreen 4K.bat** | 3840 × 2160 · 16:9 · Ultra quality |
| **06 DROP SONG - All Formats.bat** | Vertical, widescreen, and square at standard sizes |

All launchers render at **60 frames per second**. The 4K launchers render more pixels and use **ultra** encoding, which retains more detail and takes longer. Multiple dropped songs render one after another. Existing videos are kept; repeat renders get a numbered filename.

## What you need

- Windows 10 or 11, **Python 3.11 or newer**, and a graphics driver supporting **OpenGL 3.3 or newer**. If Python is missing, install it from [python.org](https://www.python.org/downloads/windows/) with the Python launcher enabled.
- Internet for the first launch, which installs the rendering libraries into a private `.venv` folder. Future renders run locally. Songs are not uploaded.
- Enough free disk space for the output video. High resolution and long tracks create larger files.

FFmpeg is included through the automatic setup; a separate FFmpeg installation is unnecessary. Common inputs include MP3, WAV, FLAC, M4A, OGG, and AAC; decoding depends on FFmpeg's support for the source file.

## More control

Open a terminal in this folder and run any of these examples:

```powershell
# Render a short preview before committing to the full song.
py -3 launch.py --aspect vertical --preview-seconds 12 "C:\Music\My Song.mp3"

# Make a 4K YouTube video.
py -3 launch.py --aspect wide --width 3840 --height 2160 --quality ultra "C:\Music\My Song.wav"

# Soften the effects and remove the song title.
py -3 launch.py --aspect square --calm --no-title "C:\Music\My Song.flac"

# Choose an output folder and a lower frame rate.
py -3 launch.py --aspect wide --fps 30 --output-dir "D:\Finished Videos" "C:\Music\My Song.mp3"

# Try another visual variation with more frequent scene changes.
py -3 launch.py --seed 42 --scene-seconds 8 --title "MIDNIGHT SIGNAL" "C:\Music\My Song.mp3"
```

| Option | Meaning |
| --- | --- |
| `--aspect vertical`, `wide`, or `square` | Video shape; default is vertical |
| `--all-formats` | Make vertical, widescreen, and square videos for each song |
| `--width N --height N` | Override both dimensions; even numbers from 64 to 8192; unavailable with `--all-formats` |
| `--fps N` | Frames per second from 1 to 120; default is 60 |
| `--quality high` or `ultra` | Video compression quality; ultra retains more detail, encodes more slowly, and generally makes larger files; default is high |
| `--preview-seconds N` | Render only the first N seconds |
| `--output-dir "folder"` | Save all videos in this folder |
| `--seed N` | Choose a repeatable visual variation using a nonnegative whole number |
| `--scene-seconds N` | Approximate seconds between scene changes; minimum 4, default 12 |
| `--title "Your title"` | Override the opening title and video title metadata |
| `--no-title` | Hide the song title |
| `--calm` | Soften beat pulses, shake, color splitting, glitches, and trails |

## If something goes wrong

- **Python is missing:** Install Python 3.11 or newer, then reopen the launcher.
- **First setup fails:** Check the internet connection and run the launcher again. Keep the folder outside the ZIP and in a location you can write to.
- **A graphics/OpenGL error appears:** Update your graphics driver. OpenGL support can be limited in remote desktop sessions or virtual machines. Try rendering directly on the computer.
- **4K fails or runs too slowly:** Try the standard-size launcher. Render speed depends on the graphics hardware and scene complexity.
- **You moved the app to another computer:** Copy the app files without `.venv`; the new computer creates its own environment on first launch.

Press **Ctrl+C** in the render window to stop. Finished videos stay saved; an unfinished render is removed. Error details appear in the window and are also saved in the app's **logs** folder when possible.

## Source repository

Clone or download the complete source tree, including `shaders`. Dependencies are installed on your computer; no runtime, vendor libraries, songs, or rendered videos are included. See [BUILD.md](BUILD.md) for manual setup.

## License

No project license was included in the source snapshot. This repository does not assign a new license. Any third-party components retain their own terms.
