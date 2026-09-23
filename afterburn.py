"""AFTERBURN — drop a track, get a finished, audio-reactive MP4."""
from __future__ import annotations

import argparse
import hashlib
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback

FORMATS = {'vertical': (1080,1920), 'wide': (1920,1080), 'square': (1080,1080)}


def positive_float(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError('Must be a positive finite number.')
    return number


def get_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='*', type=Path, help='One or more songs. Omit to open a file picker.')
    parser.add_argument('--aspect', choices=FORMATS, default='vertical')
    parser.add_argument('--all-formats', action='store_true', help='Render vertical, widescreen, and square for each song.')
    parser.add_argument('--width', type=int)
    parser.add_argument('--height', type=int)
    parser.add_argument('--fps', type=int, default=60)
    parser.add_argument('--quality', choices=('high','ultra'), default='high', help='Ultra uses slower encoding and a higher bitrate.')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--preview-seconds', type=positive_float, help='Render only the opening N seconds.')
    parser.add_argument('--seed', type=int, help='Choose a different visual variation; default comes from the song.')
    parser.add_argument('--scene-seconds', type=positive_float, default=12, help='Approximate time between scene changes (minimum 4).')
    parser.add_argument('--no-title', action='store_true')
    parser.add_argument('--title', help='Override the opening song title.')
    parser.add_argument('--calm', action='store_true', help='Reduce shake, color splitting, glitch and trails.')
    args = parser.parse_args(argv)
    if not 1 <= args.fps <= 120:
        parser.error('--fps must be between 1 and 120.')
    if bool(args.width is not None) != bool(args.height is not None):
        parser.error('Set --width and --height together.')
    if args.width is not None and (min(args.width,args.height)<64 or max(args.width,args.height)>8192 or args.width%2 or args.height%2):
        parser.error('Width and height must be even numbers between 64 and 8192.')
    if args.all_formats and args.width is not None:
        parser.error('--all-formats uses its own dimensions; remove --width and --height.')
    if args.scene_seconds < 4:
        parser.error('--scene-seconds must be at least 4.')
    if args.seed is not None and args.seed < 0:
        parser.error('--seed must be zero or a positive integer.')
    return args


def choose_songs():
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost',True)
    try:
        result = filedialog.askopenfilenames(title='AFTERBURN — choose your songs',filetypes=[('Audio files','*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.opus *.aiff *.aif *.wma'),('All files','*.*')])
        return [Path(item) for item in result]
    finally:
        root.destroy()


def song_seed(path: Path):
    digest = hashlib.blake2b(digest_size=8)
    with path.open('rb') as source:
        while chunk := source.read(1024*1024):
            digest.update(chunk)
    return int.from_bytes(digest.digest(),'little') % (2**32)


def available_output(folder: Path, stem: str):
    candidate = folder / (stem+'.mp4')
    suffix = 2
    while candidate.exists():
        candidate = folder / f'{stem} ({suffix}).mp4'
        suffix += 1
    return candidate


def duration_label(seconds):
    if not math.isfinite(seconds):
        return 'estimating'
    seconds = max(0,int(seconds))
    h,remainder=divmod(seconds,3600)
    m,s=divmod(remainder,60)
    return f'{h:d}h {m:02d}m' if h else f'{m:d}m {s:02d}s'


