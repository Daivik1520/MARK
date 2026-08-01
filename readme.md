<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:0a0a0a,50:1a1a2e,100:e65100&height=220&section=header&text=M.A.R.K.&fontSize=80&fontColor=ffffff&animation=fadeIn&fontAlignY=38&desc=Machine%20Augmented%20Reality%20Kernel&descSize=18&descAlignY=58&descAlign=50" width="100%" />
</p>

<p align="center">
  <b>Your Personal AI System Controller for macOS</b>
</p>

<p align="center">
  <a href="https://github.com/Daivik1520/MARK/stargazers"><img src="https://img.shields.io/github/stars/Daivik1520/MARK?style=for-the-badge&logo=starship&color=e65100&logoColor=white" /></a>
  <a href="https://github.com/Daivik1520/MARK/blob/main/LICENSE"><img src="https://img.shields.io/github/license/Daivik1520/MARK?style=for-the-badge&logo=opensourceinitiative&color=1a1a2e&logoColor=white" /></a>
  <a href="https://github.com/Daivik1520/MARK/issues"><img src="https://img.shields.io/github/issues/Daivik1520/MARK?style=for-the-badge&logo=gitbook&color=e65100&logoColor=white" /></a>
  <a href="https://github.com/Daivik1520"><img src="https://img.shields.io/badge/creator-Daivik1520-1a1a2e?style=for-the-badge&logo=github&logoColor=white" /></a>
</p>

<br/>

<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=JetBrains+Mono&weight=600&size=16&duration=3000&pause=1000&color=E65100&center=true&vCenter=true&random=false&width=500&lines=%22Hey+MARK%2C+open+VS+Code%22;%22MARK%2C+turn+on+living+room+light%22;%22Set+brightness+to+50%25%22;%22Scrape+top+laptops+to+CSV%22;Voice-controlled+Local+AI+for+macOS" />
</p>

## 🎆 What is M.A.R.K.?

**M.A.R.K. (Machine Augmented Reality Kernel)** is an autonomous, voice-controlled local AI system controller for **macOS**. Think Jarvis — powered by **Gemma 3 4B** with Metal GPU acceleration, operating 100% on-device with zero required API keys. Say "MARK" and it controls system settings, interacts with UI elements on screen, manages IoT smart home devices, executes agentic web scraping and website generation, and speaks back through an audio-reactive 3D particle orb interface.

> 🎤 *"MARK, turn on the living room light"* → Controls smart device via local IoT controller & canvas overlay.  
> 🎤 *"MARK, build me a todo app website"* → Generates HTML/CSS/JS, creates local folder, and opens in browser.  
> 🎤 *"MARK, click on the Submit button"* → Uses 3-layer screen perception (AXUIElement + macOS Vision OCR) to locate and click.

---

## 🚀 One-Click Setup

### Prerequisites
- ✅ **macOS** (Ventura or later, Apple Silicon or Intel)
- ✅ **Python 3.10+** (`python3 --version` to check)
- ✅ **~3 GB free disk** for local model loading
- ❌ **No API keys required** — MARK runs 100% locally on-device

### Setup & Run

```bash
# 1️⃣ Clone the repo
git clone https://github.com/Daivik1520/MARK.git
cd MARK

# 2️⃣ Run the setup script (installs dependencies + launches MARK)
chmod +x start.sh
./start.sh
```

MARK will be live at **http://localhost:3000**

### macOS Permissions

MARK prompts for permissions when needed. Grant them in **System Settings › Privacy & Security**:

| Permission | Needed for | Without it |
|---|---|---|
| **Screen Recording** | Screen analysis (`analyze_screen`, vision OCR clicks) | Vision fallback disabled, system control still works |
| **Accessibility** | Native window management, UI element positioning, dictation | Vision OCR fallback used |

> **What `start.sh` does automatically:**
> - Verifies Python & pip installation
> - Installs required dependencies from `requirements.txt`
> - Configures Chromium via Playwright (for scraping & browser copilot)
> - Frees port 3000 if occupied
> - Launches the FastAPI + Socket.IO server

### Running Benchmarks & Evals

MARK includes a dedicated evaluation framework:

```bash
python3 evals/run_evals.py
```

---

## 🌟 What Can MARK Do?

<table>
<tr>
<td width="50%">

### 🧠 100% Local AI & Lexical Router
- **Local Gemma 3 4B Model** (Metal GPU accelerated)
- **Lexical Tool Router**: Dynamically filters 100+ tools down to ~14 per prompt (~350 token budget vs 3,450+ tokens), avoiding context bloat
- **Grammar-Constrained Tool Calling**: Schema-guided generation guarantees clean execution without model hallucinations

