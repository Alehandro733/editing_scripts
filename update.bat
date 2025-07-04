@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: === Параметры:
set "GIT_BIN=%~dp0tools\minigit\cmd\git.exe"
set "REPO_URL=https://github.com/Alehandro733/editing_scripts.git"
set "BRANCH=master"
set "TMP_NAME=_temp_repo"

cd /d "%~dp0"

:: Если нет .git — первичная инициализация
if not exist ".git" (
    echo Первичная загрузка репозитория...
    :: Удаляем временную папку на всякий случай
    if exist "%TMP_NAME%" rd /s /q "%TMP_NAME%"
    "%GIT_BIN%" clone --branch %BRANCH% %REPO_URL% "%TMP_NAME%" || (
        echo Ошибка: не удалось клонировать репозиторий & pause & goto :eof
    )
    :: Удаляем всё в текущей директории, кроме временной папки
    pushd "%~dp0"
    for /f "delims=" %%i in ('dir /b') do (
        if /i not "%%i"=="%TMP_NAME%" rd /s /q "%%i" 2>nul
    )
    popd
    :: Перемещаем содержимое клона из TMP в корень
    pushd "%TMP_NAME%"
    for /f "delims=" %%i in ('dir /b /a') do (
        move "%%i" "%~dp0" >nul
    )
    popd
    :: Удаляем временную папку
    rd /s /q "%TMP_NAME%"
    echo Инициализация завершена.
) else (
    :: Уже есть .git — обновляем
    echo Обновление репозитория...
    "%GIT_BIN%" fetch --all
    "%GIT_BIN%" checkout %BRANCH% || (
        echo Ошибка: не удалось переключиться на ветку %BRANCH% & pause & goto :eof
    )
    "%GIT_BIN%" reset --hard origin/%BRANCH%
    :: Удалить все не ослеживаемые файлы из репозитория:
    ::  "%GIT_BIN%" clean -fd
	
    :: === Очищаем внутренности tools\miniforge3\pkgs ===
	if exist "%~dp0tools\miniforge3\pkgs" (
    echo Очищаю содержимое папки tools\miniforge3\pkgs...
    :: Удаляем все подкаталоги
    for /d %%P in ("%~dp0tools\miniforge3\pkgs\*") do (
        rd /s /q "%%P"
    )
    :: Удаляем все файлы
    del /q "%~dp0tools\miniforge3\pkgs\*.*" 2>nul
    echo Очистка папки pkgs завершена.
)	


    echo Обновление завершено.
)

pause
