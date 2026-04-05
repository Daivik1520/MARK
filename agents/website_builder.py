"""
MARK — Website Builder
Generates complete multi-file websites (HTML + CSS + JS) from natural language.
Creates project folder on Desktop and opens in browser.
Powered by local Gemma 2 2B.
"""

import os
import subprocess
from dotenv import load_dotenv

load_dotenv()

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
    """Call local Gemma model. Returns raw text content."""
    try:
        from core.local_llm import local_chat
        response = local_chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=4096,
            temperature=0.3,
        )
        if not response:
            return None
        content = response.strip()
        # Strip markdown code fences if model included them
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[-1].strip() == "```":
                lines = lines[1:-1]
            else:
                lines = lines[1:]
            content = "\n".join(lines)
        print(f"    ✓ Got {len(content)} chars from local Gemma")
        return content
    except Exception as e:
        print(f"    ✗ Website builder AI error: {e}")
        return None


def build_website(description, name=""):
    """
    Generate a complete website from a natural language description.
    Creates a project folder on Desktop with index.html, style.css, script.js.
    """
    if not description:
        return "❌ Please describe what website to build."

    if not name:
        words = description.lower().split()
        skip = {"a", "an", "the", "make", "build", "create", "website", "site", "page", "web", "for", "me", "my"}
        clean = [w for w in words if w.isalnum() and w not in skip][:4]
        name = "-".join(clean) if clean else "my-website"

    name = name.replace(" ", "-").lower()

    project_dir = os.path.join(os.path.expanduser("~/Desktop"), name)
    os.makedirs(project_dir, exist_ok=True)

    task = f"Build this website: {description}"

    print(f"  🌐 [1/3] Generating HTML...")
    html = _call_ai(HTML_PROMPT, task)
    if not html:
        return "❌ Failed to generate HTML. Try again."

    print(f"  🎨 [2/3] Generating CSS...")
    css = _call_ai(CSS_PROMPT, task + "\n\nThe HTML structure is:\n" + html[:1500])
    if not css:
        css = "/* CSS generation failed */\nbody { font-family: sans-serif; margin: 0; padding: 20px; background: #1a1a2e; color: #eee; }"

    print(f"  ⚡ [3/3] Generating JavaScript...")
    js = _call_ai(JS_PROMPT, task + "\n\nThe HTML structure is:\n" + html[:1500])
    if not js:
        js = "// JavaScript generation failed\nconsole.log('Website loaded');"

    if "style.css" not in html:
        html = html.replace("</head>", '    <link rel="stylesheet" href="style.css">\n</head>')
    if "script.js" not in html:
        html = html.replace("</body>", '    <script src="script.js"></script>\n</body>')

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
