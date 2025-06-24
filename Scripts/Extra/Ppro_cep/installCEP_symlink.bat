@echo off
setlocal

REM Check if PowerShell is available
where powershell >nul 2>&1
if %errorlevel% EQU 0 (
    set "USE_PS=1"
) else (
    set "USE_PS=0"
)

REM Check for administrator privileges
openfiles >nul 2>&1
if %errorlevel% NEQ 0 (
    if %USE_PS%==1 (
        powershell -Command "Write-Host 'Please run this script as Administrator.' -ForegroundColor Red"
    ) else (
        echo Please run this script as Administrator.
    )
    set /p dummy=Press Enter to exit...
    exit /b
)

REM Set source and target paths
set "SOURCE=%~dp0Scripts\Extra\Ppro_cep\MyPanelScript"
set "TARGET=C:\Program Files (x86)\Common Files\Adobe\CEP\extensions\MyPanelScript"
set "REGPATH=%~dp0Scripts\Extra\Ppro_cep"

REM Remove existing target if it exists
if exist "%TARGET%" (
    echo Checking existing target: "%TARGET%"
    dir /AL "%TARGET%" >nul 2>&1
    if %errorlevel% EQU 0 (
        echo Symbolic link found. Deleting...
        rmdir "%TARGET%"
    ) else (
        echo Folder found (not a symlink). Deleting...
        rmdir /S /Q "%TARGET%"
    )
)

REM Create symbolic link
echo Creating symbolic link...
mklink /D "%TARGET%" "%SOURCE%"
if %errorlevel% NEQ 0 (
    if %USE_PS%==1 (
        powershell -Command "Write-Host 'Failed to create symbolic link.' -ForegroundColor Red"
    ) else (
        echo Failed to create symbolic link.
    )
    set /p dummy=Press Enter to exit...
    exit /b
)

if %USE_PS%==1 (
    powershell -Command "Write-Host 'Symbolic link created successfully.' -ForegroundColor Green"
) else (
    echo Symbolic link created successfully.
)

REM Import registry file
echo Importing registry entries...
reg import "%REGPATH%\csxs.reg"
if %errorlevel% EQU 0 (
    if %USE_PS%==1 (
        powershell -Command "Write-Host 'Registry entries imported successfully.' -ForegroundColor Green"
    ) else (
        echo Registry entries imported successfully.
    )
) else (
    if %USE_PS%==1 (
        powershell -Command "Write-Host 'Failed to import registry file.' -ForegroundColor Red"
    ) else (
        echo Failed to import registry file.
    )
)

pause
