import json
import fitz  # pymupdf
import ollama

import config
import db


def extract_text_from_pdf(path):
    doc = fitz.open(path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text


def parse_resume(raw_text):
    prompt = f"""Analyze this resume and return a JSON object with exactly two keys:

1. "profile": A plain-text summary of the candidate including:
   - Key technical skills
   - Years of experience
   - Seniority level (junior/mid/senior)
   - Preferred roles
   - Industries worked in

2. "keywords": A list of 5-10 search keywords that should be used to find matching jobs on LinkedIn.
   These should be specific role titles and key skills (e.g. ["Python Developer", "Backend Engineer", "Data Engineer", "Django", "AWS"]).
   Focus on job titles and core technical skills, not soft skills.

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


def get_or_create_profile():
    existing = db.get_profile()
    if existing:
        keywords = existing["keywords"].split(",")
        return existing["parsed_profile"], keywords

    raw_text = extract_text_from_pdf(config.RESUME_PATH)
    parsed_profile, keywords = parse_resume(raw_text)

    keywords_str = ",".join(keywords)
    db.save_profile(raw_text, parsed_profile, keywords_str)

    print(f"Resume parsed. Extracted keywords: {keywords}")
    return parsed_profile, keywords
