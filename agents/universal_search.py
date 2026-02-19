"""
MARK — Universal Search (Semantic Desktop Search)
Finds files by CONTENT, not filename. Uses TF-IDF for fast relevance ranking.
Pure Python — no external ML dependencies.
"""

import os
import re
import math
import time
from collections import Counter, defaultdict


# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

SEARCHABLE_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".html", ".css", ".json",
    ".csv", ".xml", ".yaml", ".yml", ".sh", ".bash", ".sql",
    ".java", ".cpp", ".c", ".go", ".rs", ".rb", ".swift", ".kt",
    ".log", ".ini", ".cfg", ".conf", ".env", ".toml",
    ".jsx", ".tsx", ".vue", ".svelte",
}

DEFAULT_DIRECTORIES = [
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Downloads"),
]

MAX_FILE_SIZE = 500_000   # 500KB — skip huge files
MAX_FILES = 5000          # Safety cap
SNIPPET_LENGTH = 200      # Preview snippet size


# ─────────────────────────────────────────────
# TF-IDF ENGINE (Pure Python)
# ─────────────────────────────────────────────

class SearchIndex:
    """In-memory TF-IDF search index for local files."""

    def __init__(self):
        self.documents = {}       # filepath -> raw text
        self.doc_tokens = {}      # filepath -> list of tokens
        self.idf = {}             # term -> IDF score
        self.doc_count = 0
        self.last_indexed = 0
        self.index_age_max = 300  # Re-index every 5 minutes

    def _tokenize(self, text):
        """Convert text to lowercase tokens, removing punctuation."""
        text = text.lower()
        # Split on non-alphanumeric (keep underscores for code)
        tokens = re.findall(r'[a-z0-9_]+', text)
        # Remove very short tokens and stop words
        stop_words = {
            "the", "a", "an", "is", "it", "in", "on", "at", "to", "of",
            "and", "or", "for", "with", "as", "by", "from", "this", "that",
            "be", "are", "was", "were", "has", "have", "had", "do", "does",
            "not", "but", "if", "else", "then", "so", "up", "out", "no",
            "can", "will", "would", "should", "could", "may", "might",
            "def", "class", "import", "return", "self", "none", "true", "false",
        }
        return [t for t in tokens if len(t) > 2 and t not in stop_words]

    def _read_file(self, filepath):
        """Read a file's text content safely."""
        try:
            size = os.path.getsize(filepath)
            if size > MAX_FILE_SIZE:
                return None

            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception:
            return None

    def _scan_directory(self, directory):
        """Recursively find all searchable files in a directory."""
        files = []
        try:
            for root, dirs, filenames in os.walk(directory, topdown=True):
                # Skip hidden directories and common non-useful dirs
                dirs[:] = [d for d in dirs if not d.startswith(".")
                          and d not in {"node_modules", "__pycache__", ".git", "venv",
                                       "env", ".venv", "build", "dist", ".cache"}]

                for fname in filenames:
                    if len(files) >= MAX_FILES:
                        return files
                    ext = os.path.splitext(fname)[1].lower()
                    if ext in SEARCHABLE_EXTENSIONS and not fname.startswith("."):
                        files.append(os.path.join(root, fname))
        except PermissionError:
            pass
        return files

    def build_index(self, directories=None):
        """Build or rebuild the search index from the specified directories."""
        if directories is None:
            directories = DEFAULT_DIRECTORIES

        self.documents.clear()
        self.doc_tokens.clear()

        # Collect all files
        all_files = []
        for d in directories:
            d = os.path.expanduser(d)
            if os.path.isdir(d):
                all_files.extend(self._scan_directory(d))

        # Read and tokenize each file
        doc_freq = defaultdict(int)  # term -> number of docs containing it

        for filepath in all_files:
            content = self._read_file(filepath)
            if content and len(content.strip()) > 10:
                tokens = self._tokenize(content)
                if tokens:
                    self.documents[filepath] = content
                    self.doc_tokens[filepath] = tokens
                    # Count document frequency for IDF
                    unique_terms = set(tokens)
                    for term in unique_terms:
                        doc_freq[term] += 1

        self.doc_count = len(self.documents)

        # Compute IDF: log(N / df)
        self.idf = {}
        for term, df in doc_freq.items():
            self.idf[term] = math.log((self.doc_count + 1) / (df + 1)) + 1

        self.last_indexed = time.time()
        return self.doc_count

    def search(self, query, top_k=10):
        """
        Search the index for documents matching the query.
        Returns list of (filepath, score, snippet).
        """
        # Re-index if stale
        if time.time() - self.last_indexed > self.index_age_max or not self.documents:
            self.build_index()

        if not self.documents:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # Compute TF-IDF scores for each document
        scores = {}
        for filepath, tokens in self.doc_tokens.items():
            tf = Counter(tokens)
            total_terms = len(tokens)
            score = 0.0

            for qt in query_tokens:
                if qt in tf:
                    # TF: term frequency in document (normalized)
                    term_tf = tf[qt] / total_terms
                    # IDF: inverse document frequency
                    term_idf = self.idf.get(qt, 1.0)
                    score += term_tf * term_idf

            if score > 0:
                scores[filepath] = score

        # Sort by score descending
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        # Build results with snippets
        results = []
        for filepath, score in ranked:
            content = self.documents.get(filepath, "")
            snippet = self._extract_snippet(content, query_tokens)
            results.append((filepath, round(score, 4), snippet))

        return results

    def _extract_snippet(self, content, query_tokens):
        """Extract a relevant snippet around the first query term match."""
        content_lower = content.lower()
        best_pos = len(content)

        for token in query_tokens:
            pos = content_lower.find(token)
            if pos != -1 and pos < best_pos:
                best_pos = pos

        if best_pos >= len(content):
            # No direct match found — return beginning
            return content[:SNIPPET_LENGTH].strip() + "..."

        # Extract snippet centered on the match
        start = max(0, best_pos - 60)
        end = min(len(content), best_pos + SNIPPET_LENGTH)
        snippet = content[start:end].strip()

        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet += "..."

        return snippet


