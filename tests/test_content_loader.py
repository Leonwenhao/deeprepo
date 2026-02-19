import pytest

from deeprepo.content_loader import load_content, format_content_metadata


TEST_PATH = "tests/test_content"


def test_load_returns_required_keys():
    """load_content returns dict with documents, file_tree, metadata."""
    data = load_content(TEST_PATH)
    assert "documents" in data
    assert "file_tree" in data
    assert "metadata" in data


def test_document_count():
    """All 5 test content files are loaded."""
    data = load_content(TEST_PATH)
    assert data["metadata"]["total_files"] == 5
    assert data["metadata"]["total_documents"] == 5


def test_document_types():
    """File type counts are correct."""
    data = load_content(TEST_PATH)
    types = data["metadata"]["document_types"]
    assert types.get(".md") == 3
    assert types.get(".html") == 1
    assert types.get(".txt") == 1


def test_content_categories():
    """Top-level subdirs detected as categories."""
    data = load_content(TEST_PATH)
    cats = data["metadata"]["content_categories"]
    assert "blog" in cats
    assert "email" in cats
    assert "social" in cats


def test_word_count():
    """Total word count is positive and reasonable."""
    data = load_content(TEST_PATH)
    assert data["metadata"]["total_words"] > 0


def test_date_range():
    """Date range detected from filenames and/or front matter."""
    data = load_content(TEST_PATH)
    dr = data["metadata"]["date_range"]
    assert dr is not None
    assert dr["earliest"] <= "2025-09"


def test_file_tree():
    """File tree string contains expected paths."""
    data = load_content(TEST_PATH)
    tree = data["file_tree"]
    assert "blog" in tree
    assert "brand-guidelines.md" in tree


def test_format_metadata():
    """format_content_metadata produces a non-empty string."""
    data = load_content(TEST_PATH)
    formatted = format_content_metadata(data["metadata"])
    assert isinstance(formatted, str)
    assert len(formatted) > 0
    assert "test_content" in formatted


def test_empty_dir_raises(tmp_path):
    """Empty directory raises ValueError."""
    with pytest.raises(ValueError):
        load_content(str(tmp_path))
