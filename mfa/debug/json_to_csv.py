#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import csv
import argparse
import sys

def parse_flat_words(data, writer):
    """Пишем каждое слово как отдельную строку с колонками word, start, end."""
    for start, end, label in data.get('tiers', {}).get('words', {}).get('entries', []):
        writer.writerow({
            'word': label,
            'start': start,
            'end': end
        })

def parse_words_with_phones(data, writer):
    """
    Сначала строка со словом (phone пусто, но указаны start/end слова),
    затем по одной строке на каждую фонему внутри этого слова (word пусто).
    """
    words = data.get('tiers', {}).get('words', {}).get('entries', [])
    phones = data.get('tiers', {}).get('phones', {}).get('entries', [])

    # Отсортируем фонемы по времени начала
    phones = sorted(phones, key=lambda x: x[0])

    for w_start, w_end, w_label in words:
        # 1) строка со словом
        writer.writerow({
            'word':  w_label,
            'phone': '',
            'start': w_start,
            'end':   w_end
        })
        # 2) строки с фонемами внутри [w_start, w_end]
        for p_start, p_end, p_label in phones:
            if p_start >= w_start and p_end <= w_end:
                writer.writerow({
                    'word':  '',
                    'phone': p_label,
                    'start': p_start,
                    'end':   p_end
                })

def main():
    parser = argparse.ArgumentParser(
        description='Парсер JSON с таймингами в CSV.'
    )
    parser.add_argument(
        '-phones',
        action='store_true',
        help='если указан, группировать слова с их фонемами и выводить start/end для всех'
    )
    parser.add_argument(
        'input_json',
        help='путь к входному JSON-файлу'
    )
    parser.add_argument(
        'output_csv',
        help='путь к выходному CSV-файлу'
    )
    args = parser.parse_args()

    # 1) Загрузка JSON
    try:
        with open(args.input_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f'Ошибка при чтении JSON: {e}', file=sys.stderr)
        sys.exit(1)

    # 2) Открываем CSV на запись
    try:
        with open(args.output_csv, 'w', newline='', encoding='utf-8') as csvfile:
            if args.phones:
                # header: word, phone, start, end
                fieldnames = ['word', 'phone', 'start', 'end']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                parse_words_with_phones(data, writer)
            else:
                # header: word, start, end
                fieldnames = ['word', 'start', 'end']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                parse_flat_words(data, writer)
    except Exception as e:
        print(f'Ошибка при записи CSV: {e}', file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
