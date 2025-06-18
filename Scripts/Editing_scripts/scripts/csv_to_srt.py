# csv_to_srt.py
import sys
import csv
from pathlib import Path
from datetime import timedelta

def format_srt_time(td: timedelta) -> str:
    """
    Форматирует timedelta в строку SRT-времени: HH:MM:SS,mmm
    """
    total_seconds = int(td.total_seconds())
    milliseconds = int(td.microseconds / 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

def sanitize_filename(name: str) -> str:
    """
    Заменяет в заголовке недопустимые для имени файла символы на подчёркивания,
    а пробелы — на нижнее подчёркивание.
    """
    safe = []
    for c in name:
        if c.isalnum() or c in (' ', '-', '_'):
            safe.append(c)
        else:
            safe.append('_')
    return ''.join(safe).strip().replace(' ', '_')

def csv_to_srt(input_path: str, duration: int = 3):
    """
    Генерирует .srt-файлы из каждого столбца CSV,
    игнорируя столбцы, в заголовках которых:
      - пустая строка;
      - есть 'images' или 'audio'.
    
    :param input_path: путь к исходному CSV-файлу
    :param duration: длительность каждого субтитра в секундах
    """
    input_path = Path(input_path)
    if not input_path.exists() or input_path.suffix.lower() != '.csv':
        print("Укажите корректный путь к CSV-файлу.")
        return

    # Читаем CSV
    with input_path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        try:
            headers = next(reader)
        except StopIteration:
            print("CSV-файл пуст.")
            return
        rows = list(reader)

    # Для каждого столбца
    for col_idx, header in enumerate(headers):
        # Пропускаем пустые заголовки
        if not header or not header.strip():
            print(f"Пропускаем пустой заголовок в столбце #{col_idx + 1}.")
            continue

        # Пропускаем столбцы с нежелательными словами
        low = header.lower()
        if 'images' in low or 'audio' in low or 'name' in low:
            print(f"Пропускаем столбец «{header}» (contains 'images' or 'audio' or 'name').")
            continue

        # Собираем только непустые ячейки
        blocks = []
        for row in rows:
            if col_idx < len(row):
                cell = row[col_idx].strip()
                if cell:
                    blocks.append(cell)

        # Пропускаем столбцы без контента
        if not blocks:
            continue

        # Генерируем имя выходного файла
        safe_header = sanitize_filename(header)
        output_path = input_path.with_name(f"{safe_header}.srt")

        # Пишем SRT
        with output_path.open('w', encoding='utf-8') as out:
            start_time = timedelta(seconds=0)
            for idx, text in enumerate(blocks, start=1):
                end_time = start_time + timedelta(seconds=duration)
                out.write(f"{idx}\n")
                out.write(f"{format_srt_time(start_time)} --> {format_srt_time(end_time)}\n")
                out.write(f"{text}\n\n")
                start_time = end_time

        print(f"Сгенерирован: {output_path.name}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Использование: python csv_to_srt.py путь_к_файлу.csv")
    else:
        csv_to_srt(sys.argv[1])
