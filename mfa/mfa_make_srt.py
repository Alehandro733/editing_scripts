#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для генерации SRT‑субтитров c подсветкой караоке
(принимает на вход TXT или SRT + JSON‑тайминги из MFA)

v14 – рефакторинг parse_srt и parse_txt: общая функция tokenize_lines убирает дублирование,
       сохраняется логика сбора block_starts для SRT.
"""

import argparse
import json
import string
import re
import sys
from pathlib import Path
from typing import List, Tuple, Optional

# ---------------------------------------------------------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# ФОРМАТИРОВАНИЕ ВРЕМЕНИ
# ---------------------------------------------------------------------------

def format_timestamp(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    hours, rem_ms = divmod(total_ms, 3600 * 1000)
    minutes, rem_ms = divmod(rem_ms, 60 * 1000)
    secs, millis = divmod(rem_ms, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

def parse_timestamp(timestamp_str: str) -> float:
    """'HH:MM:SS,mmm'  ->  секунды (float)"""
    time_part, millis_part = timestamp_str.strip().split(',')
    hours, minutes, seconds = map(int, time_part.split(':'))
    return hours * 3600 + minutes * 60 + seconds + int(millis_part) / 1000.0


def normalize_token(token: str) -> str:
    specials = {"<eps>", "<unk>"}
    if token in specials:
        return token
    token = (
        token.replace('’', "'")
             .replace('‘', "'")
             .replace('“', '"')
             .replace('”', '"')
             .lower()
             .strip(string.punctuation.replace("'", "").replace("-", ""))
    )
    return token


def remove_tags(text: str) -> str:
    """Удаляет любые HTML/XML‑теги"""
    return re.sub(r'<[^>]+>', '', text)

# ---------------------------------------------------------------------------
# ПАРСИНГ JSON ТАЙМИНГОВ
# ---------------------------------------------------------------------------
def parse_json(json_path: str) -> List[dict]:
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    entries = data['tiers']['words']['entries']
    json_entries = []
    for start, end, label in entries:
        if label == '<eps>':
            continue  # удаляем <eps> вместе с таймингами
        json_entries.append({
            'raw_label': label,
            'normalized_word': normalize_token(label),
            'start_time': start,
            'end_time': end
        })
    return json_entries

# ---------------------------------------------------------------------------
# ОБЩАЯ ФУНКЦИЯ ТОКЕНИЗАЦИИ
# ---------------------------------------------------------------------------

def tokenize_lines(lines: List[str]) -> Tuple[List[str], List[Tuple[int, int, int]]]:
    """
    Превращает список строк в плоский список нормализованных токенов и их спанов.
    Возвращает (words_norm, word_spans), где word_spans — список кортежей (линия, start, end).
    words_norm и word_spans это по сути одни и те же слова, но представленные в разном виде. Количество индексов - одинаково
    

    """
    token_re = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿœŒ0-9'’\-]+")
    words_norm: List[str] = []
    word_spans: List[Tuple[int, int, int]] = []
    for li, line in enumerate(lines):
        norm_line = line.replace('’', "'")
        for m in token_re.finditer(norm_line):
            tok = m.group(0)
            words_norm.append(normalize_token(tok))
            word_spans.append((li, m.start(), m.end()))
    return words_norm, word_spans

# ---------------------------------------------------------------------------
# ПАРСИНГ ВХОДНОГО ТЕКСТА (SRT / TXT)
# ---------------------------------------------------------------------------

def parse_srt(srt_path: str):
    """
    Важно - время из HH:MM:SS,mmm' конвертируется в секунды (float)
    """

    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    blocks = [b.strip() for b in content.split('\n\n') if b.strip()]
    lines: List[str] = []
    block_starts: List[float] = []

    for block in blocks:
        parts = block.split('\n')
        if len(parts) < 3 or '-->' not in parts[1]:
            continue
        start_ts, _ = parts[1].split('-->', 1)
        block_starts.append(parse_timestamp(start_ts))
        text = ' '.join(ln.strip() for ln in parts[2:])
        lines.append(remove_tags(text))

    words_norm, word_spans = tokenize_lines(lines)
    return lines, words_norm, word_spans, block_starts


def parse_txt(txt_path: str):
    with open(txt_path, 'r', encoding='utf-8') as f:
        lines = [ln.rstrip() for ln in f if ln.strip()]

    words_norm, word_spans = tokenize_lines(lines)
    return lines, words_norm, word_spans, None


def parse_input(path: str):
    return parse_srt(path) if path.lower().endswith('.srt') else parse_txt(path)

# ---------------------------------------------------------------------------
# НОВЫЙ АЛГОРИТМ ВЫРАВНИВАНИЯ (try_match / process)
# ---------------------------------------------------------------------------

def clean_word(w: str) -> str:
    return ''.join(ch for ch in w if ch.isalnum()).lower() if w else ''


def try_match(text: List[str], tok: List[str], i: int, j: int) -> Tuple[bool, Optional[int], Optional[int]]:
    if j >= len(tok):
        return False, None, None
    if tok[j] == '<unk>':
        return False, -1, -1

    word = clean_word(text[i])
    acc = ''
    jj = j
    used: List[int] = []

    while jj < len(tok) and len(acc) < len(word):
        part_tok = tok[jj]
        if part_tok == '<unk>':
            return False, None, j
        nxt = acc + clean_word(part_tok)
        if not word.startswith(nxt):
            return False, None, j
        used.append(jj)
        acc, jj = nxt, jj + 1
        if acc == word:
            return True, used[0], used[-1]

    return False, None, j


def handle_tok(text: List[str], tok: List[str], i: int, j: int, *, max_skip: int = 2) -> Tuple[bool, Optional[List[Tuple[int, Optional[int], Optional[int]]]]]:
    ok, st, ed = try_match(text, tok, i, j)
    if ok:
        return True, [(i, st, ed)]
    if st == -1 and ed == -1:
        return handle_unk(text, tok, i, j)

    def shift_token(offset: int):
        nj = j + offset
        if nj < len(tok) and tok[nj] != '<unk>':
            ok2, st2, ed2 = try_match(text, tok, i, nj)
            return [(i, st2, ed2)] if ok2 else None
    def shift_text(offset: int):
        ni = i + offset
        if ni < len(text):
            ok2, st2, ed2 = try_match(text, tok, ni, j)
            if ok2:
                return [(i + k, st2, ed2) for k in range(offset)] + [(ni, st2, ed2)]

    for off in range(1, max_skip + 1):
        blk = shift_token(off) or shift_text(off)
        if blk:
            return True, blk

    return False, None


def handle_unk(text: List[str], tok: List[str], i: int, j: int, *, allow_skip: bool = True) -> Tuple[bool, Optional[List[Tuple[int, Optional[int], Optional[int]]]]]:
    if allow_skip:
        k = j
        while k < len(tok) and tok[k] == '<unk>':
            k += 1
        if k < len(tok):
            ok, _, _ = try_match(text, tok, i, k)
            if ok and (len(tok) - k) >= (len(text) - i):
                return handle_tok(text, tok, i, k)

    block: List[Tuple[int, Optional[int], Optional[int]]] = []
    cur_i, cur_j = i, j

    while cur_j < len(tok) and tok[cur_j] == '<unk>':
        nxt = cur_j + 1
        while nxt < len(tok) and tok[nxt] == '<unk>':
            nxt += 1
        if nxt < len(tok):
            ok, _, _ = try_match(text, tok, cur_i, nxt)
            if ok and (allow_skip or block):
                ok2, tail = handle_tok(text, tok, cur_i, nxt)
                if ok2 and tail:
                    block.extend(tail)
                    return True, block
        block.append((cur_i, cur_j, cur_j))
        cur_i += 1
        cur_j += 1
        if cur_i >= len(text):
            return False, None

    if cur_j >= len(tok):
        return False, None
    ok, tail = handle_tok(text, tok, cur_i, cur_j)
    if ok and tail:
        block.extend(tail)
        return True, block
    return False, None


def process(text: List[str], tok: List[str], idx: List[int]) -> List[Tuple[Optional[int], Optional[int]]]:
    res: List[Tuple[Optional[int], Optional[int]]] = [(None, None)] * len(text)
    """
    получает список слов из parse_srt/txt (text) и список слов-токенов из json (tok). 
    Находит соответсвия и выдаёт диапазон, который занимает каждое слово из text в tok
    """

    i = j = 0
    while i < len(text):
        if j >= len(tok):
            sys.exit(f"[ERROR] JSON‑токены закончились на слове #{i}: '{text[i]}'")
        handler = handle_unk if tok[j] == '<unk>' else handle_tok
        ok, block = handler(text, tok, i, j)
        if not ok or block is None:
            sys.exit(f"[ERROR] Не удалось сопоставить слово #{i} '{text[i]}' / токен #{j} '{tok[j]}'")
        for ti, sj, ej in block:
            if sj is None:
                res[ti] = (None, None)
            else:
                res[ti] = (idx[sj], idx[ej])
        i = max(ti for ti, _, _ in block) + 1
        j = max(v for _, sj, ej in block for v in (sj, ej) if v is not None) + 1
    return res

# ---------------------------------------------------------------------------
# ГЕНЕРАЦИЯ SRT С ДВУМЯ ЦВЕТАМИ
# ---------------------------------------------------------------------------

def write_srt(lines, spans, timings,
              starts: Optional[List[float]],
              output_path: str,
              highlight_color: str,
              base_color: str) -> None:
    # ------------------------------------------------------------------ #
    # 1. «Сырые» сегменты                                                #
    # ------------------------------------------------------------------ #
    def build_segments():
        lines2words = {}
        for wi, (li, si, ei) in enumerate(spans):
            lines2words.setdefault(li, []).append((wi, si, ei))

        segs = []
        for li, words in lines2words.items():
            n = len(words)
            for pos, (wi, si, ei) in enumerate(words):
                # точка окончания подсветки:
                #  – начало след. слова (trim-позже)        – если есть след. слово
                #  – конец строки                           – если слова последнее
                if pos < n - 1:
                    seg_end = words[pos + 1][1]        # start of next word
                else:
                    seg_end = len(lines[li])

                segs.append({
                    'idx'        : len(segs) + 1,
                    'li'         : li,
                    'start_time' : starts[li] if (pos == 0 and starts)
                                               else timings[wi][0],
                    'end_raw'    : (timings[words[pos + 1][0]][0]
                                    if pos < n - 1
                                    else timings[wi][1]),
                    'seg_start'  : si,
                    'seg_end'    : seg_end,
                    'is_last'    : (pos == n - 1)
                })
        return segs

    # ------------------------------------------------------------------ #
    # 2. HTML-построитель с “умной” границей                             #
    # ------------------------------------------------------------------ #
    def html_span(text: str, start: int, end: int, *, is_last: bool) -> str:
        """
        • сдвигает `start` влево, если перед словом “прилипшие” знаки;
        • убирает лишние пробелы справа, если сегмент НЕ последний в строке;
        """
        # 2a. захватываем символы прямо перед словом (пока не пробел)
        while start > 0 and not text[start - 1].isspace() \
                       and not text[start - 1].isalnum():
            start -= 1                       # например, «"слово»

        # 2b. для НЕ-последнего слова убираем пробел(ы) справа
        if not is_last:
            while end > start and text[end - 1].isspace():
                end -= 1                     # “Слово,” ← без пробела

        pre, sel, suf = text[:start], text[start:end], text[end:]

        html = ''
        if pre:
            html += f'<font color="#{base_color}">{pre}</font>'
        html += f'<font color="#{highlight_color}">{sel}</font>'
        if suf:
            html += f'<font color="#{base_color}">{suf}</font>'
        return html

    # ------------------------------------------------------------------ #
    # 3. Исправляем интервалы start > end (склейка)                      #
    # ------------------------------------------------------------------ #
    def fix_intervals(raw):
        fixed, i = [], 0
        while i < len(raw):
            cur = raw[i]
            if cur['start_time'] <= cur['end_raw']:
                fixed.append(cur)
                i += 1
                continue

            # --- ищем, на чьём end остановиться (до +5) ---
            j = None
            for look in range(i + 1, min(i + 6, len(raw))):
                if raw[look]['end_raw'] >= cur['start_time']:
                    j = look
                    break
            if j is None:                    # совсем плохо? – сплющиваем
                cur['end_raw'] = cur['start_time']
                fixed.append(cur)
                i += 1
                continue

            group = raw[i:j + 1]
            first, last = group[0], group[-1]

            # 3a. всё в одной строке ➜ просто расширяем диапазон
            if all(g['li'] == first['li'] for g in group):
                li = first['li']
                text = lines[li]
                new_html = html_span(
                    text,
                    first['seg_start'],
                    last['seg_end'],
                    is_last=last['is_last']
                )
                fixed.append({
                    'idx'        : first['idx'],
                    'start_time' : first['start_time'],
                    'end_raw'    : last['end_raw'],
                    'text_html'  : new_html
                })
            # 3b. «одиночное» слово-строка ➜ физическое слияние строк
            else:
                lines_block = [lines[g['li']] for g in group
                               if g is group[0] or g['li'] != group[0]['li']]
                combo = ' '.join(lines_block)
                offset = len(lines[group[0]['li']]) + 1   # +1 за пробел
                span_start = first['seg_start']
                span_end   = offset + group[-1]['seg_end']
                new_html   = html_span(combo, span_start, span_end, is_last=True)

                fixed.append({
                    'idx'        : first['idx'],
                    'start_time' : first['start_time'],
                    'end_raw'    : last['end_raw'],
                    'text_html'  : new_html
                })
            i = j + 1

        # синхронизируем «концы» с «началами» следующих
        for k in range(len(fixed) - 1):
            fixed[k]['end_raw'] = fixed[k + 1]['start_time']
        return fixed

    # ------------------------------------------------------------------ #
    # 4. Записываем файл                                                 #
    # ------------------------------------------------------------------ #
    def dump(segs):
        with open(output_path, 'w', encoding='utf-8') as f:
            for new_idx, seg in enumerate(segs, 1):
                f.write(f"{new_idx}\n")
                f.write(f"{format_timestamp(seg['start_time'])} --> "
                        f"{format_timestamp(seg['end_raw'])}\n")

                html = seg.get('text_html')
                if html is None:
                    # «нормальный» сегмент – строим HTML здесь
                    li = seg['li']
                    html = html_span(
                        lines[li],
                        seg['seg_start'],
                        seg['seg_end'],
                        is_last=seg['is_last']
                    )
                f.write(html + '\n\n')
        print(f"SRT файл создан: {output_path}")

    # ---- pipeline ----
    raw   = build_segments()
    good  = fix_intervals(raw)
    dump(good)




# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Генерация караоке‑SRT")
    ap.add_argument('-j', '--json', required=True, help="JSON c таймингами")
    ap.add_argument('-t', '--text', required=True, help="TXT или SRT‑транскрипт")
    ap.add_argument('-o', '--output', required=True, help="выходной SRT")
    ap.add_argument('-c', '--highlight-color', dest='highlight_color', default='2DE471',
                   help="цвет выделения (6 hex-цифр без '#'), пример: 2DE471")
    ap.add_argument('-b', '--base-color', dest='base_color', default='FFFFFF',
                   help="цвет основного текста (6 hex-цифр без '#'), пример: FFFFFF")
    args = ap.parse_args()
    # проверка кодов
    for val, name in ((args.highlight_color, 'highlight_color'), (args.base_color, 'base_color')):
        if not re.fullmatch(r'[0-9A-Fa-f]{6}', val):
            sys.exit(f"Неверный код `{name}`: '{val}'. Ожидается 6 hex-символов без '#'.")

    json_entries = parse_json(args.json)
    lines, txt_words, spans, starts = parse_input(args.text)
    # prepare tokens and indices
    toks = [e['normalized_word'] for e in json_entries]
    idxs = list(range(len(json_entries)))
    # align
    result = process(txt_words, toks, idxs)
    # convert to timings тут индексы таймингов конвертируются в конкретные значения времени
    timings = []
    for st, ed in result:
        if st is None or ed is None:
            sys.exit(f"[ERROR] Нет таймингов для слова с индексом: {st}")
        start_time = json_entries[st]['start_time']
        end_time = json_entries[ed]['end_time']
        timings.append((start_time, end_time))

    write_srt(lines, spans, timings, starts, args.output, args.highlight_color, args.base_color)

if __name__ == '__main__':
    main()
