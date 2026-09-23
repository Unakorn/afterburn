@echo off
setlocal DisableDelayedExpansion
title AFTERBURN - Widescreen 4K.bat
py -3 -c "import sys; sys.exit(sys.version_info.__lt__((3, 11)))" >nul 2>&1
if not errorlevel 1 goto use_py
python -c "import sys; sys.exit(sys.version_info.__lt__((3, 11)))" >nul 2>&1
if not errorlevel 1 goto use_python
echo AFTERBURN needs Python 3.11 or newer.
echo Install Python from https://www.python.org/downloads/windows/
echo Enable the Python launcher during installation, then try again.
echo.
pause
exit /b 1

:use_py
py -3 "%~dp0launch.py" --aspect wide --width 3840 --height 2160 --quality ultra %*
set "afterburn_exit=%errorlevel%"
goto finish

:use_python
python "%~dp0launch.py" --aspect wide --width 3840 --height 2160 --quality ultra %*
set "afterburn_exit=%errorlevel%"

:finish
echo.
if not "%afterburn_exit%"=="0" echo AFTERBURN stopped with an error. The details are above.
pause
exit /b %afterburn_exit%
