"""
MARK — RAG Memory (Retrieval-Augmented Generation)
Semantic vector-based memory that remembers everything intelligently.
Uses ChromaDB for local vector storage with automatic embedding.
Falls back to TF-IDF if ChromaDB is not available.
"""

import os
import json
import time
import hashlib
import datetime
import math
import re
from collections import Counter


# ─────────────────────────────────────────────
# STORAGE PATHS
# ─────────────────────────────────────────────

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RAG_DIR = os.path.join(_PROJECT_DIR, "rag_data")
_CHROMA_DIR = os.path.join(_RAG_DIR, "chroma_db")
_FALLBACK_FILE = os.path.join(_RAG_DIR, "memory_index.json")

os.makedirs(_RAG_DIR, exist_ok=True)

# ─────────────────────────────────────────────
# BACKEND DETECTION
# ─────────────────────────────────────────────

_chroma_client = None
_collection = None
_use_chroma = False


def _init_chroma():
    """Try to initialize ChromaDB. Falls back to TF-IDF if unavailable."""
    global _chroma_client, _collection, _use_chroma

    if _chroma_client is not None:
        return _use_chroma

    try:
        import chromadb
        _chroma_client = chromadb.PersistentClient(path=_CHROMA_DIR)
        _collection = _chroma_client.get_or_create_collection(
            name="mark_memory",
            metadata={"hnsw:space": "cosine"},
        )
        _use_chroma = True
        print("  ✓ RAG Memory: ChromaDB initialized (semantic search enabled)")
        return True
    except ImportError:
        print("  ⚠ RAG Memory: ChromaDB not installed. Using TF-IDF fallback.")
        print("    Install for better results: pip install chromadb")
        _use_chroma = False
        return False
    except Exception as e:
        print(f"  ⚠ RAG Memory: ChromaDB error ({e}). Using TF-IDF fallback.")
        _use_chroma = False
        return False


# ─────────────────────────────────────────────
# TF-IDF FALLBACK (no dependencies)
# ─────────────────────────────────────────────

_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "he", "in", "is", "it", "its", "of", "on", "or", "she",
    "that", "the", "to", "was", "were", "will", "with", "this", "but",
    "they", "have", "had", "not", "what", "when", "where", "which", "who",
    "how", "do", "does", "did", "can", "could", "would", "should", "may",
    "i", "me", "my", "you", "your", "we", "our", "them", "their",
}


def _tokenize(text):
    """Simple tokenizer: lowercase, split on non-alphanum, remove stop words."""
    words = re.findall(r'[a-z0-9]+', text.lower())
    return [w for w in words if w not in _STOP_WORDS and len(w) > 1]


def _load_fallback_index():
    """Load the TF-IDF fallback index."""
    if not os.path.exists(_FALLBACK_FILE):
        return {"documents": {}, "idf": {}}
    try:
        with open(_FALLBACK_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"documents": {}, "idf": {}}


def _save_fallback_index(index):
    """Save the TF-IDF fallback index."""
    with open(_FALLBACK_FILE, "w") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)


def _update_idf(index):
    """Recompute IDF scores for the fallback index."""
    docs = index["documents"]
    n_docs = len(docs)
    if n_docs == 0:
        index["idf"] = {}
        return

    # Count how many docs contain each term
    df = Counter()
    for doc_id, doc in docs.items():
        terms = set(_tokenize(doc.get("text", "") + " " + doc.get("key", "")))
        for term in terms:
            df[term] += 1

    index["idf"] = {term: math.log(n_docs / count) for term, count in df.items()}


def _tfidf_search(query, index, n_results=5):
    """Search using TF-IDF scoring."""
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    idf = index.get("idf", {})
    docs = index.get("documents", {})

    scores = []
    for doc_id, doc in docs.items():
        doc_text = doc.get("text", "") + " " + doc.get("key", "")
        doc_tokens = _tokenize(doc_text)
        if not doc_tokens:
            continue

        # TF for this document
        tf = Counter(doc_tokens)
        doc_len = len(doc_tokens)

        score = 0.0
        for token in query_tokens:
            if token in tf:
                term_freq = tf[token] / doc_len
                inverse_doc_freq = idf.get(token, 1.0)
                score += term_freq * inverse_doc_freq

        if score > 0:
            scores.append((doc_id, score, doc))

    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:n_results]


# ─────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────

