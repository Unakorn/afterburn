"""Audio analysis for AFTERBURN. Requires NumPy and an FFmpeg executable.

Features are evaluated at video-frame timestamps and are always finite float32
values in [0, 1]. The full song sets normalization, so quiet passages stay quiet.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import subprocess
import tempfile

import numpy as np


SAMPLE_RATE = 22050
FFT_SIZE = 2048
HOP_SIZE = 512
FEATURE_NAMES = (
    "bass", "mid", "treble", "energy", "beat", "slow_energy",
    "section_novelty", "reserved",
)


@dataclass
class AudioAnalysis:
    duration: float
    frame_count: int
    features: np.ndarray
    spectrum: np.ndarray
    tempo: float = 0.0
    sample_rate: int = SAMPLE_RATE


def _moving_mean(values: np.ndarray, width: int) -> np.ndarray:
    """Centered box average with edge extension; supports vectors/matrices."""
    width = max(1, min(int(width), len(values)))
    if width <= 1:
        return np.array(values, dtype=np.float64, copy=True)
    left = width // 2
    right = width - left - 1
    padding = [(left, right)] + [(0, 0)] * (values.ndim - 1)
    padded = np.pad(values, padding, mode="edge")
    sums = np.cumsum(padded, axis=0, dtype=np.float64)
    sums = np.concatenate((np.zeros_like(sums[:1]), sums), axis=0)
    return (sums[width:] - sums[:-width]) / width


def _normalize(values: np.ndarray, minimum_reference: float,
               exponent: float = 0.7) -> np.ndarray:
    """Use song-level references and a real amplitude floor, never per-frame gain."""
    reference = np.maximum(np.percentile(values, 95, axis=0), minimum_reference)
    floor = np.maximum(reference * 0.012, minimum_reference * 0.02)
    scaled = np.clip((values - floor) / np.maximum(reference - floor, 1e-12), 0, 1)
    return np.power(scaled, exponent)


def _beat_envelope(spectrum: np.ndarray, bass: np.ndarray,
                   energy: np.ndarray, times: np.ndarray) -> tuple[np.ndarray, float]:
    """Adaptive spectral-flux attacks with a short refractory period and decay."""
    if len(times) < 3 or float(np.max(energy)) < 0.03:
        return np.zeros(len(times)), 0.0
    delta = HOP_SIZE / SAMPLE_RATE
    log_spectrum = np.log1p(spectrum * 12.0)
    flux = np.maximum(np.diff(log_spectrum, axis=0, prepend=log_spectrum[:1]), 0).mean(axis=1)
    bass_rise = np.maximum(np.diff(bass, prepend=bass[0]), 0)
    onset = 0.75 * _normalize(flux, 0.025, 1.0) + 0.25 * _normalize(bass_rise, 0.035, 1.0)
    onset *= np.clip(energy * 3.0, 0, 1)
    local_mean = _moving_mean(onset, round(0.75 / delta))
    local_square = _moving_mean(onset * onset, round(0.75 / delta))
    local_std = np.sqrt(np.maximum(local_square - local_mean * local_mean, 0))
    threshold = np.maximum(0.07, local_mean + 0.40 * local_std)
    candidates = np.flatnonzero(
        (onset >= np.roll(onset, 1)) & (onset > np.roll(onset, -1))
        & (onset > threshold)
    )
    candidates = candidates[(candidates > 0) & (candidates < len(times) - 1)]
    peaks: list[int] = []
    cooldown = max(1, round(0.18 / delta))
    for candidate in candidates:
        if not peaks or candidate - peaks[-1] >= cooldown:
            peaks.append(int(candidate))
        elif onset[candidate] > onset[peaks[-1]]:
            peaks[-1] = int(candidate)
    impulses = np.zeros(len(times), dtype=np.float64)
    if peaks:
        strength = onset[peaks]
        impulses[peaks] = np.clip(0.60 + 0.40 * strength, 0, 1)
    pulse = np.zeros(len(times), dtype=np.float64)
    decay = math.exp(-delta / 0.16)
    for index in range(len(times)):
        pulse[index] = max(impulses[index], pulse[index - 1] * decay if index else 0)
    pulse *= np.clip(energy * 4.0, 0, 1)

    # A tempo estimate informs scene timing; the actual visual attacks above stay
    # tied to detected sound, rather than to an invented fixed metronome.
    tempo = 0.0
    if len(peaks) >= 4 and times[-1] >= 4.0:
        centered = onset - onset.mean()
        low_lag = max(1, math.floor(60 / (190 * delta)))
        high_lag = min(len(centered) // 2, math.ceil(60 / (65 * delta)))
        lags = np.arange(low_lag, high_lag + 1)
        denominator = float(np.dot(centered, centered)) + 1e-12
        correlation = np.array([
            np.dot(centered[:-lag], centered[lag:]) / denominator for lag in lags
        ])
        if len(correlation) and float(correlation.max()) > 0.08:
            best = int(lags[int(np.argmax(correlation))])
            tempo = float(60.0 / (best * delta))
    return pulse, tempo


def _analyze_samples(samples: np.ndarray, fps: int,
                     sample_rate: int = SAMPLE_RATE) -> AudioAnalysis:
    """Analyze decoded mono PCM; exposed internally for deterministic tests."""
    if sample_rate != SAMPLE_RATE:
        raise ValueError(f"Expected audio decoded at {SAMPLE_RATE} Hz.")
    if not isinstance(fps, (int, np.integer)) or fps <= 0:
        raise ValueError("fps must be a positive integer.")
    if samples.ndim != 1 or len(samples) == 0:
        raise ValueError("The audio file contains no decodable audio samples.")
    duration = len(samples) / sample_rate
    frame_count = math.ceil(duration * fps)
    analysis_count = math.ceil(len(samples) / HOP_SIZE) + 1
    analysis_times = np.arange(analysis_count, dtype=np.float64) * HOP_SIZE / sample_rate
    band_rms = np.zeros((analysis_count, 3), dtype=np.float64)
    bins = np.zeros((analysis_count, 32), dtype=np.float64)
    rms = np.zeros(analysis_count, dtype=np.float64)
    frequencies = np.fft.rfftfreq(FFT_SIZE, 1.0 / sample_rate)
    edges = np.geomspace(35.0, 10500.0, 33)
    spectrum_masks = [(frequencies >= edges[i]) & (frequencies < edges[i + 1]) for i in range(32)]
    # The lowest log-spaced bins can be narrower than a Fourier bin. Give each
    # one the closest real frequency instead of leaving dead spectrum bars.
    for index, mask in enumerate(spectrum_masks):
        if not mask.any():
            mask[np.argmin(np.abs(frequencies - math.sqrt(edges[index] * edges[index + 1])))] = True
    wide_masks = [
        (frequencies >= 25) & (frequencies < 220),
        (frequencies >= 220) & (frequencies < 2200),
        (frequencies >= 2200) & (frequencies < 10500),
    ]
    window = np.hanning(FFT_SIZE).astype(np.float32)
    power_scale = 2.0 / (FFT_SIZE * float(np.dot(window, window)))
    offsets = np.arange(FFT_SIZE) - FFT_SIZE // 2
    # ~8 MB of working FFT/sample data per chunk. A ten-minute song is never
    # expanded into a giant time-by-frequency array.
    for first in range(0, analysis_count, 256):
        last = min(first + 256, analysis_count)
        indices = np.arange(first, last)[:, None] * HOP_SIZE + offsets[None, :]
        valid = (indices >= 0) & (indices < len(samples))
        frames = np.asarray(samples[np.clip(indices, 0, len(samples) - 1)], dtype=np.float32)
        np.nan_to_num(frames, copy=False, nan=0.0, posinf=0.0, neginf=0.0)
        # Corrupt floating-point input must not overflow RMS or FFT arithmetic.
        np.clip(frames, -16.0, 16.0, out=frames)
        frames *= valid
        rms[first:last] = np.sqrt(np.mean(frames * frames, axis=1, dtype=np.float64))
        transform = np.fft.rfft(frames * window, axis=1)
        power = (transform.real * transform.real + transform.imag * transform.imag) * power_scale
        for index, mask in enumerate(wide_masks):
            band_rms[first:last, index] = np.sqrt(np.maximum(power[:, mask].sum(axis=1), 0))
        for index, mask in enumerate(spectrum_masks):
            bins[first:last, index] = np.sqrt(np.maximum(power[:, mask].sum(axis=1), 0))

    energy = _normalize(rms, 0.006)
    wide = _normalize(band_rms, 0.004)
    normalized_spectrum = _normalize(bins, 0.0015, 0.65)
    # This extra physical-amplitude gate prevents near-silence or a codec noise
    # floor becoming a full-height frequency display after normalization.
    audible = np.clip((rms - 0.00003) / 0.002, 0, 1)
    wide *= audible[:, None]
    normalized_spectrum *= audible[:, None]
    energy *= audible
    beat, tempo = _beat_envelope(normalized_spectrum, wide[:, 0], energy, analysis_times)
    slow_energy = _moving_mean(energy, round(0.8 * sample_rate / HOP_SIZE))
    # Compare a smoothed timbre to the preceding phrase for scene-transition cues.
    smooth_spectrum = _moving_mean(normalized_spectrum, round(1.1 * sample_rate / HOP_SIZE))
    phrase_delay = max(1, round(1.8 * sample_rate / HOP_SIZE))
    previous = smooth_spectrum[np.maximum(np.arange(analysis_count) - phrase_delay, 0)]
    difference = np.abs(smooth_spectrum - previous).mean(axis=1)
    novelty = _normalize(difference, 0.045, 1.0) * np.clip(energy * 3.0, 0, 1)
    # No transition at the artificial beginning of an audio file.
    novelty *= np.clip((analysis_times - 0.5) / 1.5, 0, 1)
    source_features = np.column_stack((wide, energy, beat, slow_energy, novelty,
                                       np.zeros(analysis_count)))
    video_times = np.arange(frame_count, dtype=np.float64) / fps
    features = np.column_stack([
        np.interp(video_times, analysis_times, source_features[:, index]) for index in range(8)
    ]).astype(np.float32)
    spectrum = np.column_stack([
        np.interp(video_times, analysis_times, normalized_spectrum[:, index]) for index in range(32)
    ]).astype(np.float32)
    np.clip(features, 0, 1, out=features)
    np.clip(spectrum, 0, 1, out=spectrum)
    return AudioAnalysis(duration, frame_count, features, spectrum, tempo, sample_rate)


def analyze_audio(audio_path: Path, ffmpeg_exe: str, fps: int,
                  work_dir: Path, max_seconds: float | None = None) -> AudioAnalysis:
    """Decode and analyze the first audio stream of any FFmpeg-supported file.

    Args:
        audio_path: Input song path (spaces and Unicode are supported).
        ffmpeg_exe: Path to the FFmpeg executable.
        fps: Positive integer video frame rate.
        work_dir: Writable directory for temporary decoded PCM; cleaned on exit.
        max_seconds: Optional positive limit for previews, starting at time zero.

    Returns:
        AudioAnalysis with duration measured from decoded samples; frame_count is
        ceil(duration * fps). features is (frame_count, 8) in FEATURE_NAMES order,
        spectrum is (frame_count, 32), from low to high log-spaced frequencies.
        Both arrays contain finite float32 values in [0, 1]. Silence produces all
        zeros. tempo is an approximate BPM, or 0 when no reliable beat is found.

    Raises:
        ValueError for invalid parameters or empty audio; RuntimeError when
        FFmpeg cannot decode the file. No shell is used to invoke FFmpeg.
    """
    audio_path, work_dir = Path(audio_path), Path(work_dir)
    if not audio_path.is_file():
        raise FileNotFoundError(f"Song not found: {audio_path}")
    if not isinstance(fps, (int, np.integer)) or fps <= 0:
        raise ValueError("fps must be a positive integer.")
    if max_seconds is not None and (not math.isfinite(max_seconds) or max_seconds <= 0):
        raise ValueError("max_seconds must be a finite positive number.")
    work_dir.mkdir(parents=True, exist_ok=True)
    print(f"Analyzing sound: {audio_path.name}", flush=True)
    with tempfile.TemporaryDirectory(prefix="audio-", dir=str(work_dir)) as temporary:
        pcm_path = Path(temporary) / "mono.f32"
        command = [str(ffmpeg_exe), "-hide_banner", "-loglevel", "error", "-nostdin",
                   "-y", "-i", str(audio_path), "-map", "0:a:0", "-vn", "-ac", "1",
                   "-ar", str(SAMPLE_RATE)]
        if max_seconds is not None:
            command.extend(["-t", str(max_seconds)])
        command.extend(["-f", "f32le", "-acodec", "pcm_f32le", str(pcm_path)])
        with tempfile.TemporaryFile(mode="w+b") as error_log:
            try:
                process = subprocess.run(command, stdin=subprocess.DEVNULL,
                                         stdout=subprocess.DEVNULL, stderr=error_log,
                                         check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except OSError as error:
                raise RuntimeError(f"Could not start FFmpeg: {error}") from error
            if process.returncode != 0:
                error_log.seek(0, 2)
                error_log.seek(max(0, error_log.tell() - 5000))
                details = error_log.read().decode("utf-8", errors="replace").strip()
                raise RuntimeError(f"FFmpeg could not decode {audio_path.name}:\n{details}")
        if not pcm_path.exists() or pcm_path.stat().st_size < 4:
            raise ValueError(f"No audio samples could be decoded from {audio_path.name}.")
        samples = np.memmap(pcm_path, dtype="<f4", mode="r")
        try:
            analysis = _analyze_samples(samples, fps)
        finally:
            # Release the file handle before TemporaryDirectory removes it on Windows.
            samples._mmap.close()
    tempo_text = f", about {analysis.tempo:.0f} BPM" if analysis.tempo else ""
    print(f"Sound ready: {analysis.duration:.2f} seconds, {analysis.frame_count:,} frames{tempo_text}", flush=True)
    return analysis