def encode_video(song: Path, analysis, args, aspect: str, seed: int, ffmpeg: str):
    from afterburn_render import Renderer, Director, SCENE_NAMES
    width,height = (args.width,args.height) if args.width else FORMATS[aspect]
    folder = (args.output_dir.resolve() if args.output_dir else song.parent/'Rendered Videos')
    folder.mkdir(parents=True,exist_ok=True)
    # Keep filenames comfortably inside typical Windows path limits.
    stem = song.stem[:95].rstrip(' .') or 'Track'
    output = available_output(folder,f'{stem} - AFTERBURN {aspect} {width}x{height}')
    title = '' if args.no_title else (args.title or song.stem)
    director = Director(analysis.features,args.fps,seed,args.scene_seconds)
    renderer = None
    encoder = None
    started=time.perf_counter()
    print(f'\n  {aspect.upper()}  /  {width} x {height}  /  {args.fps} fps',flush=True)
    print(f'  {analysis.frame_count:,} frames  /  {duration_label(analysis.duration)} of music',flush=True)
    try:
        renderer=Renderer(width,height,args.fps,seed,title,args.calm)
        print(f'  GPU: {renderer.info}',flush=True)
        print('  Worlds: '+ ' > '.join(SCENE_NAMES[s] for _,s in director.events[:6]),flush=True)
        with tempfile.TemporaryDirectory(prefix='.afterburn-',dir=folder) as temp_name:
            temp=Path(temp_name)
            partial=temp/'render.mp4'
            error_path=temp/'encoder.log'
            command=[ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-y',
                '-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height}',
                '-r',str(args.fps),'-i','pipe:0','-i',str(song),
                '-map','0:v:0','-map','1:a:0','-map_metadata','-1',
                '-vf','vflip','-c:v','libx264','-preset','veryslow' if args.quality=='ultra' else 'slow',
                '-crf','15' if args.quality=='ultra' else '17','-pix_fmt','yuv420p',
                '-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709',
                '-c:a','aac','-b:a','320k','-ac','2','-af','apad',
                '-t',f'{analysis.duration:.9f}','-movflags','+faststart',
                '-metadata',f'title={args.title or song.stem}',str(partial)]
            with error_path.open('wb') as error_file:
                encoder=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=error_file,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                last_update=0.
                try:
                    for frame in range(analysis.frame_count):
                        pixels=renderer.render(frame,analysis.features[frame],analysis.spectrum[frame],director.at(frame))
                        encoder.stdin.write(pixels)
                        now=time.perf_counter()
                        if now-last_update>=2. or frame==analysis.frame_count-1:
                            elapsed=now-started
                            speed=(frame+1)/max(elapsed,.001)
                            remaining=(analysis.frame_count-frame-1)/max(speed,.001)
                            print(f'\r  {(frame+1)/analysis.frame_count:6.1%} | {speed:5.1f} frames/s | remaining ~{duration_label(remaining):>9}    ',end='',flush=True)
                            last_update=now
                    encoder.stdin.close()
                    print('\n  Finishing the MP4...',flush=True)
                    returncode=encoder.wait()
                except BaseException:
                    if encoder.poll() is None:
                        encoder.terminate()
                    try:
                        encoder.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        encoder.kill()
                        encoder.wait()
                    if encoder.stdin and not encoder.stdin.closed:
                        try:
                            encoder.stdin.close()
                        except OSError:
                            pass
                    error_file.flush()
                    details=error_path.read_text(encoding='utf-8',errors='replace').strip()
                    if details:
                        print('\n  Encoder details: '+details[-4000:],file=sys.stderr)
                    raise
            if returncode != 0 or not partial.is_file() or partial.stat().st_size < 100:
                raise RuntimeError('Video encoder failed: '+error_path.read_text(encoding='utf-8',errors='replace')[-4000:])
            # os.rename refuses to overwrite an existing destination on Windows.
            # Re-check after a long render in case another launch finished first.
            original_stem=output.stem
            while True:
                output=available_output(folder,original_stem)
                try:
                    partial.rename(output)
                    break
                except FileExistsError:
                    continue
        print(f'  DONE in {duration_label(time.perf_counter()-started)}\n  {output}',flush=True)
        return output
    finally:
        if renderer is not None:
            renderer.close()


def main(argv=None):
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):
            stream.reconfigure(encoding='utf-8',errors='replace')
    args=get_args(argv)
    print('\n  A F T E R B U R N\n  MUSIC IN. WORLDS OUT.\n',flush=True)
    try:
        import imageio_ffmpeg
        from afterburn_audio import analyze_audio
    except ImportError as exc:
        print(f'Missing a required library: {exc}. Open one of the DROP SONG launchers to finish setup.',file=sys.stderr)
        return 1
    if not args.inputs:
        try:
            args.inputs=choose_songs()
        except Exception as exc:
            print(f'Could not open the song picker: {exc}. Drop songs onto a launcher instead.',file=sys.stderr)
            return 1
    if not args.inputs:
        print('No songs selected.')
        return 0
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    failures=0
    completed=[]
    for input_path in args.inputs:
        song=input_path.expanduser().resolve()
        try:
            if not song.is_file():
                raise ValueError(f'Not a file: {song}')
            print(f'\n  TRACK: {song.name}\n  Listening for rhythm and frequency changes...',flush=True)
            with tempfile.TemporaryDirectory(prefix='afterburn-audio-') as temp_name:
                analysis=analyze_audio(song,ffmpeg,args.fps,Path(temp_name),args.preview_seconds)
            seed=args.seed if args.seed is not None else song_seed(song)
            if getattr(analysis,'tempo',0)>0:
                print(f'  Approximate pulse: {analysis.tempo:.0f} BPM  /  visual seed: {seed}',flush=True)
            formats=list(FORMATS) if args.all_formats else [args.aspect]
            for aspect in formats:
                completed.append(encode_video(song,analysis,args,aspect,seed,ffmpeg))
        except KeyboardInterrupt:
            print('\n  Cancelled. Completed videos are saved; the unfinished video was removed.',flush=True)
            return 130
        except Exception as exc:
            failures+=1
            print(f'\n  Could not finish {song.name}: {exc}',file=sys.stderr,flush=True)
            log_dir=Path(__file__).parent/'logs'
            try:
                log_dir.mkdir(exist_ok=True)
                log=log_dir/f'error-{time.time_ns()}.txt'
                log.write_text(traceback.format_exc(),encoding='utf-8')
                print(f'  Details saved to: {log}',flush=True)
            except OSError:
                pass
    print(f'\n  Finished: {len(completed)} video(s).'+(f' {failures} track(s) had errors.' if failures else ''),flush=True)
    return 1 if failures else 0


if __name__=='__main__':
    raise SystemExit(main())