def rag_remember(text="", category="general", source="user"):
    """
    Store a piece of information in RAG memory.
    Automatically embeds and indexes for semantic search.

    Args:
        text: The information to remember
        category: Category tag (e.g., "personal", "work", "preference", "fact", "conversation")
        source: Where this info came from (e.g., "user", "web", "file", "conversation")
    """
    if not text or not text.strip():
        return "Nothing to remember. Provide some text."

    text = text.strip()
    doc_id = hashlib.md5(text.encode()).hexdigest()[:16]
    timestamp = datetime.datetime.now().isoformat()

    metadata = {
        "category": category,
        "source": source,
        "timestamp": timestamp,
        "length": len(text),
    }

    _init_chroma()

    if _use_chroma:
        try:
            # Check if this exact text already exists
            existing = _collection.get(ids=[doc_id])
            if existing and existing["ids"]:
                _collection.update(
                    ids=[doc_id],
                    documents=[text],
                    metadatas=[metadata],
                )
                return f"Memory updated: '{text[:60]}...'" if len(text) > 60 else f"Memory updated: '{text}'"

            _collection.add(
                ids=[doc_id],
                documents=[text],
                metadatas=[metadata],
            )
            count = _collection.count()
            return f"Remembered ({count} total memories): '{text[:60]}...'" if len(text) > 60 else f"Remembered ({count} total): '{text}'"
        except Exception as e:
            print(f"  ✗ ChromaDB add error: {e}")
            # Fall through to TF-IDF fallback

    # TF-IDF fallback
    index = _load_fallback_index()
    index["documents"][doc_id] = {
        "text": text,
        "key": category,
        "metadata": metadata,
    }
    _update_idf(index)
    _save_fallback_index(index)
    count = len(index["documents"])
    return f"Remembered ({count} total): '{text[:60]}...'" if len(text) > 60 else f"Remembered ({count} total): '{text}'"


def rag_recall(query="", n_results=5):
    """
    Search RAG memory semantically. Returns the most relevant memories.

    Args:
        query: What to search for (natural language)
        n_results: Maximum number of results to return (default 5)
    """
    if not query or not query.strip():
        return "What would you like me to recall?"

    query = query.strip()

    try:
        n_results = int(n_results)
    except (ValueError, TypeError):
        n_results = 5

    _init_chroma()

    if _use_chroma:
        try:
            count = _collection.count()
            if count == 0:
                return "I don't have any memories stored yet, sir."

            results = _collection.query(
                query_texts=[query],
                n_results=min(n_results, count),
            )

            if not results["documents"] or not results["documents"][0]:
                return f"No memories matching '{query}'."

            lines = [f"Found {len(results['documents'][0])} relevant memories:"]
            for i, (doc, meta, dist) in enumerate(zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )):
                relevance = max(0, round((1 - dist) * 100))
                category = meta.get("category", "")
                timestamp = meta.get("timestamp", "")[:10]
                cat_tag = f" [{category}]" if category and category != "general" else ""
                lines.append(f"  {i+1}. ({relevance}% match{cat_tag} {timestamp}) {doc}")

            return "\n".join(lines)
        except Exception as e:
            print(f"  ✗ ChromaDB search error: {e}")

    # TF-IDF fallback
    index = _load_fallback_index()
    if not index["documents"]:
        return "I don't have any memories stored yet, sir."

    results = _tfidf_search(query, index, n_results)
    if not results:
        return f"No memories matching '{query}'."

    lines = [f"Found {len(results)} relevant memories:"]
    for i, (doc_id, score, doc) in enumerate(results):
        category = doc.get("metadata", {}).get("category", "")
        timestamp = doc.get("metadata", {}).get("timestamp", "")[:10]
        cat_tag = f" [{category}]" if category and category != "general" else ""
        text = doc.get("text", "")
        lines.append(f"  {i+1}. (score: {score:.2f}{cat_tag} {timestamp}) {text}")

    return "\n".join(lines)


def rag_forget(query=""):
    """
    Remove memories matching a query.

    Args:
        query: Text to match for deletion
    """
    if not query or not query.strip():
        return "Specify what to forget."

    query = query.strip()
    _init_chroma()

    if _use_chroma:
        try:
            # Search for matching memories
            count = _collection.count()
            if count == 0:
                return "No memories to forget."

            results = _collection.query(
                query_texts=[query],
                n_results=min(5, count),
            )

            if not results["ids"] or not results["ids"][0]:
                return f"No memories matching '{query}'."

            # Delete the closest match
            best_id = results["ids"][0][0]
            best_doc = results["documents"][0][0]
            best_dist = results["distances"][0][0]

            # Only delete if it's a reasonable match (distance < 0.5)
            if best_dist > 0.5:
                return f"No close match for '{query}'. Closest was: '{best_doc[:60]}...'"

            _collection.delete(ids=[best_id])
            remaining = _collection.count()
            return f"Forgotten: '{best_doc[:60]}...' ({remaining} memories remaining)" if len(best_doc) > 60 else f"Forgotten: '{best_doc}' ({remaining} remaining)"
        except Exception as e:
            print(f"  ✗ ChromaDB delete error: {e}")

    # TF-IDF fallback
    index = _load_fallback_index()
    results = _tfidf_search(query, index, 1)
    if not results:
        return f"No memories matching '{query}'."

    doc_id = results[0][0]
    doc_text = results[0][2].get("text", "")
    del index["documents"][doc_id]
    _update_idf(index)
    _save_fallback_index(index)
    remaining = len(index["documents"])
    return f"Forgotten: '{doc_text[:60]}...' ({remaining} remaining)" if len(doc_text) > 60 else f"Forgotten: '{doc_text}' ({remaining} remaining)"


