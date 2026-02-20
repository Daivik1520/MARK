<div align="center">

<!-- Animated Header -->
<picture>
  <source media="(prefers-color-scheme: dark)" srcset=""https://capsule-render.vercel.app/api?type=waving&color=0:0a0a0a,50:1a1a2e,100:e65100&height=220&section=header&text=M.A.R.K.&fontSize=80&fontColor=ffffff&animation=fadeIn&fontAlignY=38&desc=Machine%20Augmented%20Reality%20Kernel&descSize=18&descAlignY=58&descAlign=50" width="100%">
  <img alt="M.A.R.K. Header" src="https://capsule-render.vercel.app/api?type=waving&color=0:0a0a0a,50:1a1a2e,100:e65100&height=220&section=header&text=M.A.R.K.&fontSize=80&fontColor=ffffff&animation=fadeIn&fontAlignY=38&desc=Machine%20Augmented%20Reality%20Kernel&descSize=18&descAlignY=58&descAlign=50" width="100%">
</picture>

<p align="center">
  <img src="https://readme-typing-svg.herokuapp.com?font=Fira+Code&pause=1000&color=FF6B35&center=true&vCenter=true&width=600&lines=🎤+Say+%22MARK%22+to+Control+Your+Mac;🌐+Build+Websites+with+Voice;👻+Ghost+Cursor+—+Click+Any+Button+by+Name;📊+Scrape+Web+Data+to+CSV;⚡+FastAPI+%2B+Async+Architecture" alt="M.A.R.K. Features" />
</p>

<!-- Badges -->
<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white">
  <img alt="Platform" src="https://img.shields.io/badge/Platform-macOS-000000?style=for-the-badge&logo=apple&logoColor=white">
  <img alt="AI" src="https://img.shields.io/badge/AI-OpenRouter-FF6B35?style=for-the-badge&logo=openai&logoColor=white">
  <img alt="Server" src="https://img.shields.io/badge/Server-FastAPI+Uvicorn-009688?style=for-the-badge&logo=fastapi&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge">
</p>

<p align="center">
  <a href="#-one-click-setup">🚀 Setup</a> •
  <a href="#-what-can-mark-do">🌟 Features</a> •
  <a href="#-voice-commands">🎤 Commands</a> •
  <a href="#-architecture">🏗️ Architecture</a> •
  <a href="#-creator">👨‍💻 Creator</a>
</p>

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif">

</div>

## 🎆 What is M.A.R.K.?

**M.A.R.K. (Machine Augmented Reality Kernel)** is a voice-controlled AI system for **macOS**. Think Jarvis — say "MARK" and it controls your entire computer, builds websites, scrapes data, searches the web, and talks back with natural speech through a stunning audio-reactive orb interface.

> 🎤 *"MARK, build me a todo app website"* → Creates folder, writes HTML/CSS/JS, opens in browser.  
> 🎤 *"MARK, set brightness to 50"* → Done in 50ms, no AI needed.  
> 🎤 *"MARK, click on the Settings button"* → OCR finds it on screen and clicks.

---

## 🚀 One-Click Setup

