#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для генерации SRT-субтитров c подсветкой караоке
(принимает на вход TXT или SRT + JSON-тайминги из MFA)
Можно выбрать базовый цвет и цвет посветки
"""

import argparse
import json
import string
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ---------------------------------------------------------------------------

def parse_timestamp(timestamp_str: str) -> float:
    """'HH:MM:SS,mmm'  ->  секунды (float)"""
    time_part, millis_part = timestamp_str.strip().split(',')
    hours, minutes, seconds = map(int, time_part.split(':'))
    return hours * 3600 + minutes * 60 + seconds + int(millis_part) / 1000.0

def normalize_token(token: str) -> str:
    specials = {"<eps>", "<unk>"}
    if token in specials:
        return token
    token = (token
             .replace('’', "'")
             .replace('‘', "'")
             .replace('“', '"')
             .replace('”', '"')
             .lower()
             .strip(string.punctuation.replace("'", "").replace("-", "")))
    return token

def remove_tags(text: str) -> str:
    """Удаляет любые HTML/XML-теги"""
    return re.sub(r'<[^>]+>', '', text)

# ---------------------------------------------------------------------------
# ПАРСИНГ JSON ТАЙМИНГОВ
# ---------------------------------------------------------------------------

def parse_json(json_path: str):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    entries = data['tiers']['words']['entries']
    json_entries_raw = []
    for start, end, label in entries:
        json_entries_raw.append({
            'raw_label': label,
            'normalized_word': normalize_token(label),
            'start_time': start,
            'end_time': end
        })

    # фильтруем <eps>
    json_entries_filtered = [e.copy() for e in json_entries_raw
                             if e['raw_label'] != '<eps>']
    return json_entries_raw, json_entries_filtered

# ---------------------------------------------------------------------------
# ПАРСИНГ ВХОДНОГО ТЕКСТА (SRT / TXT)
# ---------------------------------------------------------------------------

def parse_srt(srt_path: str):
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    blocks = [b.strip() for b in content.split('\n\n') if b.strip()]
    lines = []
    block_starts = []

    token_re = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿœŒ'’\-]+")
    txt_words_normalized = []
    txt_word_spans = []

    for block in blocks:
        parts = block.split('\n')
        if len(parts) < 3 or '-->' not in parts[1]:
            continue

        start_ts, _ = parts[1].split('-->', 1)
        block_starts.append(parse_timestamp(start_ts))

        text = ' '.join(ln.strip() for ln in parts[2:])
        clean_text = remove_tags(text)
        lines.append(clean_text)

        norm_line = clean_text.replace('’', "'")
        for m in token_re.finditer(norm_line):
            tok = m.group(0)
            txt_words_normalized.append(normalize_token(tok))
            txt_word_spans.append((len(lines) - 1, m.start(), m.end()))

    return lines, txt_words_normalized, txt_word_spans, block_starts

def parse_txt(txt_path: str):
    with open(txt_path, 'r', encoding='utf-8') as f:
        lines = [ln.rstrip() for ln in f if ln.strip()]

    token_re = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿœŒ'’\-]+")
    txt_words_normalized = []
    txt_word_spans = []

    for li, line in enumerate(lines):
        norm_line = line.replace('’', "'")
        for m in token_re.finditer(norm_line):
            tok = m.group(0)
            txt_words_normalized.append(normalize_token(tok))
            txt_word_spans.append((li, m.start(), m.end()))

    return lines, txt_words_normalized, txt_word_spans, None

def parse_input(path: str):
    return parse_srt(path) if path.lower().endswith('.srt') else parse_txt(path)

# ---------------------------------------------------------------------------
# СОВПАДЕНИЕ СЛОВ ТЕКСТА И JSON-ТАЙМИНГОВ
# ---------------------------------------------------------------------------

def match_one(txt_idx, json_idx, txt_words, json_entries_filtered, json_entries_raw, ratio_threshold=0.7):

    if json_idx >= len(json_entries_filtered):
        return False, json_idx, None, None, "error: no more entries", txt_idx

    txt_word = txt_words[txt_idx]
    json_entry = json_entries_filtered[json_idx]
    json_word = json_entry['normalized_word']
    start_time = json_entry['start_time']
    end_time = json_entry['end_time']

    # 1. EPS-MISALIGN-FIX
    if (txt_idx + 1 < len(txt_words)) and (json_word == txt_words[txt_idx + 1]):
        if json_idx == 0:
            return False, json_idx, None, None, "error: cannot fix misalignment", txt_idx

        prev_json_entry = json_entries_filtered[json_idx - 1]
        raw_idx = next((k for k, e in enumerate(json_entries_raw)
                        if e['start_time'] == prev_json_entry['start_time'] and
                        e['normalized_word'] == prev_json_entry['normalized_word']), None)

        if raw_idx is None or raw_idx == 0:
            return False, json_idx, None, None, "error: cannot fix misalignment", txt_idx

        prev_raw_entry = json_entries_raw[raw_idx - 1]
        fix_start = (prev_raw_entry['start_time']
                     if prev_raw_entry['raw_label'] == "<eps>"
                     else prev_raw_entry['end_time'])

        return True, json_idx, fix_start, end_time, "eps-misalign-fix", txt_idx

    # 2. Normal matching
    if json_word == "<unk>":
        ok = (json_idx + 1 < len(json_entries_filtered) and
              txt_idx + 1 < len(txt_words) and
              (txt_words[txt_idx + 1] in json_entries_filtered[json_idx + 1]['normalized_word'] or
               json_entries_filtered[json_idx + 1]['normalized_word'] in txt_words[txt_idx + 1]))
    else:
        ratio = len(json_word) / len(txt_word) if txt_word else 0
        ok = ratio >= ratio_threshold and json_word in txt_word
        if not ok:
            idx0 = txt_word.find(json_word)
            if idx0 != -1:
                end_pos = idx0 + len(json_word)
                if end_pos == len(txt_word) or not txt_word[end_pos].isalpha():
                    ok = True
                elif idx0 == 0 or not txt_word[idx0 - 1].isalpha():
                    ok = True

    if ok:
        return True, json_idx + 1, start_time, end_time, "normal", txt_idx + 1
    else:
        return False, json_idx + 1, None, None, "error", txt_idx + 1

def match_timings(txt_words, json_entries_filtered, json_entries_raw, log_path: Path):
    # # ——— DEBUG: пишем CSV с тремя колонками, по одной строке на элемент ———
    # import csv
    # import json as _json

    # debug_csv = log_path.with_name('debug_match_timings.csv')
    # n = max(len(txt_words), len(json_entries_filtered), len(json_entries_raw))

    # with open(debug_csv, 'w', encoding='utf-8', newline='') as _f:
    #     writer = csv.writer(_f)
    #     writer.writerow(['txt_word', 'json_filtered', 'json_raw'])
    #     for i in range(n):
    #         txt = txt_words[i] if i < len(txt_words) else ''
    #         jf = _json.dumps(json_entries_filtered[i], ensure_ascii=False) if i < len(json_entries_filtered) else ''
    #         jr = _json.dumps(json_entries_raw[i], ensure_ascii=False)      if i < len(json_entries_raw)      else ''
    #         writer.writerow([txt, jf, jr])
    # # ————————————————————————————————————————————————————————————————

    max_txt_word_len = max((len(w) for w in txt_words), default=4)
    max_json_word_len = max((len(e['normalized_word']) for e in json_entries_filtered),
                            default=5)
    word_timings = []
    txt_idx = json_idx = 0
    n_words = len(txt_words)
    error_mode = False
    post_error_written = 0

    with open(log_path, 'w', encoding='utf-8') as log:
        log.write(f"{'TXT_WORD':<{max_txt_word_len}}  "
                  f"{'JSON_WORD':<{max_json_word_len}}  START    END    STATUS\n")
        log.write(f"{'-' * max_txt_word_len}  "
                  f"{'-' * max_json_word_len}  ------  ------  ------\n")

        while txt_idx < n_words:
            # попытка починки split-слов
            while (json_idx + 1 < len(json_entries_filtered)):
                next_json_word = json_entries_filtered[json_idx + 1]['normalized_word']
                pattern = rf"(?:^|[-']){re.escape(next_json_word)}(?:$|[-'])"
                if re.search(pattern, txt_words[txt_idx]):
                    removed = json_entries_filtered.pop(json_idx + 1)
                    log.write(f"{txt_words[txt_idx]:<{max_txt_word_len}}  "
                              f"{removed['normalized_word']:<{max_json_word_len}}        "
                              f"      split-fix(removed)\n")
                else:
                    break

            ok, new_json_idx, start, end, action, new_txt_idx = match_one(
                txt_idx, json_idx, txt_words,
                json_entries_filtered, json_entries_raw
            )

            current_json_word = (json_entries_filtered[new_json_idx - 1]['normalized_word']
                                 if ok else '')
            if ok and start is not None:
                if end is None:
                    end = json_entries_filtered[new_json_idx - 1]['end_time']
                word_timings.append({'start': start, 'end': end})
                start_s = f"{start:>6.3f}"
                end_s = f"{end:>6.3f}"
            else:
                start_s = end_s = '      '

            log.write(f"{txt_words[txt_idx]:<{max_txt_word_len}}  "
                      f"{current_json_word:<{max_json_word_len}}  "
                      f"{start_s}  {end_s}  {action}\n")

            if "error" in action:
                error_mode = True
            elif error_mode:
                post_error_written += 1

            if error_mode and post_error_written >= 5:
                sys.exit("Прекращено после ошибки и 5 строком следом.")

            txt_idx, json_idx = new_txt_idx, new_json_idx

    if len(word_timings) != n_words:
        sys.exit(f"Сопоставлено {len(word_timings)} из {n_words} слов.")

    return word_timings

# ---------------------------------------------------------------------------
# ФОРМАТИРОВАНИЕ ВРЕМЕНИ
# ---------------------------------------------------------------------------

def format_timestamp(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    hours, rem_ms = divmod(total_ms, 3600 * 1000)
    minutes, rem_ms = divmod(rem_ms, 60 * 1000)
    secs, millis = divmod(rem_ms, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

# ---------------------------------------------------------------------------
# ГЕНЕРАЦИЯ SRT С ДВУМЯ ЦВЕТАМИ
# ---------------------------------------------------------------------------

def write_srt(txt_lines, txt_word_spans, word_timings, block_starts, output_path, highlight_color, base_color):
    # группируем слова по строкам
    lines2words = {}
    for idx, (li, si, ei) in enumerate(txt_word_spans):
        lines2words.setdefault(li, []).append(idx)

    subs = []
    sub_idx = 1

    for li, line in enumerate(txt_lines):
        if li not in lines2words:
            continue
        word_indices = lines2words[li]
        n_words = len(word_indices)

        for i, w_idx in enumerate(word_indices):
            _, start_pos, _ = txt_word_spans[w_idx]

            seg_start = 0 if i == 0 else start_pos
            if i < n_words - 1:
                next_start = txt_word_spans[word_indices[i + 1]][1]
                seg_end = next_start
            else:
                seg_end = len(line)

            # разбиваем на префикс/выделенный/суффикс
            prefix   = line[:seg_start]
            selected = line[seg_start:seg_end]
            suffix   = line[seg_end:]

            # HTML для выделения (добавляем ‘#’ перед кодом)
            hl = f'<font color="#{highlight_color}">{selected}</font>'

            # собираем итоговую строку
            if i == 0:
                text_html = hl + (f'<font color="#{base_color}">{suffix}</font>' if suffix else '')
            elif i == n_words - 1:
                text_html = (f'<font color="#{base_color}">{prefix}</font>' if prefix else '') + hl
            else:
                text_html = (
                    f'<font color="#{base_color}">{prefix}</font>' +
                    hl +
                    f'<font color="#{base_color}">{suffix}</font>'
                )

            # тайминги
            if i == 0 and block_starts and li < len(block_starts):
                start_time = block_starts[li]
            else:
                start_time = word_timings[w_idx]['start']
            end_time = (word_timings[word_indices[i + 1]]['start']
                        if i < n_words - 1 else word_timings[w_idx]['end'])

            subs.append({
                'index': sub_idx,
                'start': start_time,
                'end': end_time,
                'text': text_html
            })
            sub_idx += 1

    # синхронизируем интервалы
    for k in range(len(subs) - 1):
        subs[k]['end'] = subs[k + 1]['start']

    # запись в файл
    with open(output_path, 'w', encoding='utf-8') as f:
        for s in subs:
            f.write(f"{s['index']}\n")
            f.write(f"{format_timestamp(s['start'])} --> {format_timestamp(s['end'])}\n")
            f.write(f"{s['text']}\n\n")

    print(f"SRT файл создан: {output_path}")

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Генерация караоке-SRT")
    ap.add_argument('-j', '--json',     required=True, help="JSON c таймингами")
    ap.add_argument('-t', '--text',     required=True, help="TXT или SRT-транскрипт")
    ap.add_argument('-o', '--output',   required=True, help="выходной SRT")
    ap.add_argument('-c', '--highlight-color',
                    dest='highlight_color',
                    default='2DE471',
                    help="цвет выделения (6 hex-цифр без ‘#’), пример: 2DE471")
    ap.add_argument('-b', '--base-color',
                    dest='base_color',
                    default='FFFFFF',
                    help="цвет основного текста (6 hex-цифр без ‘#’), пример: FFFFFF")

    args = ap.parse_args()

    # проверка, что коды цветов — ровно 6 hex-символов
    for val, name in ((args.highlight_color, 'highlight_color'),
                      (args.base_color,     'base_color')):
        if not re.fullmatch(r'[0-9A-Fa-f]{6}', val):
            sys.exit(f"Неверный код `{name}`: «{val}». Ожидается 6 hex-символов без ‘#’.")

    json_raw, json_filtered = parse_json(args.json)
    txt_lines, txt_words_norm, txt_word_spans, block_starts = parse_input(args.text)
    log_path = Path('log_split.txt')
    word_timings = match_timings(
        txt_words_norm, json_filtered, json_raw, log_path
    )

    write_srt(
        txt_lines, txt_word_spans, word_timings,
        block_starts, args.output,
        highlight_color=args.highlight_color,
        base_color=args.base_color
    )

if __name__ == '__main__':
    main()
