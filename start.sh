#!/bin/bash
# ═══════════════════════════════════════════════
#  M.A.R.K. — One-Click Setup & Run
#  Machine Augmented Reality Kernel
#  100% Local AI — Gemma 3 4B (Metal GPU)
# ═══════════════════════════════════════════════

set -e

ORANGE='\033[0;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo ""
echo -e "${ORANGE}${BOLD}"
echo "    ╔══════════════════════════════════════╗"
echo "    ║         M.A.R.K. SETUP               ║"
echo "    ║    Machine Augmented Reality Kernel   ║"
echo "    ║    🧠 Gemma 3 4B (Metal GPU)        ║"
echo "    ╚══════════════════════════════════════╝"
echo -e "${NC}"

# ─── Check Python ───
echo -e "${CYAN}[1/4]${NC} Checking Python..."
if command -v python3 &>/dev/null; then
    PY=$(python3 --version 2>&1)
    echo -e "  ${GREEN}✓${NC} $PY"
else
    echo -e "  ${RED}✗ Python 3 not found!${NC}"
    echo "  Install it: brew install python3"
    exit 1
fi

# ─── Check pip ───
echo -e "${CYAN}[2/4]${NC} Checking pip..."
if python3 -m pip --version &>/dev/null; then
    echo -e "  ${GREEN}✓${NC} pip available"
else
    echo -e "  ${RED}✗ pip not found!${NC}"
    echo "  Install it: python3 -m ensurepip"
    exit 1
fi

# ─── Install dependencies ───
echo -e "${CYAN}[3/4]${NC} Installing dependencies..."
python3 -m pip install -r requirements.txt --break-system-packages -q 2>/dev/null || \
python3 -m pip install -r requirements.txt -q 2>/dev/null || \
pip3 install -r requirements.txt -q 2>/dev/null
echo -e "  ${GREEN}✓${NC} All dependencies installed"

# ─── Install Playwright browsers (for web scraping/browser copilot) ───
echo -e "${CYAN}[4/4]${NC} Setting up Playwright browsers..."
python3 -m playwright install chromium 2>/dev/null && \
    echo -e "  ${GREEN}✓${NC} Chromium browser ready" || \
    echo -e "  ${ORANGE}⚠${NC} Playwright setup skipped (browser features may not work)"

PORT=${PORT:-3000}

# ─── Kill existing MARK if running ───
if lsof -ti:$PORT &>/dev/null; then
    echo ""
    echo -e "  ${ORANGE}⚠${NC} Port $PORT already in use — stopping old instance..."
    lsof -ti:$PORT | xargs kill -9 2>/dev/null
    sleep 1
fi

# ─── Launch ───
echo ""
echo -e "${GREEN}${BOLD}    ✅ Setup complete! Starting M.A.R.K...${NC}"
echo ""
echo -e "${ORANGE}${BOLD}"
echo "    ╔══════════════════════════════════════╗"
echo "    ║         M.A.R.K. IS LIVE             ║"
echo "    ║     http://localhost:$PORT             ║"
echo "    ║     🧠 Gemma 3 4B (Metal GPU)      ║"
echo "    ║     Press Ctrl+C to stop             ║"
echo "    ╚══════════════════════════════════════╝"
echo -e "${NC}"

PORT=$PORT python3 app.py