### Prerequisites
- ✅ **macOS** (Ventura or later)
- ✅ **Python 3.10+** (`python3 --version` to check)
- ✅ **Free OpenRouter API key** — get one at [openrouter.ai/keys](https://openrouter.ai/keys)

### Setup & Run

```bash
# 1️⃣  Clone the repo
git clone https://github.com/Daivik1520/MARK.git
cd MARK

# 2️⃣  Add your API key to .env
#     Open .env in any editor and set:
#     OPENROUTER_API_KEY=sk-or-v1-your-key-here

# 3️⃣  Run the setup script (installs everything + starts MARK)
chmod +x start.sh
./start.sh
```

That's it. MARK will be live at **http://localhost:5001**

> **What `start.sh` does automatically:**
> - Checks Python & pip
> - Installs all dependencies from `requirements.txt`
> - Sets up Playwright browser (for web scraping)
> - Validates your `.env` config
> - Kills any existing instance on port 5001
> - Launches the server

### Running After Setup

Once set up, you only need:

```bash
./start.sh
```

Or directly:

```bash
python3 app.py
```

---

## 🌟 What Can MARK Do?

<table>
<tr>
<td width="50%">

### 🎤 Voice & Interaction

🎙️ **Always-On Wake Word**
- Say **"MARK"** to activate hands-free
- Fuzzy matching (Levenshtein distance) — catches "Mark", "Marc", "March", even "Park"
- Checks all speech alternatives for best match
- Anti-feedback system prevents self-triggering

✨ **Premium Orb Interface**
- 3D particles orbiting a reactive core
- Audio-reactive — pulses to MARK's voice
- 6 dynamic states: Dormant → Listening → Thinking → Speaking
- Retina-ready Canvas rendering

🔊 **Natural TTS**
- High-quality Edge-TTS neural voices
- Plays through the browser, pauses wake word to prevent feedback

</td>
<td width="50%">

### 💻 System Control

📂 **Apps & Files**
- Open any app by name
- Create/open files and folders
- Search documents by content (TF-IDF ranking)

⚙️ **Hardware**
- Volume: set, mute, unmute
- Brightness: set to any level
- Window management: focus, tile, list, maximize
- Power: sleep, restart, shutdown

🌐 **Web & Media**
- Real-time web search (SerpAPI)
- Play music on Spotify/YouTube
- Send WhatsApp messages
- Open any website

</td>
</tr>
</table>

### 🆕 Phase 5 Features

<table>
<tr>
<td width="50%">

🌐 **Website Builder**
```
"Build me a calendar website"
"Make a todo app page"
"Create a portfolio site"
```
→ Creates folder on Desktop with `index.html`, `style.css`, `script.js`  
→ Opens in browser automatically

📊 **Data Extraction**
```
"Scrape laptops from Amazon"
"Extract top 10 results to CSV"
```
→ Playwright navigates, BeautifulSoup extracts  
→ Saves as CSV/JSON to Desktop

</td>
<td width="50%">

👻 **Ghost Cursor**
```
"Move mouse to 500 300"
"Click on the Submit button" (OCR!)
"Scroll down 5"
"Type hello world"
```
→ PyAutoGUI + macOS Vision OCR  
→ Click any button by its text label

🎯 **Command Palette**
- Press **Cmd+Space** → input dialog
- 🤖 menubar icon with quick actions
- Works without opening the browser

🎙️ **Local Dictation**
- Press **Ctrl+Option+Shift** → macOS dictation
- Types directly into the active app

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
| **🖥️ Apps** | "Open Safari" · "Launch VS Code" · "Focus on Terminal" · "List windows" |
| **📂 Files** | "Create a folder named Project" · "Open file notes.txt" · "Search for budget" |
| **🔊 Audio** | "Set volume to 50" · "Mute" · "Play lofi music on YouTube" |
| **💡 Display** | "Set brightness to 80" · "Dim the screen" |
| **🌐 Web** | "Search for latest AI news" · "Open github.com" · "Who won the match?" |
| **🌐 Build** | "Make a calculator website" · "Build a landing page" |
| **📊 Data** | "Scrape products from Amazon" · "Extract results to CSV" |
| **👻 Cursor** | "Click on Settings" · "Move mouse to 400 300" · "Scroll down" |
| **📝 Code** | "Write a Python sorting algorithm" · "Generate a REST API" |
| **⚡ Power** | "Go to sleep" · "Restart" · "Screenshot" |
| **🧠 Memory** | "Remember my wifi password is XYZ" · "What's my wifi password?" |
| **⏰ Remind** | "Remind me to call Mom in 30 minutes" |

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────┐
│                  BROWSER (UI)                     │
│  ┌───────────┐  ┌──────────┐  ┌───────────────┐ │
│  │ Orb Canvas│  │Speech API│  │ Socket.IO v4  │ │
│  └───────────┘  └──────────┘  └───────┬───────┘ │
└───────────────────────────────────────┼──────────┘
                                        │ WebSocket
┌───────────────────────────────────────┼──────────┐
│              FastAPI + Uvicorn (Async)            │
│  ┌─────────────┐                                 │
│  │ Fast Router  │─── regex match ──→ Instant exec│
│  │ (< 100ms)   │                    (no AI call) │
│  └──────┬──────┘                                 │
│         │ miss                                   │
│  ┌──────▼──────┐    ┌──────────────────────────┐ │
│  │  AI Engine  │───▶│    Tool Execution         │ │
│  │ (OpenRouter)│    │  ┌──────────────────────┐ │ │
│  │ Gemini/Llama│    │  │ 40+ registered tools │ │ │
│  └─────────────┘    │  └──────────────────────┘ │ │
│                     └──────────────────────────┘ │
│  ┌────────────┐  ┌──────────┐  ┌──────────────┐ │
│  │  TTS Engine│  │Dictation │  │Cmd Palette   │ │
│  │ (Edge-TTS) │  │(native)  │  │(menubar)     │ │
│  └────────────┘  └──────────┘  └──────────────┘ │
└──────────────────────────────────────────────────┘
```

### Key Modules

| Module | File | Purpose |
|--------|------|---------|
| **Fast Router** | `core/fast_router.py` | Regex matching for 30+ commands — executes in <100ms without AI |
| **AI Engine** | `core/ai_engine.py` | OpenRouter API with function calling (Gemini, Llama, DeepSeek) |
| **System Controller** | `core/system_controller.py` | 40+ tools: AppleScript, shell, file ops, hardware |
| **Website Builder** | `agents/website_builder.py` | AI generates full HTML/CSS/JS websites |
| **Data Extractor** | `agents/data_extractor.py` | Playwright + BeautifulSoup web scraping |
| **Ghost Cursor** | `tools/ghost_cursor.py` | PyAutoGUI + macOS Vision OCR for mouse control |
| **Browser Copilot** | `agents/browser_copilot.py` | AI-driven Playwright browser automation |
| **TTS Engine** | `core/tts_engine.py` | Edge-TTS neural text-to-speech |
| **Command Palette** | `services/command_palette.py` | macOS menubar + Cmd+Space hotkey |

---

## 📁 Project Structure

```
MARK/
├── app.py                    # FastAPI + Async SocketIO server
├── start.sh                  # One-click setup & run script
├── requirements.txt          # Python dependencies
├── .env                      # API keys (not committed)
│
├── core/                     # Core engine
│   ├── ai_engine.py          # AI model interface + function calling
│   ├── fast_router.py        # Regex-based instant command router
│   ├── system_controller.py  # Tool registry + macOS execution
│   ├── tts_engine.py         # Text-to-speech
│   └── context_engine.py     # App context awareness
│
├── agents/                   # AI-powered agents
│   ├── website_builder.py    # Generate full websites
│   ├── data_extractor.py     # Web scraping → CSV/JSON
│   ├── browser_copilot.py    # Browser automation
│   ├── research_agent.py     # Deep topic research
│   ├── code_writer.py        # Code generation
│   ├── web_steerer.py        # Web navigation
│   └── universal_search.py   # File content search
│
├── tools/                    # Utility tools
│   ├── ghost_cursor.py       # Mouse/keyboard control + OCR
│   ├── window_manager.py     # Window tiling & focus
│   ├── memory_manager.py     # Persistent memory
│   ├── reminder_manager.py   # Timed reminders
│   ├── clipboard_manager.py  # Clipboard history
│   ├── digital_janitor.py    # Desktop/Downloads cleanup
│   ├── vision_engine.py      # Screen analysis
│   ├── image_tools.py        # Image editing
│   ├── news_briefing.py      # News summaries
│   ├── password_gen.py       # Password generator
│   ├── phone_tracker.py      # Phone tracking
│   └── code_runner.py        # Execute code snippets
│
├── services/                 # Background services
│   ├── command_palette.py    # Menubar + hotkey
│   ├── dictation.py          # Voice dictation
│   ├── focus_bubble.py       # Focus mode (block distractions)
│   ├── gesture_controller.py # Gesture handling
│   ├── proactive_monitor.py  # System health alerts
│   └── routines.py           # Automated routines
│
└── static/                   # Frontend
    ├── index.html            # Main page
    ├── css/style.css         # Styling
    └── js/app.js             # UI logic, orb, wake word
```

---

## ⚙️ Configuration

### Required

| Key | Get it from | Purpose |
|-----|-------------|---------|
| `OPENROUTER_API_KEY` | [openrouter.ai/keys](https://openrouter.ai/keys) | AI models (free tier available) |

### Optional

| Key | Get it from | Purpose |
|-----|-------------|---------|
| `SERPAPI_KEY` | [serpapi.com](https://serpapi.com) | Web search results |
| `NEWSAPI_KEY` | [newsapi.org](https://newsapi.org) | News briefings |

---

## 🔧 Troubleshooting

| Problem | Fix |
|---------|-----|
| **Port 5001 in use** | `lsof -ti:5001 \| xargs kill -9` then try again |
| **Pip install fails** | Add `--break-system-packages` flag or use a virtualenv |
| **Wake word not detecting** | Check microphone permissions in System Settings → Privacy → Microphone |
| **No sound from MARK** | Ensure browser tab isn't muted, check volume |
| **Website builder fails** | AI models may be rate-limited — wait 30s and try again |
| **Brightness not working** | Install: `brew install brightness` |

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
