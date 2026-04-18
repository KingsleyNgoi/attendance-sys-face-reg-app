<#
.SYNOPSIS
    One-click setup for the Face Recognition Attendance System.
    Run this on a fresh Windows machine to install everything needed.

.DESCRIPTION
    This script will:
      1. Check/install Python 3.11 (via winget)
      2. Enable Windows long paths (avoids WinError 206)
      3. Create a Python virtual environment
      4. Install pip dependencies from requirements.txt
      5. Download the InsightFace buffalo_l recognition model if missing
      6. Guide Redis Cloud setup (or detect existing config)
      7. Generate self-signed SSL cert for HTTPS (webcam access over LAN)

.EXAMPLE
    Right-click this file -> "Run with PowerShell"
    OR from a terminal:
        powershell -ExecutionPolicy Bypass -File .\setup.ps1
#>

# """
# * A [switch] parameter 
#   - is triggered when you pass its name as a flag like input when running the script.
# 
# # Neither switch triggered (both are $false by default)
# .\setup.ps1
# 
# # SkipPython triggered ($SkipPython = $true)
# .\setup.ps1 -SkipPython
# 
# # SkipRedis triggered ($SkipRedis = $true)
# .\setup.ps1 -SkipRedis
# 
# # Both triggered
# .\setup.ps1 -SkipPython -SkipRedis
# """
param(
    [switch]$SkipPython,
    [switch]$SkipRedis
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
Set-Location $scriptRoot



# ─────────────────────────────────────────────
# Helper: colored output
# ─────────────────────────────────────────────
function Write-Step  { param([string]$msg) Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok    { param([string]$msg) Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Warn  { param([string]$msg) Write-Host "    [WARN] $msg" -ForegroundColor Yellow }
function Write-Err   { param([string]$msg) Write-Host "    [ERROR] $msg" -ForegroundColor Red }



# ─────────────────────────────────────────────
# STEP 1: Python 3.11
# ─────────────────────────────────────────────
Write-Step "Checking Python installation..."
$pythonCmd = $null
$requiredMajor = 3
$requiredMinor = 11

# Search common locations + PATH
$candidates = @(
    "python3.11",
    "python3",
    "python",
    "py -3.11"
)

foreach ($candidate in $candidates) {
    try {
        # """
        # * &: 
        #   - The PowerShell call operator. It's required to execute a string or command stored in a variable/expression. 
        #     Without it, PowerShell treats the line as a plain string, not something to run.
        # * cmd /c:
        #   - Runs the command via cmd.exe, where /c means "execute this command then exit."
        # * * 2>&1:
        #   - Redirects stderr to stdout (inside cmd), so the version string is captured 
        #regardless of which stream it's written to.
        # """
        $versionOutput = & cmd /c "$candidate --version 2>&1"
        if ($versionOutput -match "Python (\d+)\.(\d+)") {
            # """
            # * $Matches 
            #   - is an automatic variable that PowerShell populates whenever a -match operator succeeds. 
            #   - It's a hashtable where:
            #       > $Matches[0] = the full match (e.g., "Python 3.11")
            #       > $Matches[1] = first capture group (\d+) → "3"
            #       > $Matches[2] = second capture group (\d+) → "11"
            # """
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -eq $requiredMajor -and $minor -ge $requiredMinor -and $minor -lt 13) {
                $pythonCmd = $candidate
                break
            }
        }
    }
    # """
    # * The empty catch { } 
    #   - intentionally swallows all errors silently. The purpose is:
    #   - If a candidate like "python3.11" doesn't exist, cmd /c throws an error
    #   - We don't care — we just want to skip that candidate and try the next one in the foreach loop
    #   - There's nothing useful to log or handle; a missing command is an expected outcome, not a real error.
    # * It's the PowerShell equivalent of Python's:
    #   try:
    #     ...
    #   except Exception:
    #     pass
    # """ 
    catch { }
}

if (-not $pythonCmd -and -not $SkipPython) {
    Write-Warn "Python 3.11+ not found on this system."
    Write-Step "Installing Python 3.11 via winget..."
    # """
    # * Get-Command
    #   - a built-in PowerShell cmdlet. 
    #   - It checks if a command/program exists and returns info about it (path, type, version). 
    #   - Similar to which in Linux.
    # * winget
    #   - is the Windows Package Manager CLI, a separate Microsoft tool 
    #     that comes pre-installed on Windows 10 (1809+) and Windows 11. 
    #   - It's an external .exe — that's why we use Get-Command to check if it exists before calling it.
    # * -ErrorAction
    #   - a built-in common parameter available on every PowerShell cmdlet. 
    #   - It controls what happens when that specific command encounters an error. 
    #   - Overrides $ErrorActionPreference for just that one call.
    # * SilentlyContinue
    #   - It's one of the built-in enum values for -ErrorAction:
    #     > Suppress error message, keep going
    # """
    $hasWinget = Get-Command winget -ErrorAction SilentlyContinue
    if ($hasWinget) {
        winget install --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements
        # Refresh PATH for this session
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                     [System.Environment]::GetEnvironmentVariable("Path", "User")
        $pythonCmd = "python"
    } else {
        Write-Err "winget not available. Please install Python 3.11 manually from https://www.python.org/downloads/"
        Write-Host "    After installing, re-run this script." -ForegroundColor Yellow
        exit 1
    }
}

if (-not $pythonCmd) {
    Write-Err "Python 3.11+ is required but was not found. Use -SkipPython only if you know what you're doing."
    exit 1
}

# Resolve the actual python executable path
try {
    # """
    # * Pipes the output and takes only the first result (highest priority in PATH). 
    # * Select-Object is a built-in PowerShell cmdlet.
    # """
    $pythonExePath = (& cmd /c "where $pythonCmd 2>&1" | Select-Object -First 1).Trim()
} catch {
    $pythonExePath = $pythonCmd
}

$versionCheck = & $pythonCmd --version 2>&1
Write-Ok "Found: $versionCheck at $pythonExePath"



# ─────────────────────────────────────────────
# STEP 2: Enable Windows long paths
# ─────────────────────────────────────────────
Write-Step "Checking Windows long path support..."
$longPathEnabled = (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -ErrorAction SilentlyContinue).LongPathsEnabled

if ($longPathEnabled -eq 1) {
    Write-Ok "Long paths already enabled."
} else {
    Write-Warn "Long paths are disabled. Attempting to enable (requires admin)..."
    try {
        # """
        # * Start-Process
        #     - Built-in PowerShell cmdlet that launches a new process (like Python's subprocess.Popen).
        # * reg
        #     - The program to launch. reg.exe is a built-in Windows command-line tool for editing the Windows Registry.
        # * -ArgumentList '...'\
        #     - The arguments passed to reg.exe.
        # * add
        #     - Add/modify a registry key
        # * "HKLM\SYSTEM\..."
        #     - The registry path (HKLM = HKEY_LOCAL_MACHINE)
        # * /v LongPathsEnabled
        #     - The value name to set
        # * /t REG_DWORD
        #     - The data type (32-bit integer)
        # * /d 1
        #     - The data to write (1 = enabled)
        # * /f
        #     - Force overwrite without confirmation prompt
        # """
        Start-Process reg -ArgumentList 'add "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled /t REG_DWORD /d 1 /f' -Verb RunAs -Wait
        Write-Ok "Long paths enabled. (You may need to restart your terminal.)"
    } catch {
        Write-Warn "Could not enable long paths automatically."
        Write-Host "    Run this as Administrator, or manually set:" -ForegroundColor Yellow
        Write-Host '    reg add "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled /t REG_DWORD /d 1 /f' -ForegroundColor Yellow
    }
}



# ─────────────────────────────────────────────
# STEP 3: Create virtual environment
# ─────────────────────────────────────────────
Write-Step "Setting up Python virtual environment..."
$venvDir = Join-Path $scriptRoot ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

if (Test-Path $venvPython) {
    # Check if the venv's base Python still exists
    $pyvenvCfg = Join-Path $venvDir "pyvenv.cfg"
    $venvBroken = $false
    if (Test-Path $pyvenvCfg) {
        # """
        # * Get-Content 
        #     - Built-in PowerShell cmdlet 
        #       that reads the file and returns each line as a separate string in an array (like Python's readlines()).
        # * Where-Object
        #     - Built-in cmdlet that filters. 
        #     - Only keeps lines where the condition is $true (Like Python's filter()).
        # * $_ 
        #     - The current pipeline item (i.e., the current line being tested). 
        #     - It's an automatic variable, like x in Python's lambda x: ...
        # * "^home\s*="
        #     - Regex: line starts with home, optional whitespace, then =
        # * Result
        #     - $homeLine gets the matching line string, 
        #         > e.g.: "home = C:\Users\User\AppData\Local\Programs\Python\Python311"
        # """
        $homeLine = Get-Content $pyvenvCfg | Where-Object { $_ -match "^home\s*=" }
        if ($homeLine) {
            $homeDir = ($homeLine -split "=", 2)[1].Trim()
            if (-not (Test-Path (Join-Path $homeDir "python.exe"))) {
                Write-Warn "Existing venv points to missing Python at: $homeDir"
                $venvBroken = $true
            }
        }
    }

    if ($venvBroken) {
        Write-Warn "Removing broken virtual environment..."
        Remove-Item -Recurse -Force $venvDir
    } else {
        Write-Ok "Virtual environment already exists."
    }
}

if (-not (Test-Path $venvPython)) {
    Write-Host "    Creating .venv with $pythonCmd..."
    & $pythonCmd -m venv $venvDir
    Write-Ok "Virtual environment created."
}



# ─────────────────────────────────────────────
# STEP 4: Install dependencies
# ─────────────────────────────────────────────
Write-Step "Installing Python dependencies..."
& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install -r (Join-Path $scriptRoot "requirements.txt")

if ($LASTEXITCODE -ne 0) {
    Write-Err "pip install failed. Check the output above for errors."
    exit 1
}

# """
# * Force-install ml_dtypes==0.5.1 AFTER tensorflow.
# * tensorflow 2.15.1 pins ml-dtypes~=0.3.1, but onnx 1.19.0 needs >=0.5.
# * Installing 0.5.1 after the fact works fine at runtime — tensorflow
#   only uses basic ml_dtypes features that are still present.
# * --no-deps prevents pip from downgrading other packages.
# """
Write-Host "    Upgrading ml_dtypes to 0.5.1 (post-install fix for onnx compatibility)..."
& $venvPython -m pip install "ml_dtypes==0.5.1" --no-deps --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Warn "ml_dtypes upgrade failed. onnx may not work correctly."
}

Write-Ok "All dependencies installed."



# ─────────────────────────────────────────────
# STEP 5: Download InsightFace buffalo_l model
# ─────────────────────────────────────────────
Write-Step "Checking InsightFace buffalo_l models..."
$modelDir = Join-Path $scriptRoot "insightface_model\models\buffalo_l"
$requiredModels = @(
    "det_10g.onnx",
    "1k3d68.onnx",
    "2d106det.onnx",
    "genderage.onnx",
    "w600k_r50.onnx"
)

$missingModels = @()
foreach ($model in $requiredModels) {
    $modelPath = Join-Path $modelDir $model
    if (-not (Test-Path $modelPath)) {
        $missingModels += $model
    }
}

if ($missingModels.Count -eq 0) {
    Write-Ok "All 5 buffalo_l models present."
} else {
    Write-Warn "Missing models: $($missingModels -join ', ')"
    Write-Host "    Downloading buffalo_l model pack from GitHub (~275 MB)..."

    $zipPath = Join-Path $scriptRoot "buffalo_l_download.zip"
    try {
        & $venvPython -c @"
import urllib.request, zipfile, os, sys
url = 'https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip'
dest_zip = r'$zipPath'
model_dir = r'$modelDir'
os.makedirs(model_dir, exist_ok=True)
print('    Downloading... (this may take a few minutes)')
urllib.request.urlretrieve(url, dest_zip)
print(f'    Downloaded {os.path.getsize(dest_zip) / 1024 / 1024:.0f} MB')
print('    Extracting models...')
with zipfile.ZipFile(dest_zip, 'r') as z:
    for name in z.namelist():
        data = z.read(name)
        out = os.path.join(model_dir, os.path.basename(name))
        with open(out, 'wb') as f:
            f.write(data)
        print(f'    Extracted: {os.path.basename(name)} ({len(data) / 1024 / 1024:.1f} MB)')
os.remove(dest_zip)
print('    Cleanup done.')
"@
        Write-Ok "All buffalo_l models downloaded."
    } catch {
        Write-Err "Model download failed: $_"
        Write-Host "    You can manually download from:" -ForegroundColor Yellow
        Write-Host "    https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip" -ForegroundColor Yellow
        Write-Host "    Extract all .onnx files to: $modelDir" -ForegroundColor Yellow
        if (Test-Path $zipPath) { Remove-Item $zipPath -ErrorAction SilentlyContinue }
    }
}



# ─────────────────────────────────────────────
# STEP 6: Redis configuration
# ─────────────────────────────────────────────
if (-not $SkipRedis) {
    Write-Step "Checking Redis configuration..."
    $faceRecFile = Join-Path $scriptRoot "face_rec.py"
    $faceRecContent = Get-Content $faceRecFile -Raw

    # Check if Redis credentials are configured
    if ($faceRecContent -match "hostname_endpoint\s*=\s*'([^']+)'") {
        $currentHost = $Matches[1]
        Write-Ok "Redis host configured: $currentHost"

        # Quick connectivity test
        Write-Host "    Testing Redis connection..."
        $redisTest = & $venvPython -c @"
import sys
try:
    import redis
    r = redis.StrictRedis(host='$currentHost', port=17847, password='iJQ9dv7SbtznxD2rDQPVPzaHoLFF2psH', socket_timeout=5)
    r.ping()
    print('CONNECTED')
except Exception as e:
    print(f'FAILED: {e}')
"@ 2>&1

        if ($redisTest -match "CONNECTED") {
            Write-Ok "Redis connection successful!"
        } else {
            Write-Warn "Redis connection failed: $redisTest"
            Write-Host ""
            Write-Host "    ┌─────────────────────────────────────────────────┐" -ForegroundColor Yellow
            Write-Host "    │  Redis Cloud Setup Instructions:                │" -ForegroundColor Yellow
            Write-Host "    │                                                 │" -ForegroundColor Yellow
            Write-Host "    │  1. Go to https://redis.io/try-free            │" -ForegroundColor Yellow
            Write-Host "    │  2. Sign up / log in                           │" -ForegroundColor Yellow
            Write-Host "    │  3. Create a free database                     │" -ForegroundColor Yellow
            Write-Host "    │  4. Copy: host, port, password                 │" -ForegroundColor Yellow
            Write-Host "    │  5. Update face_rec.py lines 24-26:            │" -ForegroundColor Yellow
            Write-Host "    │     hostname_endpoint = 'your-host'            │" -ForegroundColor Yellow
            Write-Host "    │     port = your-port                           │" -ForegroundColor Yellow
            Write-Host "    │     password = 'your-password'                 │" -ForegroundColor Yellow
            Write-Host "    │                                                 │" -ForegroundColor Yellow
            Write-Host "    │  OR use Docker for local Redis:                │" -ForegroundColor Yellow
            Write-Host "    │     docker run -d -p 6379:6379 redis:latest    │" -ForegroundColor Yellow
            Write-Host "    │     Then set: host='localhost', port=6379      │" -ForegroundColor Yellow
            Write-Host "    └─────────────────────────────────────────────────┘" -ForegroundColor Yellow

            $response = Read-Host "`n    Do you want to enter Redis credentials now? (y/N)"
            if ($response -eq 'y' -or $response -eq 'Y') {
                $newHost = Read-Host "    Redis host"
                $newPort = Read-Host "    Redis port"
                $newPass = Read-Host "    Redis password"

                if ($newHost -and $newPort -and $newPass) {
                    $faceRecContent = $faceRecContent -replace "hostname_endpoint\s*=\s*'[^']*'", "hostname_endpoint = '$newHost'"
                    $faceRecContent = $faceRecContent -replace "(?<=^port\s*=\s*)\d+", $newPort
                    $faceRecContent = $faceRecContent -replace "password\s*=\s*'[^']*'", "password = '$newPass'"
                    Set-Content -Path $faceRecFile -Value $faceRecContent -NoNewline
                    Write-Ok "Redis credentials updated in face_rec.py"
                }
            }
        }
    }

    # Check for seed data
    $seedFile = Join-Path $scriptRoot "data\features_store\dataframe_love_friend_relationship.npz"
    if (Test-Path $seedFile) {
        Write-Host ""
        Write-Host "    Found seed data: $seedFile"
        $loadSeed = Read-Host "    Load seed face data into Redis? (y/N)"
        if ($loadSeed -eq 'y' -or $loadSeed -eq 'Y') {
            Write-Host "    Loading seed data into Redis..."
            & $venvPython -c @"
import numpy as np
import sys, os
sys.path.insert(0, r'$scriptRoot')

# Load the .npz file
data = np.load(r'$seedFile', allow_pickle=True)
print(f"    NPZ keys: {list(data.keys())}")
for key in data.keys():
    arr = data[key]
    print(f"    {key}: shape={arr.shape}, dtype={arr.dtype}")

try:
    import redis
    # Read current credentials from face_rec.py
    import re
    with open(r'$faceRecFile', 'r') as f:
        content = f.read()
    host = re.search(r"hostname_endpoint\s*=\s*'([^']+)'", content).group(1)
    port = int(re.search(r"^port\s*=\s*(\d+)", content, re.MULTILINE).group(1))
    pwd = re.search(r"password\s*=\s*'([^']*)'", content).group(1)
    hashname = re.search(r"hashname\s*=\s*'([^']+)'", content).group(1)

    r = redis.StrictRedis(host=host, port=port, password=pwd, socket_timeout=5)
    r.ping()

    # Try to load as a pandas-like structure
    df = None
    for key in data.keys():
        arr = data[key]
        if arr.dtype == object:
            # This is likely a serialized DataFrame
            df = arr.item() if arr.ndim == 0 else arr
            break

    if df is not None and hasattr(df, 'iterrows'):
        count = 0
        for idx, row in df.iterrows():
            name = row.get('Name', '')
            role = row.get('Role', '')
            features = row.get('Facial_Features', None)
            if name and features is not None:
                redis_key = f'{name}@{role}'
                features_arr = np.asarray(features, dtype=np.float64)
                r.hset(hashname, redis_key, features_arr.tobytes())
                count += 1
        print(f'    Loaded {count} face(s) into Redis hash: {hashname}')
    else:
        print('    Could not interpret seed data as face features DataFrame.')
        print('    You may need to register faces manually via the Registration page.')
except Exception as e:
    print(f'    Failed to load seed data: {e}')
"@
        }
    }
}



# ─────────────────────────────────────────────
# STEP 7: HTTPS for local media device access
# ─────────────────────────────────────────────
# """
# * Browsers block camera/microphone access on non-HTTPS origins (except localhost).
# * If accessing the app from another device on the LAN (e.g. http://192.168.1.x:8501),
#   the webcam will NOT work without HTTPS.
# * This step generates a self-signed SSL certificate and configures Streamlit to use it,
#   so WebRTC camera access works even over LAN.
# * On localhost (127.0.0.1) this is NOT needed — browsers allow camera on localhost.
# """
Write-Step "Configuring HTTPS for local media device access..."
$sslDir = Join-Path $scriptRoot ".ssl"
$certFile = Join-Path $sslDir "cert.pem"
$keyFile = Join-Path $sslDir "key.pem"
$streamlitConfig = Join-Path $scriptRoot ".streamlit\config.toml"

if (Test-Path $certFile) {
    Write-Ok "SSL certificate already exists at $sslDir"
} else {
    Write-Host "    Generating self-signed SSL certificate..."
    New-Item -ItemType Directory -Force -Path $sslDir | Out-Null
    # """
    # * Use Python + cryptography library to generate a self-signed cert.
    # * We use Python because OpenSSL is not always available on Windows,
    #   and the cryptography package is already installed as a dependency.
    # """
    & $venvPython -c @"
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import datetime, ipaddress

# Generate RSA private key
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

# Build certificate subject
subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COMMON_NAME, u'localhost'),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, u'FaceRecognition Dev'),
])

