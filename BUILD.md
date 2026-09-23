# Source setup

Use Python 3.11 or newer and a graphics driver with OpenGL 3.3 support. The app generates visuals locally; it does not upload songs.

The Windows drop-file launchers call `launch.py`, which creates a local `.venv` and installs `requirements.txt` on first use. That initial setup requires network access. Do not commit the generated environment, setup lock, logs, or output videos.

For manual setup without the automatic bootstrap:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python afterburn.py --help
python afterburn.py --aspect wide --preview-seconds 12 "C:\Music\example.wav"
```

Keep the `shaders` folder beside the Python modules. FFmpeg is supplied by the installed `imageio-ffmpeg` dependency. Third-party packages and their licenses are obtained through installation and are not vendored here.

No compilation step or frozen executable is needed. Source syntax and CLI parsing can be checked without rendering; an actual render additionally needs working OpenGL and the installed dependencies.
