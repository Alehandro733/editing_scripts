@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM — Administrator rights check
net session >nul 2>&1
if %errorlevel% NEQ 0 (
    echo Error: you need to run the script as Administrator.
    pause
    exit /b 1
)

REM — Paths
set "EXT_DIR=C:\Program Files (x86)\Common Files\Adobe\CEP\extensions"
set "LINK_NAME=MyPanelScript"
set "TARGET=%EXT_DIR%\%LINK_NAME%"
set "SOURCE=%~dp0MyPanelScript"
set "REGFILE=%~dp0csxs.reg"

REM — Remove old folder or symlink if it exists
if exist "%TARGET%" (
    echo Removing existing "%TARGET%"...
    dir /AL "%TARGET%" >nul 2>&1
    if %errorlevel% EQU 0 (
        echo  Symlink found, rmdir "%TARGET%"
        rmdir "%TARGET%"
    ) else (
        echo  Regular folder found, rmdir /S /Q "%TARGET%"
        rmdir /S /Q "%TARGET%"
    )
)

REM — Create symlink
echo Creating symlink "%TARGET%" -> "%SOURCE%"...
mklink /D "%TARGET%" "%SOURCE%"
if %errorlevel% NEQ 0 (
    echo Error: failed to create symlink.
    pause
    exit /b 1
)

REM — Registry import
echo Importing registry from "%REGFILE%"...
reg import "%REGFILE%"
if %errorlevel% NEQ 0 (
    echo Error: failed to import registry.
    pause
    exit /b 1
)

echo Done!
pause
