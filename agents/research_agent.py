"""
MARK — Research Agent
Autonomous multi-URL research: searches, scrapes, summarizes, and saves a formatted report.
Powered by local Gemma 2 2B for summarization.
"""

import os
import re
import requests
import asyncio
from dotenv import load_dotenv

load_dotenv()


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

        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<[^>]+>', ' ', html)
        html = re.sub(r'\s+', ' ', html).strip()

        import html as html_lib
        text = html_lib.unescape(html)

        return text[:max_chars]
    except Exception:
        return ""


def _summarize_with_ai(topic, sources_text):
    """Send collected research to local Gemma model for summarization."""
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
    try:
        from core.local_llm import local_chat
        response = local_chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Topic: {topic}\n\nResearch material:\n{sources_text}"},
            ],
            max_tokens=4096,
            temperature=0.4,
        )
        return response.strip() if response else None
    except Exception as e:
        print(f"  ✗ Research AI error: {e}")
        return None


def research_topic(topic, depth="quick"):
    """
    Research a topic by searching the web, scraping pages, and generating a report.
    """
    if not topic:
        return "❌ Please provide a topic to research."

    num_urls = 3 if depth == "quick" else 10

    results = _search_duckduckgo(topic, num_results=num_urls)
    if not results:
        return f"❌ No search results found for '{topic}'. Please try a different query."

    sources = []
    for i, r in enumerate(results):
        text = _fetch_page_text(r["url"], max_chars=2500)
        if text and len(text) > 100:
            sources.append(f"--- Source {i+1}: {r['title']} ({r['url']}) ---\n{text}\n")

    if not sources:
        sources = [f"--- {r['title']} ---\n{r['snippet']}\n" for r in results if r.get("snippet")]

    if not sources:
        return f"❌ Could not extract content for '{topic}'. Try a more specific query."

    combined_text = "\n\n".join(sources)
    if len(combined_text) > 12000:
        combined_text = combined_text[:12000]

    report = _summarize_with_ai(topic, combined_text)
    if not report:
        return f"❌ Failed to generate research report. Local AI unavailable."

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
