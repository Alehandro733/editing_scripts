@echo off
REM — Устанавливаем консоль в UTF-8 (чтобы видеть русские сообщения)
chcp 65001 >nul

REM — Проверяем, передан ли файл
if "%~1"=="" (
    echo Пожалуйста, перетащите CSV‑файл на этот батник.
    pause
    exit /b
)

REM — Получаем папку, где лежит этот батник
set "SCRIPT_DIR=%~dp0"

REM — Запускаем скрипт
python "%SCRIPT_DIR%/scripts/csv_to_srt.py" "%~1"

pause
