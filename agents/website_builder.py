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

WEBSITE_SYSTEM_PROMPT = """You are an expert frontend web developer. Given a website description, generate a COMPLETE, production-quality, single-page website.

You MUST output a valid JSON object with exactly these 3 keys:
{
  "html": "the full HTML content (do NOT include <link> or <script> tags for style.css/script.js — they will be injected automatically)",
  "css": "the complete CSS stylesheet",
  "js": "the complete JavaScript (can be empty string if not needed)"
}

Rules:
- Output ONLY the JSON. No markdown, no explanation.
- The HTML must be a complete document with <!DOCTYPE html>, <head>, <body>.
- Do NOT include <link href="style.css"> or <script src="script.js"> — they are auto-injected.
- Use modern, beautiful design: CSS Grid/Flexbox, smooth gradients, subtle shadows, rounded corners.
- Use a cohesive color palette. Prefer dark themes with vibrant accents unless told otherwise.
- Add proper Google Fonts (import via @import in CSS).
- Make it fully responsive (mobile-friendly).
- Include hover effects, transitions, and micro-animations.
- The website must be COMPLETE and FUNCTIONAL — not a skeleton.
- For interactive features (calendar, calculator, todo, etc.), write full working JavaScript.
- The design should look premium and modern — not basic or generic.
"""


def _generate_website_json(description):
    """Call AI to generate website files as JSON."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    messages = [
        {"role": "system", "content": WEBSITE_SYSTEM_PROMPT},
        {"role": "user", "content": f"Build this website: {description}"},
    ]

    for model in MODELS:
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json={"model": model, "messages": messages, "max_tokens": 8192, "temperature": 0.3},
                timeout=30,
            )
            if resp.status_code == 200:
                content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                if content:
                    # Strip markdown fences if present
                    if content.startswith("```"):
                        lines = content.split("\n")
                        if lines[-1].strip() == "```":
                            lines = lines[1:-1]
                        else:
                            lines = lines[1:]
                        content = "\n".join(lines)
                    return json.loads(content)
            elif resp.status_code in (402, 404):
                continue
            elif resp.status_code == 429:
                import time
                time.sleep(2)
                continue
        except json.JSONDecodeError:
            continue
        except Exception:
            continue
    return None


def _inject_links(html, has_css, has_js):
    """Inject <link> and <script> tags into the HTML <head> and <body>."""
    css_tag = '<link rel="stylesheet" href="style.css">'
    js_tag = '<script src="script.js"></script>'

    # Inject CSS link before </head>
    if has_css:
        if "</head>" in html:
            html = html.replace("</head>", f"    {css_tag}\n</head>")
        else:
            html = f"{css_tag}\n{html}"

    # Inject JS script before </body>
    if has_js:
        if "</body>" in html:
            html = html.replace("</body>", f"    {js_tag}\n</body>")
        else:
            html = f"{html}\n{js_tag}"

    return html


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
        # Remove filler words
        skip = {"a", "an", "the", "make", "build", "create", "website", "site", "page", "web", "for", "me", "my"}
        clean = [w for w in words if w.isalnum() and w not in skip][:4]
        name = "-".join(clean) if clean else "my-website"

    name = name.replace(" ", "-").lower()

    # Create folder on Desktop
    project_dir = os.path.join(os.path.expanduser("~/Desktop"), name)
    os.makedirs(project_dir, exist_ok=True)

    # Generate website from AI
    print(f"  🌐 Generating website: {description}")
    result = _generate_website_json(description)

    if not result or not isinstance(result, dict):
        return "❌ Failed to generate website. Please try again."

    html_content = result.get("html", "")
    css_content = result.get("css", "")
    js_content = result.get("js", "")

    if not html_content:
        return "❌ AI returned empty HTML. Please try again."

    # Inject <link> and <script> tags
    html_content = _inject_links(html_content, bool(css_content), bool(js_content))

    # Write files
    files_written = []

    html_path = os.path.join(project_dir, "index.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    files_written.append("index.html")

    if css_content:
        css_path = os.path.join(project_dir, "style.css")
        with open(css_path, "w", encoding="utf-8") as f:
            f.write(css_content)
        files_written.append("style.css")

    if js_content:
        js_path = os.path.join(project_dir, "script.js")
        with open(js_path, "w", encoding="utf-8") as f:
            f.write(js_content)
        files_written.append("script.js")

    # Open in default browser
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
