#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import argparse
import sys

def seconds_to_srt_time(sec: float) -> str:
    """
    Перевод секунд (float) в строку формата HH:MM:SS,mmm
    """
    hours = int(sec // 3600)
    minutes = int((sec % 3600) // 60)
    seconds = int(sec % 60)
    milliseconds = int(round((sec - int(sec)) * 1000))

    # Корректируем переполнения
    if milliseconds == 1000:
        seconds += 1
        milliseconds = 0
    if seconds == 60:
        minutes += 1
        seconds = 0
    if minutes == 60:
        hours += 1
        minutes = 0

    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

def build_end_times(rows, no_pause: bool):
    """
    Возвращает список конечных времён для каждого блока.
    Если no_pause=True, для i<n-1 end = start[i+1], иначе end = orig_end[i].
    """
    n = len(rows)
    # Преобразуем все строки в числа
    starts = []
    ends_orig = []
    for i, row in enumerate(rows):
        try:
            starts.append(float(row['start']))
            ends_orig.append(float(row['end']))
        except ValueError as e:
            print(f"Ошибка конвертации времени в строке {i+1}: {e}", file=sys.stderr)
            sys.exit(1)

    if not no_pause:
        return ends_orig

    # no_pause=True
    ends = []
    for i in range(n):
        if i < n - 1:
            ends.append(starts[i+1])
        else:
            ends.append(ends_orig[i])
    return ends

def csv_to_srt(rows, no_pause: bool):
    """
    Принимает список словарей с ключами 'word','start','end' (все строки CSV),
    и флаг no_pause. Возвращает список блоков SRT в виде кортежей
    (index, start_str, end_str, text).
    """
    n = len(rows)
    starts = [float(r['start']) for r in rows]
    ends   = build_end_times(rows, no_pause)

    blocks = []
    for i, row in enumerate(rows):
        idx = i + 1
        start_str = seconds_to_srt_time(starts[i])
        end_str   = seconds_to_srt_time(ends[i])
        text      = row['word']
        blocks.append((idx, start_str, end_str, text))
    return blocks

def main():
    parser = argparse.ArgumentParser(
        description='Конвертация CSV (word,start,end) → SRT'
    )
    parser.add_argument(
        '-no_pause',
        action='store_true',
        help='установить end текущего блока = start следующего (кроме последнего)'
    )
    parser.add_argument(
        'input_csv',
        help='входной CSV-файл (колонки: word,start,end)'
    )
    parser.add_argument(
        'output_srt',
        help='имя выходного .srt'
    )
    args = parser.parse_args()

    # 1) Читаем CSV
    try:
        with open(args.input_csv, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        print(f"Ошибка при чтении CSV: {e}", file=sys.stderr)
        sys.exit(1)

    # Проверяем необходимые колонки
    for col in ('word','start','end'):
        if col not in reader.fieldnames:
            print(f"Входной CSV не содержит колонку '{col}'", file=sys.stderr)
            sys.exit(1)

    # 2) Формируем блоки
    blocks = csv_to_srt(rows, args.no_pause)

    # 3) Пишем SRT
    try:
        with open(args.output_srt, 'w', encoding='utf-8') as out:
            for idx, start_str, end_str, text in blocks:
                out.write(f"{idx}\n")
                out.write(f"{start_str} --> {end_str}\n")
                out.write(f"{text}\n\n")
    except Exception as e:
        print(f"Ошибка при записи SRT: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
