@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: === Настройки ===
set GIT_BIN=%~dp0mingit\cmd\git.exe
set REPO_DIR=%~dp0editing_scripts
set REPO_URL=https://github.com/Alehandro733/editing_scripts.git
set BRANCH=master

echo === Используем Git: %GIT_BIN%
echo === Целевая папка: %REPO_DIR%
echo === Целевая ветка: %BRANCH%
echo.

:: === Клонируем, если нет репозитория ===
if not exist "%REPO_DIR%\.git" (
    echo === Репозиторий не найден. Клонируем...
    "%GIT_BIN%" clone --branch %BRANCH% %REPO_URL% "%REPO_DIR%"
    goto :done
)

:: === Синхронизация существующего репозитория ===
echo === Репозиторий найден. Синхронизация...
cd /d "%REPO_DIR%"

"%GIT_BIN%" fetch --all
"%GIT_BIN%" checkout %BRANCH%
"%GIT_BIN%" reset --hard origin/%BRANCH%
"%GIT_BIN%" clean -fd

:done
echo.
echo === ✅ Репозиторий полностью синхронизирован с веткой '%BRANCH%'.
pause
