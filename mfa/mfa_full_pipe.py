import subprocess
import os
import sys
import argparse
import re
import tempfile
from pathlib import Path

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
    tf = tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8', suffix='.txt')
    tf.write('\n'.join(lines))
    tf.close()
    return tf.name

def str2bool(val: str, default=True) -> bool:
    if val is None:
        return default
    v = str(val).strip().lower()
    if v in {"1","true","t","yes","y","on"}:
        return True
    if v in {"0","false","f","no","n","off"}:
        return False
    return default

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

    parser.add_argument('--use_textgrid', required=False, default="true",
                        help='Use TextGrid + mfa align pipeline (true/false). Default: true')

    args = parser.parse_args()
    use_textgrid = str2bool(args.use_textgrid, default=True)

    # Если на вход пришёл SRT — сделаем TXT (на случай фолбека align_one)
    if args.text_path.lower().endswith('.srt'):
        print(f"Detected SRT input. Converting '{args.text_path}' to plain TXT (align_one fallback)...")
        mfa_text_path = convert_srt_to_txt(args.text_path)
    else:
        mfa_text_path = args.text_path

    lang_map = {
        "fr": "french_mfa300",
        "en": "english_us_mfa310",
        "ru": "russian_mfa310",
        "pt": "portuguese_mfa200a",
        "sp": "spanish_mfa330",
        "sp2": "spanish_mfa200a",
        "us": "english_us_arpa300"
    }

    # G2P моделей (.zip лежат в dic/g2p/)
    g2p_map = {
        "fr":  "french_mfa300",
        "en":  "english_us_mfa300",
        "ru":  "russian_mfa310",
        "pt":  "portuguese_brazil_mfa200a",
        "sp":  "spanish_spain_mfa330",
        "sp2": "spanish_spain_mfa200a",
        "us":  "english_us_arpa200a",
    }

    if args.language not in lang_map:
        print(f"Error: unsupported language code '{args.language}'. Allowed: {', '.join(lang_map.keys())}")
        sys.exit(1)

    base_name   = lang_map[args.language]
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    activate_bat = os.path.join(script_dir, "..", "tools", "miniforge3", "Scripts", "activate.bat")
    env_path     = os.path.join(script_dir, "mfa_env")
    dict_path    = os.path.join(script_dir, "dic", f"{base_name}.dict")
    model_path   = os.path.join(script_dir, "dic", f"{base_name}.zip")

    # G2P по карте (если файл существует — подключаем)
    g2p_name = g2p_map.get(args.language)
    g2p_path = None
    if g2p_name:
        candidate = os.path.join(script_dir, "dic", "g2p", f"{g2p_name}.zip")
        if os.path.isfile(candidate):
            g2p_path = candidate
            print(f"G2P model selected: {g2p_path}")
        else:
            print(f"Warning: G2P zip not found at {candidate}. Proceeding without G2P.")
    else:
        print("No G2P mapping for this language. Proceeding without G2P.")

    # Отключаем предупреждения praatio в stdout
    env = os.environ.copy()
    env["PYTHONWARNINGS"] = "ignore::UserWarning:praatio.utilities.utils"

    def build_mfa_align_one_command(beam: int, retry_beam: int) -> str:
        #g2p_arg = f' --g2p_model_path "{g2p_path}"' if g2p_path else ''
        g2p_arg ='' # временно отключил g2p при запуске align_one, из за бага не работает https://github.com/MontrealCorpusTools/Montreal-Forced-Aligner/issues/911
        return (
            f'CALL "{activate_bat}" "{env_path}" && '
            f'mfa align_one --clean --overwrite --use_mp --num_jobs 8 '
            f'--output_format json '
            f'"{args.wav_path}" "{mfa_text_path}" '
            f'"{dict_path}" "{model_path}" "{args.output_json}" '
            f'--beam {beam} --retry_beam {retry_beam}{g2p_arg}'
        )

    def run_align_with_textgrid() -> bool:
        """
        Возвращает True, если путь TextGrid+align отработал успешно (включая
        переименование JSON в args.output_json), иначе False (будет фолбек).
        """
        wav_path = Path(args.wav_path)
        corpus_dir = str(wav_path.parent)                 # корпус = папка WAV
        wav_base = wav_path.stem
        input_tg_path = wav_path.with_suffix(".TextGrid") # .TextGrid рядом с WAV, тем же именем
        made_tg = False

        try:
            # 1) SRT -> TextGrid (обязательно из исходного SRT)
            if not args.text_path.lower().endswith(".srt"):
                print("Warning: --use_textgrid=true requires an SRT transcript; got a non-SRT. Falling back to align_one.")
                return False

            srt2tg_script = os.path.join(script_dir, "utils", "srt_to_textgrid.py")
            if not os.path.isfile(srt2tg_script):
                print(f"Error: srt_to_textgrid.py not found at: {srt2tg_script}")
                return False

            print(f"Converting SRT to TextGrid next to WAV: {input_tg_path}")
            srt2tg_cmd = [
                sys.executable, srt2tg_script,
                args.text_path, "--wav", str(wav_path),
                "--out", str(input_tg_path),
                "--mode", "single", "--tier", "SPK1"
            ]
            res = subprocess.run(srt2tg_cmd, env=env)
            if res.returncode != 0 or not input_tg_path.exists():
                print("Error: Failed to create TextGrid.")
                return False
            made_tg = True

            # 2) MFA align
            output_dir = os.path.dirname(os.path.abspath(args.output_json))
            os.makedirs(output_dir, exist_ok=True)

            g2p_arg = f' --g2p_model_path "{g2p_path}"' if g2p_path else ''
            mfa_cmd = (
                f'CALL "{activate_bat}" "{env_path}" && '
                f'mfa align --clean --overwrite --use_mp --use_threading --num_jobs 1 '
                f'--output_format json --single_speaker '
                f'"{corpus_dir}" "{dict_path}" "{model_path}" "{output_dir}" '
                f'--beam 100 --retry_beam 400{g2p_arg}'
            )
            print("Running MFA align (TextGrid path)...")
            res = subprocess.run(mfa_cmd, shell=True, env=env)
            if res.returncode != 0:
                print("Error: MFA align failed.")
                return False

            # 3) Переименуем JSON в args.output_json
            output_dir_path = Path(output_dir)
            target_json_path = Path(args.output_json)

            candidate = output_dir_path / f"{wav_base}.json"
            produced_path = None
            if candidate.exists():
                produced_path = candidate
            else:
                jsons = sorted(output_dir_path.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
                prefixed = [p for p in jsons if p.stem.startswith(wav_base)]
                if prefixed:
                    produced_path = prefixed[0]
                elif jsons:
                    produced_path = jsons[0]

            if produced_path is None or not produced_path.exists():
                print("Warning: JSON produced by MFA align not found for renaming. Falling back to align_one.")
                return False

            try:
                if target_json_path.exists():
                    try:
                        target_json_path.unlink()
                    except OSError:
                        pass
                os.replace(str(produced_path), str(target_json_path))
                print(f"Aligned JSON renamed to: {target_json_path}")
            except OSError as e:
                print(f"Error: failed to rename JSON: {e}. Falling back to align_one.")
                return False

            return True

        finally:
            # 4) Удаляем созданный TextGrid, если он нам больше не нужен
            if made_tg and input_tg_path.exists():
                try:
                    input_tg_path.unlink()
                except OSError:
                    pass

    # === Выбор пути ===
    used_textgrid = False
    if use_textgrid:
        used_textgrid = run_align_with_textgrid()

    if not used_textgrid:
        # Фолбек на align_one
        print("Running MFA align_one (fallback)...")
        cmd = build_mfa_align_one_command(beam=30, retry_beam=100)
        result = subprocess.run(cmd, shell=True, env=env)
        if result.returncode != 0:
            print("MFA failed with --beam 30/100. Retrying with --beam 100/400...")
            cmd_retry = build_mfa_align_one_command(beam=100, retry_beam=400)
            result = subprocess.run(cmd_retry, shell=True, env=env)
            if result.returncode != 0:
                sys.exit("Error while running MFA (after retry). SRT generation aborted.")

    # === Генерация финального SRT (как было) ===
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

    # Чистим временный TXT, если создавали
    if args.text_path.lower().endswith('.srt'):
        try:
            os.remove(mfa_text_path)
        except OSError:
            pass

if __name__ == "__main__":
    main()
