"""
MARK — Web Steerer
Playwright-powered headless browser agent for real web tasks.
"""

import asyncio
import threading
import re
from playwright.async_api import async_playwright


def _run_async(coro):
    """Run an async coroutine synchronously in a dedicated event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _get_page_text(url: str, wait_selector: str = None, timeout_ms: int = 12000) -> str:
    """Open a URL in headless Chromium and return its visible text content."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = await ctx.new_page()
        await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        if wait_selector:
            try:
                await page.wait_for_selector(wait_selector, timeout=5000)
            except Exception:
                pass
        text = await page.evaluate("() => document.body.innerText")
        await browser.close()
        return text[:6000]  # truncate for AI


def web_search_deep(query: str) -> str:
    """
    Perform a real web search via DuckDuckGo and return top results.
    Returns: formatted list of title + snippet + URL
    """
    async def _search():
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            page = await ctx.new_page()
            encoded = query.replace(" ", "+")
            await page.goto(f"https://html.duckduckgo.com/html/?q={encoded}",
                            timeout=12000, wait_until="domcontentloaded")

            results = []
            items = await page.query_selector_all(".result")
            for item in items[:5]:
                try:
                    title_el = await item.query_selector(".result__title")
                    snip_el  = await item.query_selector(".result__snippet")
                    link_el  = await item.query_selector(".result__url")
                    title = (await title_el.inner_text()).strip() if title_el else ""
                    snip  = (await snip_el.inner_text()).strip()  if snip_el  else ""
                    link  = (await link_el.inner_text()).strip()  if link_el  else ""
                    if title:
                        results.append(f"• {title}\n  {snip}\n  🔗 {link}")
                except Exception:
                    continue

            await browser.close()
            return "\n\n".join(results) if results else "No results found."

    try:
        return _run_async(_search())
    except Exception as e:
        return f"Search error: {e}"


def web_get_stock(ticker: str) -> str:
    """
    Fetch stock price and recent info from Yahoo Finance.
    """
    async def _stock():
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            page = await ctx.new_page()
            url = f"https://finance.yahoo.com/quote/{ticker.upper()}/"
            await page.goto(url, timeout=15000, wait_until="domcontentloaded")

            try:
                await page.wait_for_selector('[data-testid="qsp-price"]', timeout=7000)
                price = await page.locator('[data-testid="qsp-price"]').first.inner_text()
                change_el = page.locator('[data-testid="qsp-price-change"]').first
                change = await change_el.inner_text() if await change_el.count() > 0 else ""
                name_el = page.locator('h1').first
                name = await name_el.inner_text() if await name_el.count() > 0 else ticker
                result = f"📈 {name}\nPrice: ${price}\nChange: {change}"
            except Exception:
                # Fallback: scrape raw page text
                text = await page.evaluate("() => document.body.innerText")
                # Try to find price-like pattern
                m = re.search(r'\$?(\d+[\.,]\d+)\s', text)
                result = f"Price info for {ticker}: {m.group(0) if m else 'Could not parse.'}"

            await browser.close()
            return result

    try:
        return _run_async(_stock())
    except Exception as e:
        return f"Stock lookup error: {e}"


def web_book_restaurant(query: str, location: str = "nearby") -> str:
    """
    Search for restaurants matching query near location.
    Returns top results with name, rating, address.
    """
    async def _search():
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            page = await ctx.new_page()
            search_q = f"{query} restaurants {location}"
            encoded = search_q.replace(" ", "+")
            await page.goto(f"https://html.duckduckgo.com/html/?q={encoded}",
                            timeout=12000, wait_until="domcontentloaded")

            results = []
            items = await page.query_selector_all(".result")
            for item in items[:6]:
                try:
                    title_el = await item.query_selector(".result__title")
                    snip_el  = await item.query_selector(".result__snippet")
                    link_el  = await item.query_selector(".result__url")
                    title = (await title_el.inner_text()).strip() if title_el else ""
                    snip  = (await snip_el.inner_text()).strip()  if snip_el  else ""
                    link  = (await link_el.inner_text()).strip()  if link_el  else ""
                    if title and any(word in title.lower() for word in
                                     ["restaurant", "cafe", "bistro", "grill", "kitchen",
                                      "pizza", "sushi", "bar", "diner", "yelp", "zomato"]) \
                            or len(results) < 3:
                        results.append(f"🍽️ {title}\n  {snip}\n  🔗 {link}")
                except Exception:
                    continue

            await browser.close()
            if not results:
                return f"No restaurant results found for '{query}' near {location}."
            return "\n\n".join(results[:4])

    try:
        return _run_async(_search())
    except Exception as e:
        return f"Restaurant search error: {e}"


def web_navigate(url: str) -> str:
    """
    Navigate to a URL and return a summary of the page content.
    """
    if not url.startswith("http"):
        url = "https://" + url
    try:
        text = _run_async(_get_page_text(url))
        # Trim and clean whitespace
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        summary = "\n".join(lines[:60])
        return f"📄 Content from {url}:\n\n{summary}"
    except Exception as e:
        return f"Navigation error: {e}"
