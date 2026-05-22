@echo off
REM =============================================================================
REM run.bat - Start the Python Web Service
REM =============================================================================
REM
REM WHAT IS THIS FILE?
REM   A batch file is a script that runs Windows commands automatically.
REM   Double-click this file to start the web service.
REM
REM WHAT DOES IT DO?
REM   1. Activates the virtual environment
REM   2. Starts the uvicorn server
REM   3. Keeps the window open if there's an error
REM
REM COMMANDS EXPLAINED:
REM   @echo off     - Don't print each command as it runs
REM   echo          - Print text to the screen
REM   call          - Run another batch file and come back
REM   pause         - Wait for user to press a key
REM   REM           - This is a comment (ignored by Windows)
REM
REM =============================================================================

REM -----------------------------------------------------------------------------
REM DISPLAY HEADER
REM -----------------------------------------------------------------------------
REM 'echo.' prints a blank line
REM The equals signs create a visual separator

echo.
echo ============================================================
echo   PYTHON WEB SERVICE
echo ============================================================
echo.

REM -----------------------------------------------------------------------------
REM ACTIVATE VIRTUAL ENVIRONMENT
REM -----------------------------------------------------------------------------
REM We need to use 'call' because activate.bat is another batch file.
REM Without 'call', this script would stop after activate.bat runs.
REM
REM After this runs, the (venv) prefix appears in the prompt.

echo [Step 1] Activating virtual environment...
echo.

REM Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo.
    echo Please create it first by running:
    echo   python -m venv venv
    echo   venv\Scripts\activate
    echo   pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

REM -----------------------------------------------------------------------------
REM DISPLAY SERVICE INFORMATION
REM -----------------------------------------------------------------------------

echo [Step 2] Starting the web server...
echo.
echo ============================================================
echo   SERVICE URLS:
echo ============================================================
echo.
echo   Main page:           http://localhost:8000/
echo   Health check:        http://localhost:8000/health
echo   API Documentation:   http://localhost:8000/docs
echo   Process endpoint:    POST http://localhost:8000/api/process
echo.
echo ============================================================
echo.
echo   Press Ctrl+C to stop the server
echo.
echo ============================================================
echo.

REM -----------------------------------------------------------------------------
REM START THE SERVER
REM -----------------------------------------------------------------------------
REM python -m uvicorn  = Run uvicorn as a Python module
REM main:app           = In main.py, use the object named 'app'
REM --reload           = Auto-restart when code changes (for development)
REM --host 0.0.0.0     = Accept connections from any IP address
REM                      (Use 127.0.0.1 to only allow local connections)
REM --port 8000        = Listen on port 8000

python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

REM -----------------------------------------------------------------------------
REM AFTER SERVER STOPS
REM -----------------------------------------------------------------------------
REM If the server stops (Ctrl+C or error), we reach this point.
REM 'pause' keeps the window open so you can read any error messages.

echo.
echo ============================================================
echo   Server stopped.
echo ============================================================
echo.
pause
