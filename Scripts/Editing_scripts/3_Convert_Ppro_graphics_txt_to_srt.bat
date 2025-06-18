@echo off
REM — Устанавливаем консоль в UTF-8 (чтобы видеть русские сообщения)
chcp 65001 >nul

REM — Проверяем, передан ли файл
if "%~1"=="" (
    echo Пожалуйста, перетащите TXT-файл на этот батник.
    pause
    exit /b
)

REM — Получаем папку, где лежит этот батник
set "SCRIPT_DIR=%~dp0"

REM — Запускаем скрипт с частотой кадров 25 fps
python "%SCRIPT_DIR%/scripts/convert_ppro_txt_to_srt.py" "%~1" 25

pause
