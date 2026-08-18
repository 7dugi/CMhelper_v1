@echo off
setlocal
set ROOT_DIR=%~dp0..\..
set VENV_PYTHON=%ROOT_DIR%\.venv\Scripts\python.exe
if not exist "%VENV_PYTHON%" (
    echo [ERROR] Virtual environment not found at .venv
    exit /b 1
)
set PYTHONPATH=%ROOT_DIR%
"%VENV_PYTHON%" -m automation.control %*
