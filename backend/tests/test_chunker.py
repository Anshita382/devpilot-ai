"""Tests for the AST-aware chunker."""
from app.rag.chunker import chunk_file, detect_language


def test_detect_language():
    assert detect_language("app/main.py") == "python"
    assert detect_language("src/index.js") == "javascript"
    assert detect_language("Server.java") == "java"
    assert detect_language("main.go") == "go"
    assert detect_language("notes.md") == "markdown"


def test_python_symbol_chunking():
    code = (
        "import os\n\n\n"
        "def alpha(x):\n    return x + 1\n\n\n"
        "class Beta:\n    def method(self):\n        return 2\n"
    )
    chunks = chunk_file("mod.py", code)
    assert chunks, "expected at least one chunk"
    symbols = {c.symbol for c in chunks}
    # The top-level function and class should be recognised as symbols.
    assert any("alpha" in s for s in symbols)
    assert any("Beta" in s for s in symbols)
    for c in chunks:
        assert c.start_line >= 1
        assert c.end_line >= c.start_line


def test_window_fallback_for_plain_text():
    text = "\n".join(f"line {i}" for i in range(200))
    chunks = chunk_file("notes.txt", text)
    assert len(chunks) >= 1
    # Reassembled chunk text should cover the content.
    joined = "\n".join(c.text for c in chunks)
    assert "line 0" in joined and "line 199" in joined
