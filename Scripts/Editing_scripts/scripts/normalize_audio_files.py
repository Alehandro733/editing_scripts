import os
import sys
import glob
import csv
from typing import List, Tuple, Optional
import numpy as np
import soundfile as sf
import pyloudnorm as pyln
from pydub import AudioSegment
import tkinter as tk
import re
from tkinter import filedialog

# ────────────────────── Настройки ──────────────────────
TARGET_LUFS = -20.0
AUDIO_EXTENSIONS = ('.wav', '.mp3')
NORMALIZED_FOLDER = "normalized"

# ────────────────────── CSV & файлы ─────────────────────
def find_column_index(csv_path: str, possible_headers: List[str], delimiter: str = ",") -> Optional[int]:
    """Находит индекс колонки по заданным заголовкам (регистронезависимо)."""
    with open(csv_path, newline='', encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=delimiter)
        try:
            headers = next(reader)
        except StopIteration:
            return None
        for i, header in enumerate(headers):
            header_clean = header.strip().lower()
            for target in possible_headers:
                if header_clean == target.lower():
                    return i
    return None

def read_csv_column(csv_path: str, column_id: int, delimiter: str = ",") -> List[str]:
    """Читает указанную колонку из CSV (после заголовка)."""
    with open(csv_path, newline='', encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=delimiter)
        next(reader, None)  # Пропустить заголовок
        return [row[column_id].strip()
                for row in reader
                if len(row) > column_id and row[column_id].strip()]

def collect_audio_files(folder: str) -> List[str]:
    files = [
        f for f in os.listdir(folder)
        if f.lower().endswith(AUDIO_EXTENSIONS)
    ]
    # Сортируем по числовому значению первого вхождения цифр в имени файла
    files.sort(key=lambda x: int(re.search(r'\d+', x).group()))
    return files

# ──────────────────── Аудио‑обработка ──────────────────
def load_audio(path: str):
    ext = os.path.splitext(path)[1].lower()
    audio = AudioSegment.from_mp3(path) if ext == ".mp3" else AudioSegment.from_wav(path)
    samples = np.array(audio.get_array_of_samples())
    samples = samples.reshape((-1, audio.channels)) if audio.channels > 1 else samples.reshape((-1, 1))
    samples = samples.astype(np.float32) / (2 ** (8 * audio.sample_width - 1))
    return samples, audio.frame_rate

def normalize_audio(data, rate, target_lufs=TARGET_LUFS):
    meter = pyln.Meter(rate)
    gain_db = target_lufs - meter.integrated_loudness(data)
    return data * (10 ** (gain_db / 20))

def format_output_name(speaker: str, idx: Optional[int], ext: str = "wav") -> str:
    """
    Формирует имя выходного файла.
    Если idx не None — добавляется префикс-номер, иначе только имя спикера.
    """
    base = f"{speaker}"
    if idx is not None:
        base = f"{idx:03d}_{base}"
    return f"{base}.{ext}"

def save_normalized(in_path: str, out_path: str, idx: Optional[int], speaker: str) -> None:
    out_name = os.path.basename(out_path)
    print(f"[{'---' if idx is None else f'{idx:03d}'}] {os.path.basename(in_path)} → {out_name}")
    data, rate = load_audio(in_path)
    sf.write(out_path,
             normalize_audio(data, rate),
             rate, subtype="PCM_16")

# ──────────────────── Диалоги / выборы ─────────────────
def ask_file(initial_dir: str, mask: str) -> Optional[str]:
    root = tk.Tk(); root.withdraw()
    return filedialog.askopenfilename(initialdir=initial_dir,
                                      filetypes=[(mask, mask)])

def select_csv(parent: str) -> Optional[str]:
    csv_files = glob.glob(os.path.join(parent, "*.csv"))
    if len(csv_files) == 1:
        print(f"Автоматически выбран CSV: {csv_files[0]}")
        return csv_files[0]
    print(f"Найдено {len(csv_files)} CSV‑файлов в {parent}. Выберите нужный (или отмена):")
    path = ask_file(parent, "*.csv")
    return path if path else None

# ────────────────────── Pipeline helpers ────────────────
def prepare_dst(src_dir: str) -> Tuple[str, str]:
    parent = os.path.abspath(os.path.join(src_dir, os.pardir))
    dst_dir = os.path.join(parent, NORMALIZED_FOLDER)
    os.makedirs(dst_dir, exist_ok=True)
    return parent, dst_dir

def verify_counts(audio_files: List[str], speakers: List[str]) -> None:
    if len(audio_files) != len(speakers):
        sys.exit(f"❌ Несовпадение: файлов {len(audio_files)}, записей {len(speakers)}.")

def process_batch(src_dir: str, dst_dir: str, csv_path: Optional[str]) -> None:
    audio_files = collect_audio_files(src_dir)
    if not audio_files:
        sys.exit("В исходной папке нет .wav/.mp3 файлов.")

    speakers = []
    csv_valid = False

    # Попытка использовать CSV если он доступен
    if csv_path and os.path.isfile(csv_path):
        try:
            column_id = find_column_index(csv_path, ["name", "speaker"])
            if column_id is not None:
                speakers = read_csv_column(csv_path, column_id)
                csv_valid = (len(speakers) == len(audio_files))
        except Exception as e:
            print(f"⚠️ Ошибка обработки CSV: {e}")

    # Фолбек на имена файлов, если CSV не подошёл
    if not csv_valid:
        speakers = [os.path.splitext(f)[0] for f in audio_files]
        if csv_path:
            print("⚠️ Используются оригинальные имена файлов (проблемы с CSV)")

    verify_counts(audio_files, speakers)

    # Флаг: использовать ли префикс-номер
    use_counter = csv_valid

    for idx, (fname, spk) in enumerate(zip(audio_files, speakers), start=1):
        # генерируем имя: если use_counter=False, передаем idx=None
        out_name = format_output_name(spk, idx if use_counter else None)
        in_path = os.path.join(src_dir, fname)
        out_path = os.path.join(dst_dir, out_name)
        try:
            save_normalized(in_path, out_path, idx if use_counter else None, spk)
        except Exception as e:
            print(f"   ❌  Ошибка «{fname}»: {e}")

# ─────────────────────────── CLI ───────────────────────
def main() -> None:
    args = sys.argv[1:]

    if len(args) == 1:  # Автоматический режим
        src_dir = args[0]
        if not os.path.isdir(src_dir):
            sys.exit(f"Папка не найдена: {src_dir}")
        parent, dst_dir = prepare_dst(src_dir)
        csv_path = select_csv(parent)
        process_batch(src_dir, dst_dir, csv_path)

    elif len(args) == 3:  # Ручной режим
        src_dir, dst_dir, csv_path = args
        if not os.path.isdir(src_dir):
            sys.exit(f"Папка не найдена: {src_dir}")
        if csv_path and not os.path.isfile(csv_path):
            print(f"⚠️ CSV не найден: {csv_path}")
            csv_path = None
        os.makedirs(dst_dir, exist_ok=True)
        process_batch(src_dir, dst_dir, csv_path)

    else:
        print("Usage:")
        print("  python normalize_audio_files.py <src_dir>")
        print("  python normalize_audio_files.py <src_dir> <dst_dir> <csv_path>")
        sys.exit(1)

if __name__ == "__main__":
    main()
