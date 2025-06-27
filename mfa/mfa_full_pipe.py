import subprocess
import os
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description='Запустить MFA-пайплайн и сгенерировать SRT-файл.')

    parser.add_argument('-l', '--language', required=True,
                        help='Код языка (например, fr, en, ru, pt)')
    parser.add_argument('-w', '--wav-path', required=True, dest='wav_path',
                        help='Путь до WAV-файла')
    parser.add_argument('-t', '--text-path', required=True, dest='text_path',
                        help='Путь до текстового файла с расшифровкой')
    parser.add_argument('-j', '--output-json', required=True, dest='output_json',
                        help='Куда сохранить выходной JSON с таймингами')
    parser.add_argument('-s', '--output-srt', required=True, dest='output_srt',
                        help='Куда сохранить выходной SRT')
    parser.add_argument('-b', '--base-color', required=True, dest='base_color',
                        help='Базовый (background) цвет субтитров, hex без #')
    parser.add_argument('-c', '--highlight-color', required=True, dest='highlight_color',
                        help='Цвет подсветки субтитров, hex без #')

    args = parser.parse_args()

    lang_map = {
        "fr": "french_mfa", 
        "en": "english_us_mfa310",
        "ru": "russian_mfa", 
        "pt": "portuguese_mfa"
    }

    if args.language not in lang_map:
        print(f"Ошибка: неподдерживаемый код языка '{args.language}'. Допустимые: {', '.join(lang_map.keys())}")
        sys.exit(1)

    base_name = lang_map[args.language]

    script_dir   = os.path.dirname(os.path.abspath(__file__))
    activate_bat = os.path.join(script_dir, "..", "tools", "miniforge3", "Scripts", "activate.bat")
    env_path     = os.path.join(script_dir, "mfa_env")
    dict_path    = os.path.join(script_dir, "dic", f"{base_name}.dict")
    model_path   = os.path.join(script_dir, "dic", f"{base_name}.zip")

    mfa_command = (
        f'CALL "{activate_bat}" "{env_path}" && '
        f'mfa align_one --clean --overwrite --use_mp --num_jobs 8 '
        f'--output_format json '
        f'"{args.wav_path}" "{args.text_path}" '
        f'"{dict_path}" "{model_path}" "{args.output_json}" '
        f'--beam 100 --retry_beam 400'
    )

    print("Running MFA align_one…")
    result = subprocess.run(mfa_command, shell=True)
    if result.returncode != 0:
        sys.exit("Ошибка при выполнении MFA. Генерация SRT не выполнена.")

    srt_script = os.path.join(script_dir, "mfa_make_srt.py")
    srt_command = [
        sys.executable, srt_script,
        "-j", args.output_json,
        "-t", args.text_path,
        "-o", args.output_srt,
        "-c", args.highlight_color,
        "-b", args.base_color
    ]

    print("Generating SRT…")
    subprocess.run(srt_command)

if __name__ == "__main__":
    main()