# ─────────────────────────────────────────────
# SINGLETON INDEX
# ─────────────────────────────────────────────

_index = SearchIndex()


def search_content(query, directories=""):
    """
    Search local files by content using semantic TF-IDF matching.
    
    Args:
        query: What to search for (natural language)
        directories: Comma-separated directories to search (default: ~/Documents, ~/Desktop, ~/Downloads)
    
    Returns:
        Formatted list of matching files with relevance scores and snippets
    """
    if not query:
        return "❌ Please provide a search query."

    # Parse directories
    if directories and directories.strip():
        dirs = [d.strip() for d in directories.split(",") if d.strip()]
    else:
        dirs = None  # Use defaults

    # Ensure index is built
    if not _index.documents:
        count = _index.build_index(dirs)
    else:
        count = _index.doc_count

    # Search
    results = _index.search(query, top_k=8)

    if not results:
        return f"🔍 No files found matching '{query}' across {count} indexed files."

    # Format output
    lines = [f"🔍 **Search Results for '{query}'**\n"]
    lines.append(f"📂 Indexed {count} files\n")

    for i, (filepath, score, snippet) in enumerate(results, 1):
        rel_path = filepath.replace(os.path.expanduser("~"), "~")
        filename = os.path.basename(filepath)
        # Clean snippet for display
        snippet_clean = snippet.replace("\n", " ").strip()
        if len(snippet_clean) > 150:
            snippet_clean = snippet_clean[:150] + "..."

        lines.append(f"**{i}. {filename}** (relevance: {score})")
        lines.append(f"   📁 {rel_path}")
        lines.append(f"   📝 {snippet_clean}\n")

    return "\n".join(lines)
