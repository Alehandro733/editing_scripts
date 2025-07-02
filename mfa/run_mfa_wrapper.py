#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Обёртка для запуска mfa_full_pipe.py с возможностью
выбора WAV и/или TXT/SRT файла через диалог, если они
не переданы или не найдены, и с разумным дефолтом для
--output-srt в той же папке, что и текстовый файл.
"""

import argparse
import subprocess
import sys
from pathlib import Path

def select_file(filetypes, title):
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except ImportError:
        print("Ошибка: модуль tkinter недоступен. Укажите файлы через аргументы.")
        sys.exit(1)

    root = tk.Tk()
    root.withdraw()
    path = filedialog.askopenfilename(title=title, filetypes=filetypes)
    root.destroy()
    if not path:
        messagebox.showerror("Ошибка", f"Не выбран файл для «{title}».")
        sys.exit(1)
    return path

def main():
    # := Определяем директорию, где лежит этот скрипт
    SCRIPT_DIR = Path(__file__).resolve().parent

    ap = argparse.ArgumentParser(
        description="Wrapper для mfa_full_pipe.py"
    )
    ap.add_argument(
        '--language', default='fr',
        help="код языка (по умолчанию: fr)"
    )
    ap.add_argument(
        '--wav-path', dest='wav_path',
        help="путь к WAV-файлу"
    )
    ap.add_argument(
        '--text-path', dest='text_path',
        help="путь к текстовому файлу (TXT или SRT)"
    )
    ap.add_argument(
        '--output-json', dest='output_json', default='timings.json',
        help="имя выходного JSON (по умолчанию: timings.json)"
    )
    ap.add_argument(
        '--output-srt', dest='output_srt',
        help="имя выходного SRT (по умолчанию: animated_subs.srt в той же папке, что и --text-path)"
    )
    ap.add_argument(
        '--base-color', dest='base_color', default='000000',
        help="цвет основного текста (6 hex без ‘#’)"
    )
    ap.add_argument(
        '--highlight-color', dest='highlight_color', default='2DE471',
        help="цвет выделения (6 hex без ‘#’)"
    )

    args = ap.parse_args()

    # Проверяем WAV-файл
    wav_path = args.wav_path
    if not wav_path or not Path(wav_path).is_file():
        print("WAV-файл не указан или не найден — открою диалог выбора.")
        wav_path = select_file(
            [("WAV files", "*.wav"), ("Все файлы", "*.*")],
            "Выберите WAV-файл"
        )

    # Проверяем текстовый файл
    text_path = args.text_path
    if not text_path or not Path(text_path).is_file():
        print("Текстовый файл не указан или не найден — открою диалог выбора.")
        text_path = select_file(
            [("Text files", "*.txt *.srt"), ("Все файлы", "*.*")],
            "Выберите TXT или SRT файл"
        )

    # Определяем output_srt: если не передан, кладём в ту же папку, что и текст
    if args.output_srt:
        output_srt = args.output_srt
    else:
        text_dir = Path(text_path).parent
        output_srt = str(text_dir / 'animated_subs.srt')
        print(f"--output-srt не передан. Использую '{output_srt}'.")

    # Полный путь к mfa_full_pipe.py
    mfa_script = SCRIPT_DIR / 'mfa_full_pipe.py'

    # Собираем команду
    cmd = [
        sys.executable,
        str(mfa_script),
        "--language",        args.language,
        "--wav-path",        wav_path,
        "--text-path",       text_path,
        "--output-json",     args.output_json,
        "--output-srt",      output_srt,
        "--base-color",      args.base_color,
        "--highlight-color", args.highlight_color
    ]


    try:
        subprocess.run(cmd, check=True, cwd=str(SCRIPT_DIR))
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при выполнении mfa_full_pipe.py (код {e.returncode})")
        sys.exit(e.returncode)

if __name__ == "__main__":
    main()
