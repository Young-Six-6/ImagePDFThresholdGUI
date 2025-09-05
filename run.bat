@echo off
setlocal enabledelayedexpansion

REM Configuration
set "CONFIG_FILE=.config"
set "MAIN_SCRIPT=main.py"
set "REQUIREMENTS=requirements.txt"

REM Check if config file exists
if exist "%CONFIG_FILE%" (
    echo Config file detected, starting program...
    goto run_program
)

REM Check requirements.txt existence
if not exist "%REQUIREMENTS%" (
    echo Error: %REQUIREMENTS% not found
    pause
    exit /b 1
)

REM Install dependencies
echo No config file found, installing dependencies...
pip install -r "%REQUIREMENTS%"

if %errorlevel% neq 0 (
    echo Failed to install dependencies. Check pip and network.
    pause
    exit /b 1
)

REM Create config file
echo Creating config file...
type nul > "%CONFIG_FILE%"

if not exist "%CONFIG_FILE%" (
    echo Failed to create config file. Check folder permissions.
    pause
    exit /b 1
)

:run_program
REM Check main.py existence
if not exist "%MAIN_SCRIPT%" (
    echo Error: %MAIN_SCRIPT% not found
    pause
    exit /b 1
)

REM Run program with explicit python command
echo Starting program...
python "%MAIN_SCRIPT%"

if %errorlevel% equ 0 (
    echo Program exited successfully
) else (
    echo Program error, code: %errorlevel%
    if %errorlevel% equ 9009 (
        echo Python not found in PATH. Please check Python installation.
    )
    pause
)

endlocal