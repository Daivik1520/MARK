"""
MARK — Website Builder
Generates complete multi-file websites (HTML + CSS + JS) from natural language.
Creates project folder on Desktop and opens in browser.
"""

import os
import json
import subprocess
import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

MODELS = [
    "deepseek/deepseek-chat-v3-0324:free",
    "google/gemini-2.0-flash-001",
    "meta-llama/llama-4-maverick:free",
]

# ─────────────────────────────────────────────
# GENERATE EACH FILE SEPARATELY (more reliable)
# ─────────────────────────────────────────────

HTML_PROMPT = """You are an expert frontend developer. Generate a COMPLETE, beautiful, production-quality HTML file for the following website.

Rules:
- Output ONLY the raw HTML code. No markdown, no explanations, no code fences.
- Must be a complete HTML document with <!DOCTYPE html>, <head>, <body>.
- Include <link rel="stylesheet" href="style.css"> in <head>.
- Include <script src="script.js"></script> before </body>.
- Use semantic HTML5 elements.
- Include a proper <title>.
- Use Google Fonts via <link> tag if appropriate.
- The page must be fully structured and complete — not a skeleton.
"""

CSS_PROMPT = """You are an expert CSS developer. Generate a COMPLETE, beautiful stylesheet for the website described below.

Rules:
- Output ONLY the raw CSS code. No markdown, no explanations, no code fences.
- Use modern CSS: flexbox, grid, custom properties, smooth transitions.
- Use a dark theme with vibrant accent colors (unless told otherwise).
- Include hover effects, subtle animations, and smooth transitions.
- Make it fully responsive with media queries.
- Use Google Fonts (@import at the top if not linked in HTML).
- The design should look premium and modern — not basic or generic.
- Include a proper reset/normalize at the top.
"""

JS_PROMPT = """You are an expert JavaScript developer. Generate the complete JavaScript for the website described below.

Rules:
- Output ONLY the raw JavaScript code. No markdown, no explanations, no code fences.
- Use modern ES6+ (const/let, arrow functions, template literals).
- If the site is static (portfolio, landing page), output just a comment: // No JavaScript needed
- If the site needs interactivity (todo, calculator, calendar), write FULL working logic.
- Use vanilla JavaScript — no frameworks.
- Add event listeners with DOMContentLoaded.
- Make it production-ready with error handling.
"""


def _call_ai(system_prompt, user_prompt):
    """Call OpenRouter with retry across models. Returns raw text."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    for model in MODELS:
        try:
            print(f"    → Trying {model}...")
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json={"model": model, "messages": messages, "max_tokens": 4096, "temperature": 0.3},
                timeout=25,
            )
            if resp.status_code == 200:
                content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                if content:
                    # Strip markdown code fences if present
                    if content.startswith("```"):
                        lines = content.split("\n")
                        if lines[-1].strip() == "```":
                            lines = lines[1:-1]
                        else:
                            lines = lines[1:]
                        content = "\n".join(lines)
                    print(f"    ✓ Got {len(content)} chars from {model}")
                    return content
            elif resp.status_code in (402, 404):
                print(f"    ✗ {resp.status_code} on {model}, skipping")
                continue
            elif resp.status_code == 429:
                print(f"    ✗ Rate limited on {model}")
                import time
                time.sleep(2)
                continue
            else:
                print(f"    ✗ {resp.status_code} on {model}")
                continue
        except Exception as e:
            print(f"    ✗ Error on {model}: {e}")
            continue

    return None


def build_website(description, name=""):
    """
    Generate a complete website from a natural language description.
    Creates a project folder on Desktop with index.html, style.css, script.js.

    Args:
        description: What the website should be (e.g. "a calendar website")
        name: Optional project folder name (auto-generated if empty)

    Returns:
        Confirmation with folder path
    """
    if not description:
        return "❌ Please describe what website to build."

    # Generate folder name
    if not name:
        words = description.lower().split()
        skip = {"a", "an", "the", "make", "build", "create", "website", "site", "page", "web", "for", "me", "my"}
        clean = [w for w in words if w.isalnum() and w not in skip][:4]
        name = "-".join(clean) if clean else "my-website"

    name = name.replace(" ", "-").lower()

    # Create folder
    project_dir = os.path.join(os.path.expanduser("~/Desktop"), name)
    os.makedirs(project_dir, exist_ok=True)

    task = f"Build this website: {description}"

    # Generate HTML
    print(f"  🌐 [1/3] Generating HTML...")
    html = _call_ai(HTML_PROMPT, task)
    if not html:
        return "❌ Failed to generate HTML. AI models may be rate-limited — try again in a moment."

    # Generate CSS
    print(f"  🎨 [2/3] Generating CSS...")
    css = _call_ai(CSS_PROMPT, task + "\n\nThe HTML structure is:\n" + html[:1500])
    if not css:
        css = "/* CSS generation failed — add your styles here */\nbody { font-family: sans-serif; margin: 0; padding: 20px; background: #1a1a2e; color: #eee; }"

    # Generate JS
    print(f"  ⚡ [3/3] Generating JavaScript...")
    js = _call_ai(JS_PROMPT, task + "\n\nThe HTML structure is:\n" + html[:1500])
    if not js:
        js = "// JavaScript generation failed — add your logic here\nconsole.log('Website loaded');"

    # Ensure HTML has CSS and JS links
    if "style.css" not in html:
        html = html.replace("</head>", '    <link rel="stylesheet" href="style.css">\n</head>')
    if "script.js" not in html:
        html = html.replace("</body>", '    <script src="script.js"></script>\n</body>')

    # Write files
    files_written = []

    with open(os.path.join(project_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    files_written.append("index.html")

    with open(os.path.join(project_dir, "style.css"), "w", encoding="utf-8") as f:
        f.write(css)
    files_written.append("style.css")

    with open(os.path.join(project_dir, "script.js"), "w", encoding="utf-8") as f:
        f.write(js)
    files_written.append("script.js")

    # Open in browser
    html_path = os.path.join(project_dir, "index.html")
    try:
        subprocess.Popen(["open", html_path])
    except Exception:
        pass

    return (
        f"✅ **Website Created!**\n\n"
        f"📂 Folder: {project_dir}\n"
        f"📄 Files: {', '.join(files_written)}\n"
        f"🌐 Opened in browser!\n\n"
        f"To view again: `open {html_path}`"
    )