### 👁️ 3-Layer Screen Perception
1. **AXUIElement Accessibility**: Exact native macOS UI widget frame & role extraction
2. **macOS Vision.framework OCR**: Built-in, on-device visual text recognition (no Tesseract required)
3. **Gemma 3 Multimodal VQA**: Visual question answering for complex layout questions

</td>
<td width="50%">

### 🛡️ 3-Tier Security & Audit System
- **SAFE**: Instant execution for read-only tools
- **MUTATING**: Recorded in `audit/undo_log.json` with file trash backup (`audit/trash/`) for instant rollback
- **SENSITIVE**: Strict user confirmation policy for terminal execution, code running, and power actions

### 🏠 IoT & Smart Home Controller
- Interactive Smart Home Floorplan & Canvas overlay
- Voice & UI control for Smart Lights, Plugs, Thermostats, TVs, ESP32 nodes
- Virtual Mouse mode (relative movement, D-pad steps, trackpad gestures)

</td>
</tr>
</table>

<table>
<tr>
<td width="50%">

### 🌐 Agentic Automation & Web Tools
- **Website Builder**: Generates full HTML/CSS/JS applications on Desktop
- **Data Extractor**: Playwright + BeautifulSoup scraping to CSV/JSON
- **Ghost Cursor & Vision Click**: Visual automation via mouse & keyboard
- **Universal File Search**: Content-based indexing & TF-IDF search

</td>
<td width="50%">

### 🎙️ Proactive Triggers & Interface
- **Proactive Ambient Triggers**: Speaks up proactively on battery levels, system resource alerts, and reminders
- **Audio-Reactive 3D Particle Orb UI**: WebGL 3D orb with 6 dynamic states (Dormant, Listening, Thinking, Speaking)
- **Command Palette & Hotkeys**: macOS menubar integration + Cmd+Space quick action bar
- **Local Dictation**: Global hotkey dictation directly into active macOS applications

</td>
</tr>
</table>

---

## 🎤 Voice Commands

<div align="center">

### Say **"MARK..."** followed by any command

</div>

| Category | Example Commands |
|----------|-----------------|
| **🏠 Smart Home** | "Turn on the living room light" · "Set thermostat to 72" · "Toggle desk power plug" |
| **🖥️ Apps & Windows** | "Open Safari" · "Launch VS Code" · "Tile windows side by side" · "List open windows" |
| **📂 Files & Search** | "Create folder Project" · "Search documents for budget" · "Clean up my desktop" |
| **🔊 Audio & Display** | "Set volume to 60%" · "Mute audio" · "Set brightness to 80%" · "Dim screen" |
| **🌐 Web & Agents** | "Make a calculator website" · "Scrape laptops from Amazon to CSV" · "Search latest AI news" |
| **👻 Vision & Mouse** | "Click on Settings button" · "Move mouse to 400 300" · "Scroll down" · "Analyze screen" |
| **🧠 Memory & Notes** | "Remember my wifi password is XYZ" · "What is my wifi password?" · "List memories" |
| **⚡ System & Audit** | "Go to sleep" · "Restart system" · "Take screenshot" · "Undo last action" |

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     BROWSER (UI & CANVAS)                        │
│  ┌────────────────┐  ┌─────────────────┐  ┌───────────────────┐  │
│  │ 3D Particle Orb│  │ IoT Floorplan   │  │ Socket.IO Client  │  │
│  └────────────────┘  └─────────────────┘  └─────────┬─────────┘  │
└─────────────────────────────────────────────────────┼────────────┘
                                                      │ WebSocket
