@echo off
setlocal
cd /d "%~dp0"
if defined PMO_PYTHON goto custom
if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" goto codex
where py >nul 2>nul
if errorlevel 1 goto try_python
py -3 -c "import sqlite3,sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if errorlevel 1 goto try_python
py -3 start.py
goto done
:try_python
where python >nul 2>nul
if errorlevel 1 goto miniconda
python -c "import sqlite3,sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if errorlevel 1 goto miniconda
python start.py
goto done
:miniconda
if not exist "%USERPROFILE%\miniconda3\python.exe" goto missing
"%USERPROFILE%\miniconda3\python.exe" start.py
goto done
:codex
"%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" start.py
goto done
:custom
"%PMO_PYTHON%" start.py
goto done
:missing
echo Python 3.10+ with sqlite3 is required.
echo Ask Codex to locate its bundled Python runtime, or install Python.
echo You may set PMO_PYTHON to the full path of python.exe.
:done
pause
endlocal
