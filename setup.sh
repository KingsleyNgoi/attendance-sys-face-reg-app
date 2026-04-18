#!/usr/bin/env bash
# Setup wrapper — delegates to setup.ps1 on Windows (Git Bash / WSL)
#!/usr/bin/env bash
# """
# * -e: 
# 	> exit immediately if a command fails.
# * -u: 
# 	> treat use of an unset variable as an error.
# * -o pipefail: 
# 	> if a pipeline fails, return the failure from the first failing command instead of only the last command.
# """
set -euo pipefail

# """
# * ${BASH_SOURCE[0]}: 
#	> the path of the currently running Bash script
# * dirname "${BASH_SOURCE[0]}": 
#	> the directory containing that script
# * cd "$(dirname "${BASH_SOURCE[0]}")": 
#	> change into that directory
# * pwd: 
#	> print the full absolute path of the current directory
# * $(...): 
#	> capture that command output as a string
# * outer quotes "...": 
#	> preserve spaces safely in the resulting path
# """
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if command -v powershell.exe >/dev/null 2>&1; then
    POWERSHELL_BIN="powershell.exe"
elif command -v pwsh.exe >/dev/null 2>&1; then
    POWERSHELL_BIN="pwsh.exe"
elif command -v pwsh >/dev/null 2>&1; then
    POWERSHELL_BIN="pwsh"
else
    echo "PowerShell executable not found in PATH." >&2
    exit 1
fi

# """
# * -NoProfile: 
# 	> starts PowerShell without loading the user's profile scripts, which makes startup more predictable
# * -ExecutionPolicy Bypass: 
# 	> temporarily bypasses script execution policy restrictions for this run
# * -File "${SCRIPT_DIR}start_windows.ps1": 
# 	> tells PowerShell to execute that .ps1 file
# * "$@": 
# 	> forwards all arguments given to the Bash script to the PowerShell script, preserving them as separate arguments.
# """
exec "${POWERSHELL_BIN}" -NoProfile -ExecutionPolicy Bypass -File "${SCRIPT_DIR}/setup.ps1" "$@"
