import json
from unittest.mock import patch, MagicMock

import config
import db
import resume_parser


def test_extract_text_from_pdf(tmp_path):
    """Test PDF text extraction with a real tiny PDF."""
    import fitz
    pdf_path = str(tmp_path / "test.pdf")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "John Doe\nPython Developer\n5 years experience")
    doc.save(pdf_path)
    doc.close()

    text = resume_parser.extract_text_from_pdf(pdf_path)
    assert "John Doe" in text
    assert "Python Developer" in text


def test_parse_resume_returns_profile_and_keywords():
    """Test that parse_resume calls Ollama and extracts profile + keywords."""
    mock_response = {
        "message": {
            "content": json.dumps({
                "profile": "Senior Python dev, 5 years, backend focus",
                "keywords": ["Python Developer", "Backend Engineer", "Django"]
            })
        }
    }

    with patch("resume_parser.ollama.chat", return_value=mock_response):
        profile, keywords = resume_parser.parse_resume("fake resume text")

    assert "Python" in profile
    assert "Python Developer" in keywords
    assert len(keywords) == 3


def test_parse_resume_strips_markdown_fences():
    """Test that markdown code fences in LLM output are handled."""
    raw_json = json.dumps({
        "profile": "Dev profile",
        "keywords": ["React", "Node.js"]
    })
    mock_response = {
        "message": {
            "content": f"```json\n{raw_json}\n```"
        }
    }

    with patch("resume_parser.ollama.chat", return_value=mock_response):
        profile, keywords = resume_parser.parse_resume("resume text")

    assert profile == "Dev profile"
    assert keywords == ["React", "Node.js"]


def test_get_or_create_profile_creates_new(tmp_path, monkeypatch):
    """Test that get_or_create_profile parses resume when no profile exists."""
    # Create a tiny PDF
    import fitz
    pdf_path = str(tmp_path / "resume.pdf")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Jane Doe, Data Engineer")
    doc.save(pdf_path)
    doc.close()

    monkeypatch.setattr(config, "RESUME_PATH", pdf_path)

    mock_response = {
        "message": {
            "content": json.dumps({
                "profile": "Data engineer, 3 years",
                "keywords": ["Data Engineer", "SQL", "Spark"]
            })
        }
    }

    with patch("resume_parser.ollama.chat", return_value=mock_response):
        profile, keywords = resume_parser.get_or_create_profile()

    assert "Data engineer" in profile
    assert "Data Engineer" in keywords

    # Verify it was saved to DB
    saved = db.get_profile()
    assert saved is not None
    assert saved["keywords"] == "Data Engineer,SQL,Spark"


def test_get_or_create_profile_returns_existing():
    """Test that get_or_create_profile returns cached profile without calling Ollama."""
    db.save_profile("raw", "Existing profile", "Go,Kubernetes")

    # Should NOT call ollama — if it does, this would fail
    with patch("resume_parser.ollama.chat", side_effect=Exception("should not be called")):
        profile, keywords = resume_parser.get_or_create_profile()

    assert profile == "Existing profile"
    assert keywords == ["Go", "Kubernetes"]


def test_get_or_create_profile_file_not_found(monkeypatch):
    """Test that missing resume file raises FileNotFoundError."""
    monkeypatch.setattr(config, "RESUME_PATH", "/nonexistent/resume.pdf")

    import pytest
    with pytest.raises(Exception):
        resume_parser.get_or_create_profile()
