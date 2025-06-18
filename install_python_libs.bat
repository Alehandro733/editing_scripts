@echo off
chcp 65001 >nul
echo Обновление pip...
python -m pip install --upgrade pip

echo Установка необходимых библиотек...
pip install numpy soundfile pyloudnorm pydub

echo Установка завершена.
pause
