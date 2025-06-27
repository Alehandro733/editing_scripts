@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

cd /d "%~dp0"

REM — Задать путь к файлу run_mfa_wrapper.py. После WRAPPER_PATH= нужно написать абсолютный или относительный путь сохраняя кавычку в конце

REM--------------------------------------------------

set "WRAPPER_PATH=%~dp0..\..\mfa\run_mfa_wrapper.py"

REM--------------------------------------------------

if not exist "%WRAPPER_PATH%" (
    echo Ошибка: файл run_mfa_wrapper.py не найден по пути:
    echo    %WRAPPER_PATH%
    echo Выберите изменить bat файл и после WRAPPER_PATH= напишите путь к файлу run_mfa_wrapper.py 
    echo он находится в репозитории, в папке mfa
    pause
    exit /b 1
)

set "wav_arg="
set "text_arg="

REM — Если передан файл, определяем расширение и формируем аргумент
if not "%~1"=="" (
    set "ext=%~x1"
    if /I "!ext!"==".wav" (
        set wav_arg=--wav-path "%~1"
    ) else if /I "!ext!"==".txt" (
        set text_arg=--text-path "%~1"
    ) else if /I "!ext!"==".srt" (
        set text_arg=--text-path "%~1"
    ) else (
        echo Файл "%~1" не распознан как .wav/.txt/.srt. Продолжаем без файла.
    )
)

:ask_lang
REM — Запрос языка
set /p lang=Введите код языка (пример: fr, pt, en): 

REM — Запуск
echo Выполняю: python "%WRAPPER_PATH%" --language %lang% !wav_arg! !text_arg!
python "%WRAPPER_PATH%" --language %lang% !wav_arg! !text_arg!
if errorlevel 1 (
    echo Ошибка при выполнении скрипта.
    pause
    exit /b %errorlevel%
)

endlocal
