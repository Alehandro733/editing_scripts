#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для генерации SRT-субтитров c подсветкой караоке
(принимает на вход TXT или SRT + JSON-тайминги из MFA)

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
    """Приводит токен к нижнему регистру, унифицирует кавычки и
    убирает пунктуацию (кроме апострофа и дефиса внутри слова)."""
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
    """Удаляет любые HTML/XML-теги"""
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
    Возвращает (words_norm, word_spans), где word_spans — список кортежей
    (номер_строки, start, end). Количество элементов в обоих списках одинаковое.
    """
    # Буквы/цифры/апостроф, + опц. группы «-<буквы/цифры…>».
    token_re = re.compile(
        r"[A-Za-zÀ-ÖØ-öø-ÿœŒ0-9'’]+(?:-[A-Za-zÀ-ÖØ-öø-ÿœŒ0-9'’]+)*"
    )

    words_norm: List[str] = []
    word_spans: List[Tuple[int, int, int]] = []

    for li, line in enumerate(lines):
        norm_line = line.replace('’', "'")          # единый апостроф
        for m in token_re.finditer(norm_line):
            tok = m.group(0)
            norm_tok = normalize_token(tok)

            if not norm_tok:                       # одиночный «-» → ''
                continue                           # пропускаем «слово»-дефис

            words_norm.append(norm_tok)
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
            sys.exit(f"[ERROR] Ran out of JSON tokens at word #{i}: '{text[i]}'")
        handler = handle_unk if tok[j] == '<unk>' else handle_tok
        ok, block = handler(text, tok, i, j)
        if not ok or block is None:
            sys.exit(f"[ERROR] Failed to align word #{i} '{text[i]}' with token #{j} '{tok[j]}'")
        for ti, sj, ej in block:
            if sj is None:
                res[ti] = (None, None)
            else:
                res[ti] = (idx[sj], idx[ej])
        i = max(ti for ti, _, _ in block) + 1
        j = max(v for _, sj, ej in block for v in (sj, ej) if v is not None) + 1
    return res

# ---------------------------------------------------------------------------
# ГЕНЕРАЦИЯ SRT С ДВУМЯ ЦВЕТАМИ (обновлено)
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
        # гарантируем порядок строк
        for li in sorted(lines2words.keys()):
            words = lines2words[li]
            n = len(words)
            for pos, (wi, si, ei) in enumerate(words):
                # символная граница подсветки
                if pos < n - 1:
                    seg_end = words[pos + 1][1]                  # start of next word (символьный индекс)
                    end_raw = timings[words[pos + 1][0]][0]      # ВРЕМЯ: старт след. слова
                else:
                    seg_end = len(lines[li])
                    end_raw = timings[wi][1]                     # ВРЕМЯ: конец текущего слова

                # старт по времени
                start_time = starts[li] if (pos == 0 and starts) else timings[wi][0]

                # ЛОКАЛЬНЫЙ ПРЕДОХРАНИТЕЛЬ: не даём сегменту инвертироваться
                if end_raw < start_time:
                    end_raw = start_time

                segs.append({
                    'idx'        : len(segs) + 1,
                    'li'         : li,
                    'start_time' : start_time,
                    'end_raw'    : end_raw,
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
            if j is None:                    # совсем плохо? – сплющиваем в ноль
                cur = dict(cur)
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
                    'end_raw'    : max(last['end_raw'], first['start_time']),
                    'text_html'  : new_html,
                    'li'         : li,
                })
            # 3b. мультистрочная группа ➜ аккуратная склейка строк
            else:
                li_seq = []
                for g in group:
                    if g['li'] not in li_seq:
                        li_seq.append(g['li'])

                pieces = [lines[li] for li in li_seq]
                combo_text = ' '.join(pieces)
                offsets = {li_seq[0]: 0}
                for k in range(1, len(li_seq)):
                    prev_li = li_seq[k - 1]
                    offsets[li_seq[k]] = offsets[prev_li] + len(lines[prev_li]) + 1  # +1 за пробел

                span_start = offsets[first['li']] + first['seg_start']
                span_end   = offsets[last['li']]  + last['seg_end']
                new_html   = html_span(combo_text, span_start, span_end, is_last=True)

                fixed.append({
                    'idx'        : first['idx'],
                    'start_time' : first['start_time'],
                    'end_raw'    : max(last['end_raw'], first['start_time']),
                    'text_html'  : new_html,
                    'li'         : first['li'],
                })
            i = j + 1

        # 🔁 СИНХРОНИЗАЦИЯ КОНЦОВ: безусловно растягиваем к следующему старту
        for k in range(len(fixed) - 1):
            next_start = fixed[k + 1]['start_time']
            # растянуть до следующего старта, но не левее собственного старта
            fixed[k]['end_raw'] = max(next_start, fixed[k]['start_time'])

        # страховка для последнего сегмента
        if fixed:
            last = fixed[-1]
            if last['end_raw'] < last['start_time']:
                last['end_raw'] = last['start_time']

        return fixed

    def resolve_block_conflicts(segs, *, lines, spans, timings, eps_lines=None, max_neighbor_shift=0.2):
        """
        Пост-правка по блокам (строкам SRT), устраняет перекрытия/лестницы по приоритетам:
          1) если конфликтующий блок помечен eps_lines -> позволяем наезжать на него;
          2) иначе пытаемся разрезать перекрытие пополам (mid-cut);
          3) если блок схлопнут/инвертирован -> растягиваем его и соседей, но не более 0.2s;
          4) если не получилось -> берём JSON-рамки блока и стыкуем без дыр.
        segs: список сегментов из build_segments() (каждый — “событие” для плеера).
        eps_lines: set индексов строк (li), которые можно безболезненно «давить» (по умолчанию пусто).
        """

        eps_lines = set(eps_lines or [])

        # ----- построим мету для блоков -----
        #  line_bounds_json[li] = (json_start, json_end) по токенам этой строки
        from collections import defaultdict

        line_words = defaultdict(list)  # li -> список индексов слов (wi)
        for wi, (li, _si, _ei) in enumerate(spans):
            line_words[li].append(wi)

        line_bounds_json = {}
        for li, wis in line_words.items():
            js = timings[wis[0]][0]
            je = timings[wis[-1]][1]
            # корректность на всякий случай
            if je < js:
                je = js
            line_bounds_json[li] = (js, je)

        # blocks: последовательные группы segs по li
        blocks = []
        i = 0
        while i < len(segs):
            li = segs[i]['li']
            j = i
            while j < len(segs) and segs[j]['li'] == li:
                j += 1
            idxs = list(range(i, j))
            b_start = segs[idxs[0]]['start_time']
            b_end   = segs[idxs[-1]]['end_raw']
            js, je  = line_bounds_json.get(li, (b_start, b_end))
            blocks.append({
                'li': li,
                'idxs': idxs,
                'start': b_start,
                'end': b_end,
                'json_start': js,
                'json_end': je,
            })
            i = j

        def _shift_block(b, delta):
            if abs(delta) < 1e-9:
                return
            for si in b['idxs']:
                segs[si]['start_time'] += delta
                segs[si]['end_raw']    += delta
            b['start'] += delta
            b['end']   += delta

        def _trim_block_end_to(b, new_end):
            # подрезаем КОНЕЦ блока (последний сегмент)
            last = segs[b['idxs'][-1]]
            if new_end < last['start_time']:
                # нельзя подрезать раньше старта последнего сегмента — сведём в ноль
                new_end = last['start_time']
            last['end_raw'] = new_end
            b['end'] = new_end

        def _set_block_start_to(b, new_start):
            delta = new_start - b['start']
            _shift_block(b, delta)

        def _set_block_end_to(b, new_end):
            _trim_block_end_to(b, new_end)

        # ----- 1) устранение перекрытий соседних блоков (mid-cut либо сдвиг следующего) -----
        # несколько итераций на случай каскадных конфликтов
        changed = True
        iters = 0
        while changed and iters < 3:
            changed = False
            iters += 1
            for k in range(1, len(blocks)):
                A = blocks[k - 1]
                B = blocks[k]
                if B['start'] < A['end'] - 1e-9:
                    # если B — «eps-блок», позволяем наезжать (сдвигаем B к концу A)
                    if B['li'] in eps_lines:
                        _set_block_start_to(B, A['end'])
                        changed = True
                        continue

                    # пробуем разрез по середине перекрытия
                    cut = 0.5 * (A['end'] + B['start'])
                    # можно ли подрезать A до cut?
                    lastA = segs[A['idxs'][-1]]
                    if cut >= lastA['start_time'] - 1e-9:
                        _trim_block_end_to(A, cut)
                        _set_block_start_to(B, cut)
                        changed = True
                    else:
                        # mid-cut невозможен — двигаем весь B к концу A
                        _set_block_start_to(B, A['end'])
                        changed = True

        # ----- 2) обработка схлопнутых/инвертированных блоков -----
        for k, B in enumerate(blocks):
            if B['end'] >= B['start'] - 1e-9:
                continue  # ок
            # попробуем выделить окно, двигая соседей не более чем на 0.2s
            A = blocks[k - 1] if k > 0 else None
            C = blocks[k + 1] if k + 1 < len(blocks) else None

            target_len = 0.08  # минимальная длительность, чтобы хоть что-то мигнуло
            # старт хотим поставить не раньше конца A минус 0.2
            if A:
                new_start = max(A['end'] - max_neighbor_shift, A['end'])
            else:
                new_start = B['start']  # без левого соседа — оставим как есть

            if C:
                new_end = min(C['start'] + max_neighbor_shift, C['start'])
            else:
                new_end = B['end']

            if new_end < new_start + target_len:
                # не хватает места -> растянем симметрично в доступных пределах
                extra = target_len - (new_end - new_start)
                # попробуем забрать по половине с каждой стороны
                take_left  = min(max_neighbor_shift, extra / 2) if A else 0.0
                take_right = min(max_neighbor_shift, extra / 2) if C else 0.0
                new_start -= take_left
                new_end   += take_right
                # защита от заходов
                if A and new_start < A['start']:
                    new_start = A['start']
                if C and new_end > C['end']:
                    new_end = C['end']

            if new_end < new_start:
                # не получилось — упадём на JSON-рамки (ниже)
                pass
            else:
                # применим
                _set_block_start_to(B, new_start)
                _set_block_end_to(B, new_end)
                if A:
                    _set_block_end_to(A, new_start)
                if C:
                    _set_block_start_to(C, new_end)
                continue  # готово

            # ----- 3) fallback: JSON-рамки + стык без дыр -----
            js, je = B['json_start'], B['json_end']
            if je < js:
                je = js
            _set_block_start_to(B, js)
            _set_block_end_to(B, je)
            if A:
                _set_block_end_to(A, js)
            if C:
                _set_block_start_to(C, je)

        return segs

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
        print(f"SRT file created: {output_path}")

    # ---- pipeline ----
    raw   = build_segments()

        # НОВЫЙ ШАГ: устраняем редкие конфликтные «лестницы» между строками
    raw = resolve_block_conflicts(
        raw,
        lines=lines,
        spans=spans,
        timings=timings,
        eps_lines=None,          # или set([...]) если знаешь «eps-строки»
        max_neighbor_shift=0.2   # не двигаем соседей больше 0.2s с каждой стороны
    )
    
    good  = fix_intervals(raw)
    dump(good)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Generate karaoke-style SRT")
    ap.add_argument('-j', '--json', required=True, help="JSON with timings")
    ap.add_argument('-t', '--text', required=True, help="TXT or SRT transcript")
    ap.add_argument('-o', '--output', required=True, help="output SRT path")
    ap.add_argument('-c', '--highlight-color', dest='highlight_color', default='2DE471',
                   help="highlight color (6 hex digits without '#'), e.g. 2DE471")
    ap.add_argument('-b', '--base-color', dest='base_color', default='FFFFFF',
                   help="base text color (6 hex digits without '#'), e.g. FFFFFF")
    args = ap.parse_args()
    # проверка кодов
    for val, name in ((args.highlight_color, 'highlight_color'), (args.base_color, 'base_color')):
        if not re.fullmatch(r'[0-9A-Fa-f]{6}', val):
            sys.exit(f"Invalid `{name}`: '{val}'. Expected 6 hex characters without '#'.")

    json_entries = parse_json(args.json)
    lines, txt_words, spans, starts = parse_input(args.text)
    # prepare tokens and indices
    toks = [e['normalized_word'] for e in json_entries]
    idxs = list(range(len(json_entries)))
    # align
    result = process(txt_words, toks, idxs)

    # convert to timings (с защитой от инверсии)
    timings = []
    for st, ed in result:
        if st is None or ed is None:
            sys.exit(f"[ERROR] No timings for word index: {st}")
        start_time = json_entries[st]['start_time']
        end_time   = json_entries[ed]['end_time']

        # страховка от инверсии токенов/таймингов
        if end_time < start_time:
            # при необходимости можно логировать предупреждение
            # print(f"[WARN] Inverted token times: st={st}, ed={ed}, {start_time} > {end_time}")
            end_time = start_time

        timings.append((start_time, end_time))

    write_srt(lines, spans, timings, starts, args.output, args.highlight_color, args.base_color)

if __name__ == '__main__':
    main()
