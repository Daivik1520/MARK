#!/bin/bash
# ═══════════════════════════════════════════════
#  M.A.R.K. — One-Click Setup & Run
#  Machine Augmented Reality Kernel
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
echo "    ╚══════════════════════════════════════╝"
echo -e "${NC}"

# ─── Check Python ───
echo -e "${CYAN}[1/5]${NC} Checking Python..."
if command -v python3 &>/dev/null; then
    PY=$(python3 --version 2>&1)
    echo -e "  ${GREEN}✓${NC} $PY"
else
    echo -e "  ${RED}✗ Python 3 not found!${NC}"
    echo "  Install it: brew install python3"
    exit 1
fi

# ─── Check pip ───
echo -e "${CYAN}[2/5]${NC} Checking pip..."
if python3 -m pip --version &>/dev/null; then
    echo -e "  ${GREEN}✓${NC} pip available"
else
    echo -e "  ${RED}✗ pip not found!${NC}"
    echo "  Install it: python3 -m ensurepip"
    exit 1
fi

# ─── Install dependencies ───
echo -e "${CYAN}[3/5]${NC} Installing dependencies..."
python3 -m pip install -r requirements.txt --break-system-packages -q 2>/dev/null || \
python3 -m pip install -r requirements.txt -q 2>/dev/null || \
pip3 install -r requirements.txt -q 2>/dev/null
echo -e "  ${GREEN}✓${NC} All dependencies installed"

# ─── Install Playwright browsers (for web scraping/browser copilot) ───
echo -e "${CYAN}[4/5]${NC} Setting up Playwright browsers..."
python3 -m playwright install chromium 2>/dev/null && \
    echo -e "  ${GREEN}✓${NC} Chromium browser ready" || \
    echo -e "  ${ORANGE}⚠${NC} Playwright setup skipped (browser features may not work)"

# ─── Check .env file ───
echo -e "${CYAN}[5/5]${NC} Checking configuration..."
if [ -f ".env" ]; then
    if grep -q "your_openrouter_api_key_here" .env 2>/dev/null; then
        echo -e "  ${RED}✗ OPENROUTER_API_KEY not set in .env!${NC}"
        echo ""
        echo -e "  ${BOLD}To fix:${NC}"
        echo "  1. Get a free API key at: https://openrouter.ai/keys"
        echo "  2. Edit the .env file: nano .env"
        echo "  3. Replace 'your_openrouter_api_key_here' with your key"
        echo "  4. Run this script again"
        echo ""
        exit 1
    fi
    echo -e "  ${GREEN}✓${NC} .env configured"
else
    echo -e "  ${ORANGE}⚠${NC} No .env file found — creating template..."
    cat > .env << 'EOF'
# MARK AI System Controller - Environment Configuration
# Get your free key at: https://openrouter.ai/keys
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Optional: SerpAPI for web search (https://serpapi.com)
SERPAPI_KEY=

# Optional: NewsAPI for news briefings (https://newsapi.org)
NEWSAPI_KEY=
EOF
    echo -e "  ${RED}✗ Please edit .env and add your OPENROUTER_API_KEY${NC}"
    echo "  Get one free at: https://openrouter.ai/keys"
    echo ""
    exit 1
fi

# ─── Kill existing MARK if running ───
if lsof -ti:5001 &>/dev/null; then
    echo ""
    echo -e "  ${ORANGE}⚠${NC} Port 5001 already in use — stopping old instance..."
    lsof -ti:5001 | xargs kill -9 2>/dev/null
    sleep 1
fi

# ─── Launch ───
echo ""
echo -e "${GREEN}${BOLD}    ✅ Setup complete! Starting M.A.R.K...${NC}"
echo ""
echo -e "${ORANGE}${BOLD}"
echo "    ╔══════════════════════════════════════╗"
echo "    ║         M.A.R.K. IS LIVE             ║"
echo "    ║     http://localhost:5001             ║"
echo "    ║     Press Ctrl+C to stop             ║"
echo "    ╚══════════════════════════════════════╝"
echo -e "${NC}"

python3 app.py
