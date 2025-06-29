export CONDA_EXE="$(cygpath 'C:/miniforge3\Scripts\conda.exe')"
export _CE_M=''
export _CE_CONDA=''
export CONDA_PYTHON_EXE="$(cygpath 'C:/miniforge3\python.exe')"

# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
__conda_exe() (
    if [ -n "${_CE_M:+x}" ] && [ -n "${_CE_CONDA:+x}" ]; then
        # only use _CE_M/_CE_CONDA when defined to avoid issues when run with `set -u`
        "$CONDA_EXE" $_CE_M $_CE_CONDA "$@"
    else
        "$CONDA_EXE" "$@"
    fi
)

__conda_hashr() {
    if [ -n "${ZSH_VERSION:+x}" ]; then
        \rehash
    elif [ -n "${POSH_VERSION:+x}" ]; then
        :  # pass
    else
        \hash -r
    fi
}

__conda_activate() {
    if [ -n "${CONDA_PS1_BACKUP:+x}" ]; then
        # Handle transition from shell activated with conda <= 4.3 to a subsequent activation
        # after conda updated to >= 4.4. See issue #6173.
        PS1="$CONDA_PS1_BACKUP"
        \unset CONDA_PS1_BACKUP
    fi
    \local ask_conda
    ask_conda="$(PS1="${PS1:-}" __conda_exe shell.posix "$@")" || \return
    \eval "$ask_conda"
    __conda_hashr
}

__conda_reactivate() {
    # FUTURE: conda 25.9, remove this function
    echo "'__conda_reactivate' is deprecated and will be removed in 25.9. Use '__conda_activate reactivate' instead." 1>&2
    __conda_activate reactivate
}

conda() {
    \local cmd="${1-__missing__}"
    case "$cmd" in
        activate|deactivate)
            __conda_activate "$@"
            ;;
        install|update|upgrade|remove|uninstall)
            __conda_exe "$@" || \return
            __conda_activate reactivate
            ;;
        *)
            __conda_exe "$@"
            ;;
    esac
}

if [ -z "${CONDA_SHLVL+x}" ]; then
    \export CONDA_SHLVL=0
    # In dev-mode CONDA_EXE is python.exe and on Windows
    # it is in a different relative location to condabin.
    if [ -n "${_CE_CONDA:+x}" ] && [ -n "${WINDIR+x}" ]; then
        PATH="$(\dirname "$CONDA_EXE")/condabin${PATH:+":${PATH}"}"
    else
        PATH="$(\dirname "$(\dirname "$CONDA_EXE")")/condabin${PATH:+":${PATH}"}"
    fi
    \export PATH

    # We're not allowing PS1 to be unbound. It must at least be set.
    # However, we're not exporting it, which can cause problems when starting a second shell
    # via a first shell (i.e. starting zsh from bash).
    if [ -z "${PS1+x}" ]; then
        PS1=
    fi
fi
