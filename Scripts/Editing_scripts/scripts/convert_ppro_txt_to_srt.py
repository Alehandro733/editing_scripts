import argparse
import os
import re

def parse_timecode(tc: str, fps: float) -> str:
    """
    Преобразует метку времени 'HH:MM:SS:FF' в 'HH:MM:SS,mmm',
    где FF — фреймы при заданном fps.
    """
    h, m, s, f = map(int, tc.split(':'))
    total_ms = (h * 3600 + m * 60 + s) * 1000 + round(f * 1000 / fps)
    hours, rem = divmod(total_ms, 3600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"

def convert_txt_to_srt(input_path: str, fps: float, output_path: str):
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()

    blocks = re.split(r'\r?\n\s*\r?\n', content)

    srt_lines = []
    idx = 1
    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if not lines or '-' not in lines[0]:
            continue

        start_tc, end_tc = [t.strip() for t in lines[0].split('-', 1)]
        start_ts = parse_timecode(start_tc, fps)
        end_ts   = parse_timecode(end_tc, fps)

        # Пропускаем необязательную строку "V7, 1"
        text_lines = lines[2:] if len(lines) >= 3 else lines[1:]
        text = '\n'.join(text_lines)

        srt_lines += [
            str(idx),
            f"{start_ts} --> {end_ts}",
            text,
            ""
        ]
        idx += 1

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(srt_lines))

def main():
    parser = argparse.ArgumentParser(
        description="Конвертация TXT (HH:MM:SS:FF) → SRT, учитывая FPS"
    )
    parser.add_argument("input_txt",
                        help="Путь к входному TXT-файлу")
    parser.add_argument("fps", type=float,
                        help="Кадров в секунду (fps)")
    parser.add_argument("output_srt", nargs="?",
                        help="(опционально) Путь к выходному SRT-файлу")
    args = parser.parse_args()

    # Если не передали output_srt, то заменяем расширение у input_txt на .srt
    if args.output_srt:
        out_path = args.output_srt
    else:
        base, _ = os.path.splitext(args.input_txt)
        out_path = base + '.srt'

    convert_txt_to_srt(args.input_txt, args.fps, out_path)
    print(f"SRT успешно сохранён в «{out_path}»")

if __name__ == "__main__":
    main()
