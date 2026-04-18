# Attendance System using Face Recognition
A real-time face recognition attendance system built with **Streamlit**, **InsightFace**, and **Redis**. The app detects and identifies registered faces via webcam, automatically logs attendance, and provides reporting tools — all through a browser-based interface.

---

## Table of Contents
- [Purpose](#purpose)
- [Features](#features)
- [System Architecture](#system-architecture)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
  - [Automated Setup (Recommended)](#automated-setup-recommended)
  - [Manual Setup](#manual-setup)
- [Running the App](#running-the-app)
- [How to Use](#how-to-use)
  - [1. Register Faces](#1-register-faces)
  - [2. Real-Time Attendance](#2-real-time-attendance)
  - [3. View Reports](#3-view-reports)
- [HTTPS & Webcam Access over LAN](#https--webcam-access-over-lan)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

---

## Purpose
Manual attendance tracking is slow, error-prone, and easy to game. This system automates attendance by recognizing registered faces in real time through a webcam stream. It is designed for small-to-medium environments such as classrooms, offices, or events.

Key goals:
- **Automated attendance** — no manual sign-in sheets
- **Real-time identification** — faces are recognized as they appear on camera
- **Browser-based** — no native app installation needed for end users
- **Portable** — one-click setup script handles all dependencies

---

## Features
| Feature | Description |
|---|---|
| **Real-Time Face Recognition** | Live webcam stream with bounding boxes, name/role labels, and cosine similarity matching against registered faces |
| **Face Registration** | Two capture modes: auto-capture (10 samples at 1/sec) or manual snapshot. Averages 10 embeddings into a single 512-dimensional feature vector |
| **Attendance Logging** | Automatically logs `Name@Role@Timestamp` to Redis every 5 seconds, with deduplication |
| **Reporting Dashboard** | View registered faces, browse attendance logs with time-range filters (1h to 7d), export as table or JSON, delete entries |
| **WebRTC Streaming** | Browser-native webcam access via `streamlit-webrtc` with STUN/TURN support |
| **Redis Cloud Storage** | All face embeddings and attendance logs stored in Redis (cloud or local) |
| **One-Click Setup** | Automated `setup.ps1` script installs Python, dependencies, models, and configures SSL |
| **HTTPS Support** | Self-signed SSL certificate generation for webcam access over LAN |

---

## System Architecture
```
┌─────────────┐     WebRTC      ┌──────────────────────┐
│   Browser    │◄──────────────►│   Streamlit Server   │
│  (Webcam)    │                │   (Home.py + pages/) │
└─────────────┘                └──────────┬───────────┘
                                          │
                               ┌──────────▼───────────┐
                               │   InsightFace ONNX   │
                               │   (buffalo_l model)  │
                               │   - Face Detection   │
                               │   - 512-d Embedding  │
                               └──────────┬───────────┘
                                          │
                               ┌──────────▼───────────┐
                               │   Redis Database     │
                               │   - Face Embeddings  │
                               │   - Attendance Logs  │
                               └──────────────────────┘
```

A detailed Mermaid flowchart is available at 
    - [docs/system_flowchart.mmd](docs/system_flowchart.mmd)
    - [docs/system_flowchart.png](docs/system_flowchart.png)
    - [docs/system_flowchart.svg](docs/system_flowchart.svg).

---

## Tech Stack
| Component | Technology |
|---|---|
| Web Framework | Streamlit 1.56.0 |
| Face Recognition | InsightFace 0.7.3 (buffalo_l ONNX models) |
| Webcam Streaming | streamlit-webrtc 0.64.5 (WebRTC) |
| ML Inference | ONNX Runtime 1.17.1 (CUDA or CPU) |
| Database | Redis 7.4.0 (Cloud or Docker) |
| Similarity Search | scikit-learn (cosine similarity) |
| Computer Vision | OpenCV 4.9.0 |
| Language | Python 3.11 |

---

## Prerequisites
- **Windows 10/11** (setup script is PowerShell-based)
- **Python 3.11** — installed automatically by setup script if missing
- **Redis database** — either [Redis Cloud](https://redis.io/try-free) (free tier) or local Docker instance
- **Webcam** — built-in or USB camera
- **Internet connection** — for initial model download (~275 MB) and Redis Cloud

---

## Quick Start
### Automated Setup (Recommended)
The `setup.ps1` script handles everything in 7 steps:
1. Installs Python 3.11 (via `winget`) if not found
2. Enables Windows long paths (avoids WinError 206)
3. Creates a Python virtual environment (`.venv`)
4. Installs all pip dependencies
5. Downloads InsightFace buffalo_l models (~275 MB)
6. Configures Redis connection (interactive)
7. Generates self-signed SSL certificate for HTTPS

**Run from PowerShell:**
```powershell
.\setup.ps1
```

**Run from Git Bash / WSL:**
```bash
./setup.sh
```

**Optional flags:**
```powershell
.\setup.ps1 -SkipPython    # Skip Python installation check
.\setup.ps1 -SkipRedis     # Skip Redis configuration step
```

### Manual Setup
If you prefer to set up manually:

```powershell
# 1. Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt
pip install ml_dtypes==0.5.1 --no-deps   # Post-install fix for onnx/tensorflow compatibility

# 3. Verify InsightFace models exist in insightface_model/models/buffalo_l/
#    Required: det_10g.onnx, 1k3d68.onnx, 2d106det.onnx, genderage.onnx, w600k_r50.onnx
#    Download from: https://github.com/deepinsight/insightface/releases/tag/v0.7

# 4. Configure Redis credentials in face_rec.py (lines 24-26)
```

---

## Running the App
**PowerShell:**
```powershell
.\start_app.ps1
```

**Git Bash / WSL:**
```bash
./start_app.sh
```

**With options:**
```powershell
.\start_app.ps1 -BindHost "0.0.0.0" -Port 8501    # Accessible on LAN
.\start_app.ps1 -InstallDeps                        # Reinstall dependencies first
```

The app opens at: **https://localhost:8501** (or http if SSL is not configured)

> If the virtual environment is not found, `start_app.ps1` automatically runs `setup.ps1` first.

---

## How to Use
### 1. Register Faces
Navigate to **Registration Form** in the sidebar.

1. **Enter name** (first and last) and **select a role** (or create a new one)
2. **Choose capture mode:**
   - **OnlineStreaming** — automatically captures 10 face samples at 1-second intervals
   - **Camera** — manually click "Take Snapshot" for each of the 10 samples
3. **Review samples** — click "Show Samples" to see the 10 captured face crops in a grid
4. **Save** — click "Save Registration" to compute the average 512-d embedding and store it in Redis

> 10 samples are averaged into a single feature vector for more robust recognition.

### 2. Real-Time Attendance
Navigate to **Real-Time Prediction** in the sidebar.

1. The page loads all registered face data from Redis
2. Click **START** to activate the webcam stream
3. Recognized faces show **green bounding boxes** with name and role labels
4. Unrecognized faces show **red bounding boxes** labeled "Unknown"
5. Attendance is automatically logged to Redis every **5 seconds** (deduplicated by name)

> The recognition threshold is 0.5 cosine similarity. Faces below this threshold are marked "Unknown".

### 3. View Reports
Navigate to **Report** in the sidebar.

**Registered Data tab:**
- View all registered name/role pairs
- Select and delete individual entries

**Logs tab:**
- Filter attendance logs by time range: 1 hour, 3 hours, 6 hours, 12 hours, 1 day, 3 days, or 7 days
- View as table or JSON format
- Clear all logs if needed

---

## HTTPS & Webcam Access over LAN
Browsers block camera access on non-HTTPS origins (except `localhost`). If you access the app from another device on the network (e.g., `http://192.168.1.x:8501`), the webcam will **not** work.

The setup script (Step 7) generates a self-signed SSL certificate in `.ssl/` and configures Streamlit to serve over HTTPS. This allows webcam access from any device on the LAN.

**Important:** Since the certificate is self-signed, your browser will show a security warning. Click **Advanced → Proceed** to accept it. This is safe for local/development use.

To access from other devices on the network:
```powershell
.\start_app.ps1 -BindHost "0.0.0.0"
```
Then open `https://<your-ip>:8501` on the other device.

---

## Project Structure
```
├── Home.py                          # Main Streamlit entry page
├── face_rec.py                      # Core: InsightFace model, Redis ops, prediction & registration classes
├── requirements.txt                 # Python dependencies (pinned versions)
├── setup.ps1                        # One-click setup script (PowerShell)
├── setup.sh                         # Bash wrapper for setup.ps1
├── start_app.ps1                    # App launcher (PowerShell)
├── start_app.sh                     # Bash wrapper for start_app.ps1
├── .streamlit/
│   └── config.toml                  # Streamlit server config (port, SSL)
├── .ssl/
│   ├── cert.pem                     # Self-signed SSL certificate (generated)
│   └── key.pem                      # SSL private key (generated)
├── docs/
│   └── system_flowchart.mmd         # Mermaid system architecture diagram
│   └── system_flowchart.png         # Mermaid system architecture diagram image
│   └── system_flowchart.svg         # Mermaid system architecture diagram Scalable Vector Graphics for web
├── helper/
│   ├── helper_funcs.py              # Cosine similarity search, log parsing, WebRTC callbacks
│   ├── redis_db_connect.py          # Redis connection and data retrieval
│   └── webrtc_config.py             # WebRTC ICE server config (STUN/TURN)
├── insightface_model/
│   └── models/
│       └── buffalo_l/               # InsightFace ONNX models (~275 MB total)
│           ├── det_10g.onnx         # Face detection
│           ├── 1k3d68.onnx          # 3D face alignment
│           ├── 2d106det.onnx        # 2D landmark detection
│           ├── genderage.onnx       # Gender & age estimation
│           └── w600k_r50.onnx       # Face recognition (512-d embeddings)
├── pages/
│   ├── 1_Real_Time_Prediction.py    # Live webcam face recognition + attendance logging
│   ├── 2_Registration_form.py       # Face capture and registration UI
│   └── 3_Report.py                  # Attendance reports and data management
└── data/
    └── features_store/              # Optional seed data for pre-loading faces
```

---

## Configuration
### Redis
Redis credentials are configured in `face_rec.py` (lines 24–26):
```python
hostname_endpoint = 'your-redis-host'
port = 17847
password = 'your-redis-password'
```
The setup script can configure these interactively during Step 6.

### WebRTC TURN Server (Optional)
For NAT traversal (remote/cloud deployments), configure TURN credentials via Streamlit secrets (`.streamlit/secrets.toml`):
```toml
[webrtc]
turn_urls = "turn:your-turn-server:3478"
turn_username = "user"
turn_credential = "password"
```
Or via environment variables: `TURN_URLS`, `TURN_USERNAME`, `TURN_CREDENTIAL`.

### Streamlit Server
Server settings in `.streamlit/config.toml`:
```toml
[server]
address = "localhost"
port = 8501
headless = false

sslCertFile = ".ssl/cert.pem"
sslKeyFile = ".ssl/key.pem"
```

---

## Troubleshooting
| Issue | Solution |
|---|---|
| `WinError 206` (filename too long) | Run `setup.ps1` — it enables Windows long paths via registry |
| `onnx` DLL load failure | Ensure `onnx==1.19.0` and `ml_dtypes==0.5.1` are installed |
| `ml_dtypes` conflict with tensorflow | `ml_dtypes` is installed as a post-install step (after tensorflow). Run: `pip install ml_dtypes==0.5.1 --no-deps` |
| Webcam not working over LAN | Access via `https://` (not `http://`). Accept the self-signed certificate warning |
| Webcam not working on localhost | Ensure browser permissions allow camera. Try `http://127.0.0.1:8501` |
| Redis connection failed | Verify credentials in `face_rec.py`. Test with: `redis-cli -h <host> -p <port> -a <password> ping` |
| InsightFace model missing | Run `setup.ps1` — Step 5 downloads buffalo_l models automatically |
| Circular import error | Ensure `helper/helper_funcs.py` uses lazy imports for `face_rec` (inside functions, not at top) |
=======
# attendance-sys-face-reg-app

