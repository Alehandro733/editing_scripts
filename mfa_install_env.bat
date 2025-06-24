CALL "tools\miniforge3\Scripts\activate.bat" 
conda create --prefix "mfa\mfa_env" -c conda-forge montreal-forced-aligner && conda clean --all -y
pause
