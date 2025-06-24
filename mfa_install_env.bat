CALL "Scripts\Editing_scripts\scripts\miniforge3\Scripts\activate.bat" 
conda create --prefix "Scripts\Editing_scripts\scripts\mfa_env" -c conda-forge montreal-forced-aligner && conda clean --all -y
