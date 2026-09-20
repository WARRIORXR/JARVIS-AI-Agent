@echo off
echo ============================================
echo  J.A.R.V.I.S. — Dependency Installer
echo ============================================
echo.

:: Check Python
python --version 2>NUL
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

echo [1/4] Creating virtual environment...
python -m venv venv
call venv\Scripts\activate.bat

echo [2/4] Upgrading pip...
python -m pip install --upgrade pip --quiet

echo [3/4] Installing core dependencies...
pip install -r requirements.txt

echo [4/4] Installing PyAudio (Windows)...
pip install pyaudio --quiet 2>NUL || (
    echo [INFO] PyAudio install failed - trying pipwin...
    pip install pipwin --quiet
    pipwin install pyaudio --quiet 2>NUL || echo [WARN] PyAudio failed - microphone may not work
)

echo.
echo ============================================
echo  Installation complete!
echo.
echo  To start JARVIS:
echo    venv\Scripts\activate
echo    python main.py --text     (text mode, no mic)
echo    python main.py            (voice mode)
echo    python main.py --debug    (verbose output)
echo ============================================
pause
