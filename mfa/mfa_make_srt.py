#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для генерации SRT субтитров с караоке-эффектом (поддержка TXT и SRT на входе)
"""
import argparse
import json
import string
import re
import sys
from pathlib import Path
from datetime import timedelta

def parse_timestamp(timestamp_str: str) -> float:
    """Парсит строку времени в формате SRT в секунды"""
    time_part, millis_part = timestamp_str.strip().split(',')
    hours, minutes, seconds = time_part.split(':')
    total_seconds = int(hours)*3600 + int(minutes)*60 + int(seconds) + int(millis_part)/1000.0
    return total_seconds

def normalize_token(token: str) -> str:
    specials = {"<eps>", "<unk>"}
    if token in specials:
        return token
    token = token.replace('’', "'").replace('‘', "'")
    token = token.replace('“', '"').replace('”', '"')
    token = token.lower().strip(string.punctuation.replace("'", "").replace("-", ""))
    return token

def remove_tags(text: str) -> str:
    """Удаляет все HTML/XML теги из текста"""
    return re.sub(r'<[^>]+>', '', text)

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
    json_entries_filtered = [e.copy() for e in json_entries_raw if e['raw_label'] != '<eps>']
    return json_entries_raw, json_entries_filtered

def parse_srt(srt_path: str):
    """Парсит SRT файл, возвращает строки, тайминги блоков, слова и их позиции"""
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    blocks = [b.strip() for b in content.split('\n\n') if b.strip()]
    lines = []
    block_starts = []
    token_pattern = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿœŒ'’\-]+")
    txt_words_normalized = []
    txt_word_spans = []

    for block in blocks:
        lines_in_block = block.split('\n')
        if len(lines_in_block) < 3:
            continue
            
        # Парсим тайминг
        timing_line = lines_in_block[1].strip()
        if '-->' not in timing_line:
            continue
            
        start_ts, _ = timing_line.split('-->', 1)
        start_seconds = parse_timestamp(start_ts)
        block_starts.append(start_seconds)
        
        # Объединяем текст блока и удаляем теги
        text = ' '.join(ln.strip() for ln in lines_in_block[2:])
        clean_text = remove_tags(text)
        lines.append(clean_text)
        
        # Обрабатываем слова
        norm_line = clean_text.replace('’', "'")
        for m in token_pattern.finditer(norm_line):
            tok = m.group(0)
            txt_words_normalized.append(normalize_token(tok))
            txt_word_spans.append((len(lines)-1, m.start(), m.end()))
    
    return lines, txt_words_normalized, txt_word_spans, block_starts

def parse_txt(txt_path: str):
    """Парсит обычный текстовый файл"""
    with open(txt_path, 'r', encoding='utf-8') as f:
        lines = [ln.rstrip() for ln in f if ln.strip()]
    
    token_pattern = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿœŒ'’\-]+")
    txt_words_normalized = []
    txt_word_spans = []
    for li, line in enumerate(lines):
        norm_line = line.replace('’', "'")
        for m in token_pattern.finditer(norm_line):
            tok = m.group(0)
            txt_words_normalized.append(normalize_token(tok))
            txt_word_spans.append((li, m.start(), m.end()))
    
    return lines, txt_words_normalized, txt_word_spans, None

def parse_input(input_path: str):
    """Определяет тип файла и вызывает соответствующий парсер"""
    if input_path.lower().endswith('.srt'):
        return parse_srt(input_path)
    else:
        return parse_txt(input_path)

def match_one(txt_idx, json_idx, txt_words, json_entries_filtered, json_entries_raw, ratio_threshold=0.7):
    if json_idx >= len(json_entries_filtered):
        return False, json_idx, None, None, "error: no more entries", txt_idx
    
    txt_word = txt_words[txt_idx]
    json_entry = json_entries_filtered[json_idx]
    json_word = json_entry['normalized_word']
    start_time = json_entry['start_time']
    end_time = json_entry['end_time']

    # 1. EPS-MISALIGN-FIX
    if (txt_idx+1 < len(txt_words)) and (json_word == txt_words[txt_idx+1]):
        if json_idx == 0:
            return False, json_idx, None, None, "error: cannot fix misalignment", txt_idx
        
        prev_json_entry = json_entries_filtered[json_idx-1]
        raw_idx = next((k for k, e in enumerate(json_entries_raw) 
                  if e['start_time'] == prev_json_entry['start_time'] and e['normalized_word'] == prev_json_entry['normalized_word']), None)
        
        if raw_idx is None or raw_idx == 0:
            return False, json_idx, None, None, "error: cannot fix misalignment", txt_idx
        
        prev_raw_entry = json_entries_raw[raw_idx-1]
        if prev_raw_entry['raw_label'] == "<eps>":
            fix_start = prev_raw_entry['start_time']
        else:
            fix_start = prev_raw_entry['end_time']
        
        return True, json_idx, fix_start, end_time, "eps-misalign-fix", txt_idx

    # 2. Normal matching
    if json_word == "<unk>":
        if json_idx+1 < len(json_entries_filtered) and txt_idx+1 < len(txt_words):
            next_txt_word = txt_words[txt_idx+1]
            next_json_word = json_entries_filtered[json_idx+1]['normalized_word']
            ok = (next_txt_word in next_json_word) or (next_json_word in next_txt_word)
        else:
            ok = False
    else:
        ratio = len(json_word) / len(txt_word) if txt_word else 0
        if ratio >= ratio_threshold and json_word in txt_word:
            ok = True
        else:
            idx0 = txt_word.find(json_word)
            ok = False
            if idx0 != -1:
                end_pos = idx0 + len(json_word)
                if end_pos < len(txt_word):
                    ptr = end_pos
                    while ptr < len(txt_word) and not txt_word[ptr].isalpha():
                        ptr += 1
                    if ptr == len(txt_word) or (ptr < len(txt_word) and txt_word[ptr].isalpha()):
                        ok = True
                else:
                    ok = True
                if not ok and idx0 > 0:
                    ptr = idx0 - 1
                    while ptr >= 0 and not txt_word[ptr].isalpha():
                        ptr -= 1
                    if ptr < 0 or (ptr >= 0 and txt_word[ptr].isalpha()):
                        ok = True

    if ok:
        return True, json_idx+1, start_time, end_time, "normal", txt_idx+1
    else:
        return False, json_idx+1, None, None, "error", txt_idx+1

def match_timings(txt_words, json_entries_filtered, json_entries_raw, log_path: Path):
    max_txt_word_len = max((len(w) for w in txt_words), default=4)
    max_json_word_len = max((len(e['normalized_word']) for e in json_entries_filtered), default=5)
    word_timings = []
    txt_idx = 0
    json_idx = 0
    n_words = len(txt_words)
    error_mode = False
    post_error_written = 0

    with open(log_path, 'w', encoding='utf-8') as log:
        log.write(f"{'TXT_WORD':<{max_txt_word_len}}  {'JSON_WORD':<{max_json_word_len}}  {'START':>6}  {'END':>6}  STATUS\n")
        log.write(f"{'-'*max_txt_word_len}  {'-'*max_json_word_len}  {'-'*6}  {'-'*6}  ------\n")

        while txt_idx < n_words:
            removed_count = 0
            while json_idx+1 < len(json_entries_filtered):
                next_json_word = json_entries_filtered[json_idx+1]['normalized_word']
                pattern = rf"(?:^|[-']){re.escape(next_json_word)}(?:$|[-'])"
                if re.search(pattern, txt_words[txt_idx]):
                    removed = json_entries_filtered.pop(json_idx+1)
                    log.write(f"{txt_words[txt_idx]:<{max_txt_word_len}}  {removed['normalized_word']:<{max_json_word_len}}  {'':>6}  {'':>6}  split-fix (removed)\n")
                    removed_count += 1
                else:
                    break

            ok, new_json_idx, start_time, end_time, action, new_txt_idx = match_one(
                txt_idx, json_idx, txt_words, json_entries_filtered, json_entries_raw
            )
            
            current_json_word = json_entries_filtered[json_idx]['normalized_word'] if json_idx < len(json_entries_filtered) else ''
            if ok and start_time is not None:
                if end_time is None:
                    end_time = json_entries_filtered[json_idx]['end_time']
                word_timings.append({
                    'start': start_time, 
                    'end': end_time
                })
                t_str_start = f"{start_time:>6.3f}"
                t_str_end = f"{end_time:>6.3f}"
            else:
                t_str_start = ' '*6
                t_str_end = ' '*6
            log.write(f"{txt_words[txt_idx]:<{max_txt_word_len}}  {current_json_word:<{max_json_word_len}}  {t_str_start}  {t_str_end}  {action}\n")

            if "error" in action:
                if not error_mode:
                    error_mode = True
                else:
                    post_error_written += 1
            elif error_mode:
                post_error_written += 1

            if error_mode and post_error_written >= 5:
                sys.exit(f"Прекращено после 1 ошибки и 5 пост-ошибочных строк.")

            txt_idx, json_idx = new_txt_idx, new_json_idx

    if len(word_timings) != n_words:
        sys.exit(f"Ошибка: сопоставлено {len(word_timings)} из {n_words} слов.")

    return word_timings

def format_timestamp(seconds: float) -> str:
    td = timedelta(seconds=seconds)
    hours, remainder = divmod(td.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = (seconds - int(seconds)) * 1000
    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02},{int(milliseconds):03}"

def write_srt(txt_lines, txt_word_spans, word_timings, block_starts, output_path):
    # Группируем слова по строкам
    lines_words = {}
    for idx, (li, si, ei) in enumerate(txt_word_spans):
        if li not in lines_words:
            lines_words[li] = []
        lines_words[li].append(idx)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        sub_idx = 1
        for li, line in enumerate(txt_lines):
            if li not in lines_words:
                continue
                
            word_indices = lines_words[li]
            n = len(word_indices)
            
            # Для каждого слова в строке создаем отдельный блок
            for i, word_idx in enumerate(word_indices):
                li_span, start_pos, end_pos = txt_word_spans[word_idx]
                assert li_span == li
                
                # Определяем границы сегмента для выделения
                if i == 0:
                    seg_start = 0  # Для первого слова в строке - с начала строки
                else:
                    seg_start = start_pos
                
                if i < n - 1:
                    next_start_pos = txt_word_spans[word_indices[i+1]][1]
                    seg_end = next_start_pos
                else:
                    seg_end = len(line)  # Для последнего слова - до конца строки
                
                # Формируем строку с выделением
                highlighted_line = (
                    line[:seg_start] +
                    '<font color=#2DE471FF>' +
                    line[seg_start:seg_end] +
                    '</font>' +
                    line[seg_end:]
                )
                
                # Рассчитываем тайминги
                if i == 0 and block_starts and li < len(block_starts):
                    start_time = block_starts[li]
                else:
                    start_time = word_timings[word_idx]['start']
                
                if i < n - 1:
                    end_time = word_timings[word_indices[i+1]]['start']
                else:
                    end_time = word_timings[word_idx]['end']
                
                # Записываем блок SRT
                f.write(f"{sub_idx}\n")
                f.write(f"{format_timestamp(start_time)} --> {format_timestamp(end_time)}\n")
                f.write(f"{highlighted_line}\n\n")
                sub_idx += 1

    print(f"SRT файл создан: {output_path}")

def main():
    parser = argparse.ArgumentParser(description='Генерация SRT субтитров с караоке-эффектом')
    parser.add_argument('-j','--json', required=True, help='JSON с таймингами')
    parser.add_argument('-t','--text', required=True, help='TXT или SRT транскрипт')
    parser.add_argument('-o','--output', required=True, help='SRT выход')
    args = parser.parse_args()

    json_entries_raw, json_entries_filtered = parse_json(args.json)
    txt_lines, txt_words_normalized, txt_word_spans, block_starts = parse_input(args.text)
    log_path = Path('log_split.txt')
    
    word_timings = match_timings(txt_words_normalized, json_entries_filtered, json_entries_raw, log_path)
    write_srt(txt_lines, txt_word_spans, word_timings, block_starts, args.output)

if __name__ == '__main__':
    main()