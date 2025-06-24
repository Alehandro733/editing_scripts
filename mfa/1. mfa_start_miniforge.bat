CALL "..\tools\miniforge3\Scripts\activate.bat"  "mfa_env"
mfa align_one --clean --overwrite --use_mp --num_jobs 4 --output_format json "Fr_subs2.wav" "fr_sub.txt" "dic\french_mfa.dict" "dic\french_mfa.zip" "fr_sub.json"

