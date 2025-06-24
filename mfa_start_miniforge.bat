CALL "Scripts\Editing_scripts\scripts\miniforge3\Scripts\activate.bat"  "Scripts\Editing_scripts\scripts\mfa_env"
mfa align_one --clean --overwrite --use_mp --num_jobs 4 --output_format json "Fr_subs2.wav" "fr_sub.txt" "C:\Users\Michail\Desktop\MFA\dic\french_mfa.dict" "C:\Users\Michail\Desktop\MFA\dic\french_mfa.zip" "fr_sub.json"

