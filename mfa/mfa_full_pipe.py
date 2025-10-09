import subprocess
import os
import sys
import argparse
import re
import tempfile

def convert_srt_to_txt(srt_path):
    """
    Читает SRT-файл, убирает номера блоков, тайм-коды и пустые строки,
    сохраняет результат во временный TXT-файл и возвращает его путь.
    """
    timecode_re = re.compile(r'^\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}')
    lines = []
    with open(srt_path, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if line.isdigit():
                continue
            if timecode_re.match(line):
                continue
            lines.append(line)
    # Записываем в временный файл
    tf = tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8', suffix='.txt')
    tf.write('\n'.join(lines))
    tf.close()
    return tf.name

def main():
    parser = argparse.ArgumentParser(description='Run MFA pipeline and generate an SRT file.')

    parser.add_argument('-l', '--language', required=True,
                        help='Language code (e.g., fr, en, ru, pt)')
    parser.add_argument('-w', '--wav-path', required=True, dest='wav_path',
                        help='Path to WAV file')
    parser.add_argument('-t', '--text-path', required=True, dest='text_path',
                        help='Path to txt/srt transcript file')
    parser.add_argument('-j', '--output-json', required=True, dest='output_json',
                        help='Path to save output JSON with timings')
    parser.add_argument('-s', '--output-srt', required=True, dest='output_srt',
                        help='Path to save output SRT')
    parser.add_argument('-b', '--base-color', required=True, dest='base_color',
                        help='Base (background) subtitle color, hex without #')
    parser.add_argument('-c', '--highlight-color', required=True, dest='highlight_color',
                        help='Highlight subtitle color, hex without #')

    args = parser.parse_args()

    # Если на вход пришёл SRT — конвертируем его в TXT
    if args.text_path.lower().endswith('.srt'):
        print(f"Detected SRT input. Converting '{args.text_path}' to plain TXT...")
        mfa_text_path = convert_srt_to_txt(args.text_path)
    else:
        mfa_text_path = args.text_path

    lang_map = {
        "fr": "french_mfa",
        "en": "english_us_mfa310",
        "ru": "russian_mfa",
        "pt": "portuguese_mfa200a",
        "sp": "spanish_mfa330",
        "sp2": "spanish_mfa200a",
        "us": "english_us_arpa300"
        
    }

    if args.language not in lang_map:
        print(f"Error: unsupported language code '{args.language}'. Allowed: {', '.join(lang_map.keys())}")
        sys.exit(1)

    base_name = lang_map[args.language]

    script_dir   = os.path.dirname(os.path.abspath(__file__))
    activate_bat = os.path.join(script_dir, "..", "tools", "miniforge3", "Scripts", "activate.bat")
    env_path     = os.path.join(script_dir, "mfa_env")
    dict_path    = os.path.join(script_dir, "dic", f"{base_name}.dict")
    model_path   = os.path.join(script_dir, "dic", f"{base_name}.zip")

    # Формируем команду MFA с учётом возможного преобразования
    # можно так же добавить f'--quiet' чтобы не получать выводов
    mfa_command = (
        f'CALL "{activate_bat}" "{env_path}" && '
        f'mfa align_one --clean --overwrite --use_mp --num_jobs 8 '
        f'--output_format json '
        f'"{args.wav_path}" "{mfa_text_path}" '
        f'"{dict_path}" "{model_path}" "{args.output_json}" '
        f'--beam 30 --retry_beam 100'
    )

    print("Running MFA align_one...")

    #отключаем уведомление/уведомления
    env = os.environ.copy()
    env["PYTHONWARNINGS"] = "ignore::UserWarning:praatio.utilities.utils"

    result = subprocess.run(mfa_command, shell=True, env=env)
    if result.returncode != 0:
        sys.exit("Error while running MFA. SRT generation aborted.")

    # Генерация финального SRT — логика не изменилась, всегда берёт оригинальный text_path
    srt_script = os.path.join(script_dir, "mfa_make_srt.py")
    srt_command = [
        sys.executable, srt_script,
        "-j", args.output_json,
        "-t", args.text_path,
        "-o", args.output_srt,
        "-c", args.highlight_color,
        "-b", args.base_color
    ]

    print("Generating SRT...")
    subprocess.run(srt_command)

    # Убираем временный файл, если он был создан
    if args.text_path.lower().endswith('.srt'):
        try:
            os.remove(mfa_text_path)
        except OSError:
            pass

if __name__ == "__main__":
    main()