# Build the self-signed certificate (valid for 1 year)
cert = (
    x509.CertificateBuilder()
    .subject_name(subject)
    .issuer_name(issuer)
    .public_key(key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.datetime.utcnow())
    .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
    .add_extension(
        x509.SubjectAlternativeName([
            x509.DNSName(u'localhost'),
            x509.IPAddress(ipaddress.IPv4Address('127.0.0.1')),
            x509.IPAddress(ipaddress.IPv4Address('0.0.0.0')),
        ]),
        critical=False,
    )
    .sign(key, hashes.SHA256())
)

# Write cert and key to PEM files
with open(r'$certFile', 'wb') as f:
    f.write(cert.public_bytes(serialization.Encoding.PEM))
with open(r'$keyFile', 'wb') as f:
    f.write(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))
print('    Certificate generated successfully.')
"@
    if (Test-Path $certFile) {
        Write-Ok "Self-signed SSL certificate created in .ssl/"
    } else {
        Write-Warn "Failed to generate SSL certificate. HTTPS will not be available."
        Write-Host "    Camera will still work on localhost (http://127.0.0.1:8501)" -ForegroundColor Yellow
    }
}

# Update .streamlit/config.toml with SSL settings if cert exists
if (Test-Path $certFile) {
    $configContent = Get-Content $streamlitConfig -Raw
    if ($configContent -notmatch "sslCertFile") {
        Write-Host "    Adding SSL config to .streamlit/config.toml..."
        # """
        # * Append sslCertFile and sslKeyFile under [server] section.
        # * These tell Streamlit to serve over HTTPS using our self-signed cert.
        # """
        $sslConfig = @"

# HTTPS for local media device (webcam) access over LAN
sslCertFile = ".ssl/cert.pem"
sslKeyFile = ".ssl/key.pem"
"@
        Add-Content -Path $streamlitConfig -Value $sslConfig
        Write-Ok "Streamlit configured for HTTPS."
    } else {
        Write-Ok "Streamlit SSL config already present."
    }
    Write-Host ""
    Write-Host "    NOTE: Since this is a self-signed certificate, your browser" -ForegroundColor Yellow
    Write-Host "    will show a security warning. Click 'Advanced' -> 'Proceed'" -ForegroundColor Yellow
    Write-Host "    to accept it. This is safe for local development." -ForegroundColor Yellow
}



# ─────────────────────────────────────────────
# DONE
# ─────────────────────────────────────────────
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  To start the app:" -ForegroundColor White
Write-Host "    .\start_app.ps1" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Or from Git Bash / WSL:" -ForegroundColor White
Write-Host "    ./start_app.sh" -ForegroundColor Cyan
Write-Host ""
Write-Host "  The app will open at:" -ForegroundColor White
if (Test-Path $certFile) {
    Write-Host "    https://localhost:8501  (local)" -ForegroundColor Cyan
    Write-Host "    https://<your-ip>:8501  (LAN - webcam works)" -ForegroundColor Cyan
} else {
    Write-Host "    http://localhost:8501" -ForegroundColor Cyan
}
Write-Host ""