┌─────────────────────────────────────────────────────┼────────────┐
│                FASTAPI SERVER + ASYNC CONTROLLER    │            │
│  ┌───────────────┐                                  │            │
│  │ Fast Router   │─── Regex Match ──→ Instant Exec (<100ms)      │
│  │               │                    (No LLM overhead)      │
│  └───────┬───────┘                                               │
│          │ miss                                                  │
│  ┌───────▼───────┐    ┌──────────────────────────────────────┐   │
│  │ Lexical Tool  │───▶│ Gemma 3 Local AI (Metal GPU)         │   │
│  │ Router        │    │ Schema-guided Function Calling       │   │
│  └───────────────┘    └──────────────────┬───────────────────┘   │
│                                          │                       │
│                       ┌──────────────────▼───────────────────┐   │
│                       │ 3-Tier Security & Permission Engine  │   │
│                       │ (SAFE / MUTATING + Undo Log /        │   │
│                       │  SENSITIVE)                          │   │
│                       └──────────────────┬───────────────────┘   │
│                                          │                       │
│                       ┌──────────────────▼───────────────────┐   │
│                       │ 100+ System & Agent Tools            │   │
│                       │ ┌──────────────────────────────────┐ │   │
│                       │ │ 3-Layer Screen Perception        │ │   │
│                       │ │ (AXUIElement + Vision OCR)       │ │   │
│                       │ │ Smart Home / Virtual Mouse       │ │   │
│                       │ │ Web Agents & Scraping            │ │   │
│                       │ └──────────────────────────────────┘ │   │
│                       └──────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
MARK/
├── app.py                    # FastAPI + Async SocketIO web server
├── start.sh                  # One-click setup & run script
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables
│
├── core/                     # Core system architecture
│   ├── ai_engine.py          # Local AI engine interface & execution
│   ├── gemma_vision.py       # Gemma 3 multimodal turn handler
│   ├── tool_router.py        # Lexical tool router (context budget optimization)
│   ├── tool_schemas.py       # 100+ tool JSON schemas
│   ├── tool_executor.py      # Dynamic tool execution dispatcher
│   ├── permissions.py       # 3-tier security policies & undo log
│   ├── screen_sense.py       # 3-layer screen perception (AXUIElement + Vision OCR)
│   ├── fast_router.py        # Sub-100ms regex command router
│   ├── local_llm.py          # llama-cpp / Ollama backend loader
│   ├── system_controller.py  # macOS system control wrappers
│   └── tts_engine.py         # Text-to-speech engine
│
├── agents/                   # Autonomous AI agents
│   ├── website_builder.py    # Generates HTML/CSS/JS websites
│   ├── data_extractor.py     # Playwright web scraping -> CSV/JSON
│   ├── browser_copilot.py    # Interactive browser navigation
│   ├── universal_search.py   # Indexed file content search
│   └── research_agent.py     # Deep research & summarization
│
├── tools/                    # Utility & hardware tools
│   ├── iot_controller.py     # Smart Home device management
│   ├── virtual_mouse.py      # Virtual Mouse & canvas targeting
│   ├── ghost_cursor.py       # GUI mouse/keyboard automation
│   ├── vision_click.py       # OCR element clicking
│   ├── window_manager.py     # macOS window management
│   ├── memory_manager.py     # Persistent RAG memory
│   └── terminal.py           # Sandboxed command line execution
│
├── services/                 # Background services & ambient monitors
│   ├── proactive_triggers.py # Ambient system alerts (battery, reminders)
│   ├── command_palette.py    # macOS menubar & Cmd+Space launcher
│   └── dictation.py          # On-device voice dictation
│
├── evals/                    # Evaluation & test suite
│   ├── cases.py              # Test case definitions
│   └── run_evals.py          # Evaluation runner
│
├── audit/                    # Audit logs & undo vault
│   ├── undo_log.json         # Rollback registry
│   └── trash/                # Preserved pre-mutation files
│
└── static/                   # Web interface assets
    ├── index.html            # Audio-reactive Orb & IoT UI
    ├── css/style.css         # Glassmorphism styling
    └── js/app.js             # Client logic & Socket.IO handlers
```

---

## ⚙️ Configuration

### Required
- None! Core AI and system operations run 100% locally.

### Optional Integrations
| Key | Service | Purpose |
|-----|---------|---------|
| `SERPAPI_KEY` | [serpapi.com](https://serpapi.com) | Live Web Search results |
| `NEWSAPI_KEY` | [newsapi.org](https://newsapi.org) | News Briefings & summaries |

---

## 🔧 Troubleshooting

| Problem | Fix |
|---------|-----|
| **Port 3000 in use** | `lsof -ti:3000 \| xargs kill -9` or let `start.sh` automatically free it |
| **Microphone not detected** | Ensure microphone access is allowed under System Settings → Privacy & Security → Microphone |
| **Screen perception error** | Enable Screen Recording under System Settings → Privacy & Security → Screen Recording |
| **Brightness control** | Run `brew install brightness` if native macOS slider fallback is disabled |

---

## 👨‍💻 Creator

<div align="center">

<img src="https://github.com/Daivik1520.png" width="120" style="border-radius: 50%;">

### **Daivik Reddy**

**🎓 AI Enthusiast | 💻 Full Stack Developer**

<a href="https://github.com/Daivik1520">
  <img src="https://img.shields.io/badge/GitHub-Daivik1520-black?style=for-the-badge&logo=github">
</a>
<a href="mailto:daivik1520@gmail.com">
  <img src="https://img.shields.io/badge/Email-Contact-red?style=for-the-badge&logo=gmail">
</a>
<a href="https://linkedin.com/in/daivik-reddy">
  <img src="https://img.shields.io/badge/LinkedIn-Connect-blue?style=for-the-badge&logo=linkedin">
</a>

</div>

---

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0a0a0a,50:1a1a2e,100:e65100&height=120&section=footer">

**⭐ Star this repo if MARK impressed you!**

<a href="https://github.com/Daivik1520/MARK/stargazers">
  <img src="https://img.shields.io/badge/⭐_Star_on_GitHub-yellow?style=for-the-badge&logo=github&logoColor=white&labelColor=black">
</a>

</div>
