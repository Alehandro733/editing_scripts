#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from typing import Tuple
import numpy as np
import soundfile as sf
import pyloudnorm as pyln
from pydub import AudioSegment

# ────────────────────── Настройки ──────────────────────
TARGET_LUFS = -20.0
AUDIO_EXTENSIONS = ('.wav', '.mp3')
NORMALIZED_FOLDER = "normalized"

# ──────────────────── Аудио-обработка ──────────────────
def load_audio(path: str) -> Tuple[np.ndarray, int]:
    """
    Загружает WAV/MP3, возвращает numpy-массив формата float32 в диапазоне [-1, 1]
    и частоту дискретизации.
    """
    ext = os.path.splitext(path)[1].lower()
    audio = AudioSegment.from_mp3(path) if ext == ".mp3" else AudioSegment.from_wav(path)
    samples = np.array(audio.get_array_of_samples())
    # (num_samples, channels)
    samples = samples.reshape((-1, audio.channels)) if audio.channels > 1 else samples.reshape((-1, 1))
    # нормализуем к [-1, 1]
    samples = samples.astype(np.float32) / (2 ** (8 * audio.sample_width - 1))
    return samples, audio.frame_rate

def normalize_audio(data: np.ndarray, rate: int, target_lufs: float = TARGET_LUFS) -> np.ndarray:
    """
    Нормализация по интегральной громкости до target_lufs.
    """
    meter = pyln.Meter(rate)
    gain_db = target_lufs - meter.integrated_loudness(data)
    return data * (10 ** (gain_db / 20))

def save_wav(data: np.ndarray, rate: int, out_path: str) -> None:
    """
    Сохраняет массив float32 [-1,1] в WAV PCM_16 (soundfile сам сконвертирует).
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    sf.write(out_path, data, rate, subtype="PCM_16")

# ──────────────────────── Логика ───────────────────────
def build_output_root(src_dir: str) -> str:
    """
    Создаёт/возвращает путь вида <parent_of_src>/normalized/<basename(src_dir)>.
    """
    src_dir = os.path.abspath(src_dir)
    parent = os.path.dirname(src_dir)
    base = os.path.basename(src_dir.rstrip(os.sep))
    normalized_root = os.path.join(parent, NORMALIZED_FOLDER, base)
    os.makedirs(normalized_root, exist_ok=True)
    return normalized_root

def change_ext_to_wav(path: str) -> str:
    base, _ = os.path.splitext(path)
    return base + ".wav"

def should_process_file(path: str) -> bool:
    return os.path.isfile(path) and os.path.splitext(path)[1].lower() in AUDIO_EXTENSIONS

def process_tree(src_dir: str) -> None:
    """
    Рекурсивно проходит по src_dir, нормализует все WAV/MP3 и кладёт
    результат в <parent>/normalized/<basename(src_dir)> с сохранением структуры.
    """
    src_dir = os.path.abspath(src_dir)
    if not os.path.isdir(src_dir):
        sys.exit(f"❌ Папка не найдена: {src_dir}")

    out_root = build_output_root(src_dir)
    print(f"📁 Источник:   {src_dir}")
    print(f"📁 Назначение: {out_root}")
    print("—" * 60)

    total = 0
    ok = 0
    skipped = 0

    for root, dirs, files in os.walk(src_dir):
        # относительный путь от корня входной папки
        rel_root = os.path.relpath(root, src_dir)
        for fname in files:
            in_path = os.path.join(root, fname)
            if not should_process_file(in_path):
                skipped += 1
                continue

            # относительный путь файла и целевой путь в normalized (меняем расширение на .wav)
            rel_file = os.path.normpath(os.path.join(rel_root, fname)) if rel_root != "." else fname
            out_rel = change_ext_to_wav(rel_file)
            out_path = os.path.join(out_root, out_rel)

            total += 1
            try:
                data, rate = load_audio(in_path)
                data_norm = normalize_audio(data, rate, TARGET_LUFS)
                save_wav(data_norm, rate, out_path)
                print(f"✔ {os.path.relpath(in_path, src_dir)}  ->  {os.path.relpath(out_path, out_root)}")
                ok += 1
            except Exception as e:
                print(f"✖ Ошибка «{os.path.relpath(in_path, src_dir)}»: {e}")

    print("—" * 60)
    print(f"Готово. Успешно: {ok}/{total}. Пропущено (не аудио): {skipped}.")

# ─────────────────────────── CLI ───────────────────────
def main() -> None:
    if len(sys.argv) != 2:
        print("Использование:")
        print("  python normalize_tree.py <путь_к_папке>")
        sys.exit(1)
    process_tree(sys.argv[1])

if __name__ == "__main__":
    main()
