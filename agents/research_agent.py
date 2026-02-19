"""
MARK — Research Agent
Autonomous multi-URL research: searches, scrapes, summarizes, and saves a formatted report.
"""

import os
import re
import requests
import asyncio
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

MODELS = [
    "deepseek/deepseek-chat-v3-0324:free",
    "google/gemini-2.0-flash-001",
    "meta-llama/llama-4-maverick:free",
]


# ─────────────────────────────────────────────
# WEB SCRAPING (lightweight, no Playwright needed for research)
# ─────────────────────────────────────────────

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def _search_duckduckgo(query, num_results=10):
    """Search DuckDuckGo and return a list of {title, url, snippet}."""
    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        html = resp.text

        results = []
        # Parse result blocks — DDG HTML has class="result__a" for links
        link_pattern = re.compile(
            r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            re.DOTALL
        )
        snippet_pattern = re.compile(
            r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div|span)',
            re.DOTALL
        )

        links = link_pattern.findall(html)
        snippets = snippet_pattern.findall(html)

        for i, (url, title) in enumerate(links[:num_results]):
            # Clean URL (DDG wraps them)
            if "uddg=" in url:
                url = re.search(r'uddg=([^&]+)', url)
                url = requests.utils.unquote(url.group(1)) if url else ""
            
            title = re.sub(r'<[^>]+>', '', title).strip()
            snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else ""

            if url and title:
                results.append({"title": title, "url": url, "snippet": snippet})

        return results
    except Exception as e:
        return []


def _fetch_page_text(url, max_chars=3000):
    """Fetch a URL and extract readable text content."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        resp.raise_for_status()
        html = resp.text

        # Simple HTML to text: remove scripts, styles, tags
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<[^>]+>', ' ', html)
        html = re.sub(r'\s+', ' ', html).strip()

        # Decode HTML entities
        import html as html_lib
        text = html_lib.unescape(html)

        return text[:max_chars]
    except Exception:
        return ""


def _summarize_with_ai(topic, sources_text):
    """Send collected research to AI for summarization."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    system_prompt = """You are a research analyst. Given raw text from multiple web sources about a topic,
write a comprehensive, well-organized research report in Markdown format.

Rules:
- Use proper headings (##, ###) to organize sections
- Include key facts, statistics, and insights
- Cite sources where applicable
- Write in a clear, professional tone
- Include a "Key Takeaways" section at the top
- Include a "Sources" section at the bottom with numbered references
- Be thorough but concise — aim for 500-800 words
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Topic: {topic}\n\nResearch material:\n{sources_text}"},
    ]

    for model in MODELS:
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json={"model": model, "messages": messages, "max_tokens": 4096, "temperature": 0.4},
                timeout=45,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                if content:
                    return content
            elif resp.status_code in (402, 404):
                continue
            elif resp.status_code == 429:
                import time
                time.sleep(2)
                continue
        except Exception:
            continue

    return None


def research_topic(topic, depth="quick"):
    """
    Research a topic by searching the web, scraping pages, and generating a report.
    
    Args:
        topic: What to research
        depth: "quick" (3 URLs) or "deep" (10 URLs)
    
    Returns:
        Summary + file path of saved report
    """
    if not topic:
        return "❌ Please provide a topic to research."

    num_urls = 3 if depth == "quick" else 10

    # Step 1: Search
    results = _search_duckduckgo(topic, num_results=num_urls)
    if not results:
        return f"❌ No search results found for '{topic}'. Please try a different query."

    # Step 2: Scrape each URL
    sources = []
    for i, r in enumerate(results):
        text = _fetch_page_text(r["url"], max_chars=2500)
        if text and len(text) > 100:
            sources.append(f"--- Source {i+1}: {r['title']} ({r['url']}) ---\n{text}\n")

    if not sources:
        # Fall back to snippets
        sources = [f"--- {r['title']} ---\n{r['snippet']}\n" for r in results if r.get("snippet")]

    if not sources:
        return f"❌ Could not extract content for '{topic}'. Try a more specific query."

    # Step 3: Summarize with AI
    combined_text = "\n\n".join(sources)
    # Limit total to ~12000 chars to fit in context
    if len(combined_text) > 12000:
        combined_text = combined_text[:12000]

    report = _summarize_with_ai(topic, combined_text)
    if not report:
        return f"❌ Failed to generate research report. AI models unavailable."

    # Step 4: Save report to Desktop
    safe_name = re.sub(r'[^\w\s-]', '', topic).strip().replace(" ", "_")[:40]
    filename = f"{safe_name}_Report.md"
    filepath = os.path.join(os.path.expanduser("~/Desktop"), filename)

    header = f"# Research Report: {topic}\n\n"
    header += f"*Generated by MARK Research Agent*\n"
    header += f"*Sources: {len(sources)} pages analyzed*\n\n---\n\n"

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(header + report)
    except Exception as e:
        return f"❌ Failed to save report: {e}"

    # Open the report
    try:
        import subprocess
        subprocess.Popen(["open", filepath])
    except Exception:
        pass

    word_count = len(report.split())
    return (
        f"📊 **Research Report Ready**\n\n"
        f"📝 Topic: {topic}\n"
        f"🔍 Sources analyzed: {len(sources)}\n"
        f"📄 Report: ~{word_count} words\n"
        f"💾 Saved to: {filepath}\n\n"
        f"The report has been opened for your review, sir."
    )