def rag_list(category=""):
    """
    List all stored memories, optionally filtered by category.

    Args:
        category: Optional category filter (e.g., "personal", "work")
    """
    _init_chroma()

    if _use_chroma:
        try:
            count = _collection.count()
            if count == 0:
                return "No memories stored yet, sir."

            # Get all memories
            if category:
                results = _collection.get(
                    where={"category": category},
                )
            else:
                results = _collection.get()

            if not results["documents"]:
                if category:
                    return f"No memories in category '{category}'."
                return "No memories stored yet."

            lines = [f"RAG Memory ({len(results['documents'])} memories{f' in [{category}]' if category else ''}):", "─" * 40]
            for doc, meta in zip(results["documents"], results["metadatas"]):
                cat = meta.get("category", "general")
                ts = meta.get("timestamp", "")[:10]
                preview = doc[:80] + "..." if len(doc) > 80 else doc
                lines.append(f"  [{cat}] {ts} — {preview}")

            return "\n".join(lines)
        except Exception as e:
            print(f"  ✗ ChromaDB list error: {e}")

    # TF-IDF fallback
    index = _load_fallback_index()
    docs = index.get("documents", {})
    if not docs:
        return "No memories stored yet, sir."

    if category:
        docs = {k: v for k, v in docs.items() if v.get("metadata", {}).get("category") == category}
        if not docs:
            return f"No memories in category '{category}'."

    lines = [f"RAG Memory ({len(docs)} memories{f' in [{category}]' if category else ''}):", "─" * 40]
    for doc_id, doc in docs.items():
        cat = doc.get("metadata", {}).get("category", "general")
        ts = doc.get("metadata", {}).get("timestamp", "")[:10]
        text = doc.get("text", "")
        preview = text[:80] + "..." if len(text) > 80 else text
        lines.append(f"  [{cat}] {ts} — {preview}")

    return "\n".join(lines)


def rag_auto_remember(conversation_text="", user_name="sir"):
    """
    Automatically extract and remember important information from a conversation.
    Called internally by the AI engine to build knowledge over time.

    Args:
        conversation_text: The conversation text to analyze
        user_name: How the user is addressed
    """
    if not conversation_text or len(conversation_text) < 20:
        return "Nothing notable to remember."

    # Simple heuristic extraction of memorable facts
    patterns = [
        (r"(?:my|i'm|i am|i work|i live|i like|i prefer|i use|i have)\s+(.{5,80})", "personal"),
        (r"(?:password|api.?key|token|secret)\s+(?:is|for|:)\s+(.{3,50})", "credential"),
        (r"(?:remember|note|save|store)\s+(?:that\s+)?(.{5,100})", "explicit"),
        (r"(?:email|phone|address|birthday|meeting)\s+(?:is|:)\s+(.{3,60})", "contact"),
        (r"(?:deadline|due|by|before)\s+(.{5,60})", "deadline"),
    ]

    found = []
    for pattern, category in patterns:
        matches = re.findall(pattern, conversation_text, re.IGNORECASE)
        for match in matches:
            clean = match.strip().rstrip(".,!?")
            if len(clean) > 5:
                found.append((clean, category))

    if not found:
        return "No notable information to auto-remember."

    results = []
    for text, category in found[:5]:  # max 5 auto-memories per call
        result = rag_remember(text, category=category, source="conversation")
        results.append(result)

    return f"Auto-remembered {len(results)} items from conversation."


def rag_stats():
    """Get statistics about the RAG memory system."""
    _init_chroma()

    if _use_chroma:
        try:
            count = _collection.count()
            all_data = _collection.get()

            categories = Counter()
            sources = Counter()
            for meta in all_data.get("metadatas", []):
                categories[meta.get("category", "general")] += 1
                sources[meta.get("source", "unknown")] += 1

            lines = [
                f"RAG Memory Statistics",
                f"─" * 40,
                f"Backend: ChromaDB (semantic search)",
                f"Total memories: {count}",
                f"Categories: {dict(categories)}",
                f"Sources: {dict(sources)}",
                f"Storage: {_CHROMA_DIR}",
            ]
            return "\n".join(lines)
        except Exception as e:
            return f"Error getting stats: {e}"

    # TF-IDF fallback stats
    index = _load_fallback_index()
    count = len(index.get("documents", {}))
    vocab = len(index.get("idf", {}))
    return f"RAG Memory Statistics\n{'─' * 40}\nBackend: TF-IDF (fallback)\nTotal memories: {count}\nVocabulary size: {vocab}\nStorage: {_FALLBACK_FILE}"
