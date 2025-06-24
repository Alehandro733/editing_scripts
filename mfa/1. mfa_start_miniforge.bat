pushd "%~dp0"

CALL "..\tools\miniforge3\Scripts\activate.bat" "%CD%\mfa_env"

mfa align_one --clean --overwrite --use_mp --num_jobs 4 --output_format json "Fr_test.wav" "text.txt" "dic\french_mfa.dict" "dic\french_mfa.zip" "fr_sub.json"

pause

