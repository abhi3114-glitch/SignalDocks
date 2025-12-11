# SignalDock

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Frontend](https://img.shields.io/badge/frontend-Next.js%2014-black)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey)

**SignalDock** is a local-first, event-driven automation platform for your desktop. It allows you to visually connect system signals (CPU, Network, Clipboard, Window Focus) to powerful actions (File Ops, Shell Scripts, Notifications) without writing a single line of code.

Think of it as **IFTTT** or **Zapier**, but running entirely on your local machine with deep system integration.

---

## Key Features

### Signal Engine (Triggers)
The backend constantly monitors your system for state changes:
- **System**: CPU, RAM, Battery, Network Bandwidth.
- **Input**: Clipboard content, Microphone peak levels.
- **Context**: Active Window Title, Process Focus.
- **Filesystem**: Real-time file creation/modification (Watchdog).

### Action Engine (Executors)
When triggers fire, SignalDock executes actions with robust permission gating:
- **Shell**: Execute PowerShell/Bash scripts (with output capture).
- **Files**: Create, Copy, Move, Archive, Delete files.
- **Network**: Toggle WiFi/Ethernet adapters (Auto-UAC elevation).
- **Process**: Suspend/Resume/Kill applications.
- **Notifications**: Native system toasts.

### Visual Pipeline Editor
- **Drag-and-Drop**: React Flow-based editor.
- **Live Preview**: Watch data flow through nodes in real-time.
- **Logic**: Boolean Filters, Time Windows, Transformers.

---

## Architecture

SignalDock uses a decoupled architecture for maximum stability and performance:

- **Backend**: Python (FastAPI + AsyncIO). Handles system hooks, WebSocket streaming, and pipeline execution.
- **Frontend**: TypeScript (Next.js + Zustand). Provides the visual editor and real-time monitoring dashboard.
- **Communication**: Two-way WebSocket connection for sub-millisecond event transmission.

---

## Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+

### 1. Installation

**Backend Setup**
```bash
cd backend
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

**Frontend Setup**
```bash
cd frontend
npm install
```

### 2. Running the Application

**Start the Engine (Backend)**
```bash
cd backend
python main.py
# Server starts at http://localhost:8000
```

**Start the Dashboard (Frontend)**
```bash
cd frontend
npm run dev
# Dashboard opens at http://localhost:3000
```

---

## Verification & Testing

SignalDock comes with built-in diagnostic scripts to verify system integration on your machine.

**1. Test Actions (Active)**
Verify that SignalDock has permission to execute commands and manipulate files:
```bash
# Run from /backend directory
python test_features.py
```
*Creates a `verified_features.log` file as proof of execution.*

**2. Test Sources (Passive)**
Verify that SignalDock is "seeing" your system correctly:
```bash
# Run from /backend directory
python test_sources.py
```
*Interactive script that prints real-time Clipboard, Window, and CPU events.*

---

## Security & Permissions

Your privacy is paramount. SignalDock runs **locally**.
Sensitive features (Shell, File Ops, Mic, Clipboard) are gated by `backend/config.py`.

```python
# config.py
class PermissionConfig(BaseSettings):
    clipboard_enabled: bool = True      # Set False to disable
    shell_execution_enabled: bool = True # Set False to disable
    # ...
```

---

## Project Structure

```
SignalDocks/
├── backend/
│   ├── main.py                 # Core Engine
│   ├── signals/                # Monitoring Modules (cpu.py, network.py...)
│   ├── actions/                # Executors (shell.py, file_ops.py...)
│   └── pipeline/               # BFS Logic & Filter Engine
├── frontend/
│   ├── src/components/         # React Components
│   ├── src/stores/             # State Management (Zustand)
│   └── src/app/                # Next.js Pages
```

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License
[MIT](https://choosealicense.com/licenses/mit/)
