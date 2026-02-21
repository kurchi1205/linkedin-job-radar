import json
import re

import requests
import ollama

import config
import db


def _extract_doc_id(url):
    """Extract the Google Doc ID from a URL."""
    match = re.search(r"/document/d/([a-zA-Z0-9_-]+)", url)
    if not match:
        raise ValueError(f"Could not extract Doc ID from: {url}")
    return match.group(1)


def fetch_google_doc(url):
    """Fetch plain text from a Google Doc (must be shared as 'anyone with link can view')."""
    doc_id = _extract_doc_id(url)
    export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
    resp = requests.get(export_url, timeout=30)
    resp.raise_for_status()
    return resp.text


def fetch_all_resumes(links):
    """Fetch and combine text from multiple Google Doc links."""
    all_text = []
    for link in links:
        text = fetch_google_doc(link)
        all_text.append(text)
    return "\n\n---\n\n".join(all_text)


def parse_resume(raw_text):
    prompt = f"""You are a career analyst. Analyze this resume and return a JSON object with exactly two keys:

1. "profile": A plain-text summary of the candidate including:
   - Key technical skills and tools
   - Total years of professional experience
   - Seniority level (junior/mid/senior/lead)
   - Domain expertise and industries worked in
   - Types of roles held (e.g. individual contributor, team lead)

2. "keywords": A list of exactly 5 full-time job title keywords to search on LinkedIn.
   Rules for keywords:
   - Each keyword must be a realistic LinkedIn job title that this candidate is qualified for
   - Include seniority prefix where appropriate (e.g. "Senior", "Lead", "Staff")
   - Use titles that employers actually post, not generic terms
   - Do NOT include company names, soft skills, or technologies as keywords
   - Example good keywords: ["Senior Backend Engineer", "Staff Software Engineer", "Lead Platform Engineer", "Senior Python Developer", "Engineering Manager"]
   - Example bad keywords: ["Python", "AWS", "Leadership", "Google", "Backend"]

Resume:
{raw_text}

Respond ONLY with valid JSON. No markdown, no explanation."""

    response = ollama.chat(
        model=config.OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )

    content = response["message"]["content"]

    # Strip markdown code fences if present
    if content.startswith("```"):
        lines = content.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        content = "\n".join(lines)

    result = json.loads(content)
    return result["profile"], result["keywords"]


def get_or_create_profile(overwrite=False):
    existing = db.get_profile()
    if existing and not overwrite:
        keywords = existing["keywords"].split(",")
        return existing["parsed_profile"], keywords

    if not config.RESUME_LINKS:
        raise ValueError(
            "No resume links configured. "
            "Set RESUME_LINKS in .env with your Google Docs URLs."
        )

    raw_text = fetch_all_resumes(config.RESUME_LINKS)
    parsed_profile, keywords = parse_resume(raw_text)

    keywords_str = ",".join(keywords)
    db.save_profile(raw_text, parsed_profile, keywords_str)

    print(f"Resume parsed. Extracted keywords: {keywords}")
    return parsed_profile, keywords


if __name__ == "__main__":
    parsed_profile, keywords = get_or_create_profile(overwrite=True)
    print(parsed_profile)
    print(keywords)