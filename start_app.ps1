# """
# # * A [switch] parameter 
#   - is triggered when you pass its name as a flag like input when running the script.
# 
# # Neither switch triggered (both are $false by default)
# .\start_app.ps1
#
# * param(...): 
#     - declares input parameters for the script
# * [switch]$InstallDeps: 
#     - boolean flag, used like -InstallDeps
#     - .\start_app.ps1 -InstallDeps
# * [string]$BindHost = "127.0.0.1": 
#     - a string parameter with a default value
#   - .\start_app.ps1 -BindHost
# * [int]$Port = 8501: 
#     - an integer parameter with a default value
#     - .\start_app.ps1 -Port
# """
param(
    [switch]$InstallDeps,
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8501
)

# """
# * Set-StrictMode -Version Latest
#   - makes PowerShell stricter
#   - catches things like using uninitialized variables, bad property access, and some sloppy script mistakes
# 
# * $ErrorActionPreference = "Stop"
#   - tells PowerShell to treat non-terminating errors as terminating errors
#   - without it, some commands may print an error but the script can keep going
# 
# * So even if you do not see another line “using” $ErrorActionPreference, 
#   - it still affects all later commands in the script.
# 
# * without "Stop":
#   - a command may fail
#   - PowerShell may only log the error
#   - the script may continue into a broken state
# * With "Stop":
#   - the script stops immediately
#   - you fail fast instead of continuing with partial setup
# """
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# """
# * $MyInvocation
#   - automatic PowerShell variable with information about how the script/command was invoked
# * $MyInvocation.MyCommand
#   - the current script or command object
# * $MyInvocation.MyCommand.Path
#   - the full path to the current .ps1 file
# * Split-Path -Parent ...
#   - removes the filename and keeps only the parent directory
# """
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
# """
# * Set-Location
#     - a powershell command to the changes the current working directory.
# """
Set-Location $scriptRoot

# """
# * Get-VenvPython function:
#     - a user-defined function 
#         > to find the Python executable in candidate virtual environment directories
#         > takes a list of candidate virtual environment directories
#         > checks if the python executable exists in each candidate
#         > returns the path to the first found python executable
#         > throws an error if none are found
#
# * Join-Path, Test-Path 
#   - actual PowerShell built-in commands.
# """
function Get-VenvPython {
    # """
    # * [string[]]$Candidates 
    #     - is not an initially empty list by itself. It is a parameter declaration that says:
    #     - $Candidates is expected to be an array of strings
    #     - the actual values come from the function call
    #
    # * $pythonExe = Get-VenvPython -Candidates @(".venv", "venv", ".env")
    #   - $Candidates will be set to the array of strings passed in the function call
    #       (@(".venv", "venv", ".env"))
    # """
    param(
        [string[]]$Candidates
    )

    foreach ($candidate in $Candidates) {
        $pythonPath = Join-Path $scriptRoot $candidate
        $pythonPath = Join-Path $pythonPath "Scripts\python.exe"
        if (Test-Path $pythonPath) {
            return $pythonPath
        }
    }
    throw "No virtual environment Python executable was found. Expected one of: $($Candidates -join ', ')"
}

$pythonExe = $null
try {
    $pythonExe = Get-VenvPython -Candidates @(
        ".venv",
        "venv",
        ".env"
    )
} catch {
    Write-Host "No virtual environment found. Running setup first..." -ForegroundColor Yellow
    $setupScript = Join-Path $scriptRoot "setup.ps1"
    if (Test-Path $setupScript) {
        & $setupScript
        $pythonExe = Get-VenvPython -Candidates @(".venv", "venv", ".env")
    } else {
        throw "setup.ps1 not found. Please create a virtual environment manually."
    }
}

if ($InstallDeps) {
    & $pythonExe -m pip install --upgrade pip
    & $pythonExe -m pip install -r (Join-Path $scriptRoot "requirements.txt")
}

# """
# * Write-Host 
#     - prints text directly to the PowerShell console for the user to see.
# """
Write-Host "Using Python:" $pythonExe
Write-Host "Starting Streamlit on http://${BindHost}:$Port"
Write-Host "Webcam access works on localhost without HTTPS."

& $pythonExe -m streamlit run (Join-Path $scriptRoot "Home.py") `
    --server.address $BindHost `
    --server.port $Port `
    --server.headless true