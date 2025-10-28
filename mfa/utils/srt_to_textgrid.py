#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import datetime as dt
import re
from pathlib import Path
import srt
import soundfile as sf

from praatio.data_classes.textgrid import Textgrid
from praatio.data_classes.interval_tier import IntervalTier

# ---------- утилиты ----------
def td2s(td: dt.timedelta) -> float:
    return td.total_seconds()

def audio_duration_sec(wav: Path | None) -> float | None:
    if not wav:
        return None
    data, sr = sf.read(str(wav), always_2d=False)
    n = len(data) if hasattr(data, "__len__") else data.shape[0]
    return float(n) / float(sr)

SPK_RE = re.compile(
    r'^\s*(?:\[(?P<spk1>[^\]\:]{1,50})\]\s*|(?P<spk2>[^:\-–]{1,50})\s*[:\-–]\s*)(?P<txt>.+)$',
    flags=re.IGNORECASE | re.UNICODE,
)

def parse_speaker(text: str):
    """
    Возвращает (speaker, clean_text) если удалось вытащить префикс,
    иначе (None, original_text).
    """
    m = SPK_RE.match(text.strip())
    if not m:
        return None, text.strip()
    spk = (m.group("spk1") or m.group("spk2") or "").strip()
    txt = m.group("txt").strip()
    return spk, txt

def build_tier_entries_for_speaker(subs, xmax: float, spk_name: str):
    """
    Из списка субтитров, принадлежащих одному спикеру,
    делает неперекрывающиеся интервалы + заполняет пустоты "".
    """
    # Сортируем по времени на всякий случай
    items = sorted([(td2s(s.start), td2s(s.end), s.content.strip()) for s in subs], key=lambda x: (x[0], x[1]))
    entries = []
    cursor = 0.0
    for start, end, text in items:
        if start > cursor:
            entries.append((cursor, start, ""))           # тишина
        if end == start:
            end = start + 0.01                            # защита от нулевой длины
        entries.append((start, end, text))
        cursor = end
    if cursor < xmax:
        entries.append((cursor, xmax, ""))                # хвост тишины
    return entries

# ---------- основная логика ----------
def srt_to_textgrid(
    srt_path: Path,
    out_path: Path,
    wav_path: Path | None,
    mode: str,
    tier_name: str,
    speakers_whitelist: set[str] | None,
    default_tier: str,
    long_format: bool,
):
    srt_text = srt_path.read_text(encoding="utf-8")
    subs = list(srt.parse(srt_text))
    if not subs:
        raise ValueError("SRT пуст или не распознан.")

    # xmax = длительность аудио (если задано), иначе конец последней реплики
    last_end = td2s(subs[-1].end)
    dur = audio_duration_sec(wav_path)
    xmax = dur if (dur and dur > last_end) else last_end

    # Раскладываем по спикерам
    by_speaker: dict[str, list[srt.Subtitle]] = {}

    if mode == "single":
        by_speaker[tier_name] = subs
    else:  # mode == "parse"
        wl = {s.strip() for s in (speakers_whitelist or set()) if s.strip()}
        for sub in subs:
            spk, txt = parse_speaker(sub.content)
            if spk is None or (wl and spk not in wl):
                # спикер не указан или не в белом списке — кидаем в дефолт
                spk = default_tier
                clean = sub.content.strip()
            else:
                clean = txt
            sub = srt.Subtitle(index=sub.index, start=sub.start, end=sub.end, content=clean)
            by_speaker.setdefault(spk, []).append(sub)

    # Собираем Textgrid
    tg = Textgrid(0.0, xmax)  # конструктор praatio: minTimestamp, maxTimestamp

    for spk_name, spk_subs in by_speaker.items():
        entries = build_tier_entries_for_speaker(spk_subs, xmax, spk_name)
        tier = IntervalTier(spk_name, entries, 0.0, xmax)
        tg.addTier(tier)

    tg.save(
        str(out_path),
        format=("long_textgrid" if long_format else "short_textgrid"),
        includeBlankSpaces=True,
    )
    return xmax, list(by_speaker.keys())

# ---------- CLI ----------
def main():
    ap = argparse.ArgumentParser(description="Convert .srt (1 или несколько спикеров) → Praat .TextGrid для MFA")
    ap.add_argument("srt", type=Path, help="Путь к входному .srt")
    ap.add_argument("--wav", type=Path, default=None, help="Опционально: исходный .wav (xmax = длительность аудио)")
    ap.add_argument("--out", type=Path, default=None, help="Путь к .TextGrid (по умолчанию basename SRT)")
    ap.add_argument("--mode", choices=["single", "parse"], default="single",
                    help="single: один tier (один спикер); parse: спикер из префикса строки")
    ap.add_argument("--tier", type=str, default="SPK1", help="Имя tier для режима single")
    ap.add_argument("--speakers", type=str, default=None,
                    help="Белый список имён спикеров (через запятую) для parse-режима")
    ap.add_argument("--default_tier", type=str, default="SPK1",
                    help="Куда складывать строки без префикса/не из белого списка (parse-режим)")
    ap.add_argument("--long", action="store_true", help="Сохранить в long_textgrid (по умолчанию short_textgrid)")
    args = ap.parse_args()

    out_path = args.out if args.out else args.srt.with_suffix(".TextGrid")
    speakers_whitelist = set(args.speakers.split(",")) if args.speakers else None

    xmax, tiers = srt_to_textgrid(
        srt_path=args.srt,
        out_path=out_path,
        wav_path=args.wav,
        mode=args.mode,
        tier_name=args.tier,
        speakers_whitelist=speakers_whitelist,
        default_tier=args.default_tier,
        long_format=args.long,
    )
    print(f"Saved: {out_path}  xmax={xmax:.3f}s  tiers={tiers}")

if __name__ == "__main__":
    main()
