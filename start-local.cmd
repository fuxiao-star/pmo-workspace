@echo off
setlocal
cd /d "%~dp0"
if defined PMO_PYTHON goto custom
if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" goto codex
where py >nul 2>nul
if errorlevel 1 goto try_python
py -3 -c "import sqlite3,sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if errorlevel 1 goto try_python
py -3 server.py
goto done
:try_python
python -c "import sqlite3,sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if errorlevel 1 goto missing
python server.py
goto done
:codex
"%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" server.py
goto done
:custom
"%PMO_PYTHON%" server.py
goto done
:missing
echo Python 3.10+ is required. Ask Codex to locate its bundled Python runtime.
:done
pause
endlocal
