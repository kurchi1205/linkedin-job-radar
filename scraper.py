import re
import time
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

import db


class LinkedInJobScraper:
    """Scrapes public LinkedIn job listings. No authentication required."""

    def __init__(self):
        self.base_url = "https://www.linkedin.com/jobs/search"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        })

    def _extract_job_id(self, url: str) -> str:
        # Try /jobs/view/12345 (pure numeric)
        match = re.search(r"/jobs/view/(\d+)", url)
        if match:
            return match.group(1)
        # Try /jobs/view/some-slug-12345/ (slug ending with numeric ID)
        match = re.search(r"/jobs/view/.*?-(\d+)", url)
        if match:
            return match.group(1)
        # Try currentJobId=12345 query param
        match = re.search(r"currentJobId=(\d+)", url)
        if match:
            return match.group(1)
        # Last resort — grab any trailing numeric segment from the path
        match = re.search(r"/(\d+)/?(?:\?|$)", url)
        if match:
            return match.group(1)
        return ""

    def _parse_job_card(self, card) -> Optional[Dict]:
        try:
            link_elem = (
                card.find("a", class_="base-card__full-link")
                or card.find("a", href=re.compile(r"/jobs/view/"))
            )
            if not link_elem:
                return None

            job_link = link_elem.get("href", "")
            job_id = self._extract_job_id(job_link)
            if not job_id:
                return None
            
            # Skip if already in DB
            if db.job_exists(job_id):
                return None

            title_elem = (
                card.find("h3", class_="base-search-card__title")
                or card.find("span", class_="sr-only")
            )
            title = title_elem.get_text(strip=True) if title_elem else "Unknown"

            company_elem = (
                card.find("h4", class_="base-search-card__subtitle")
                or card.find("a", class_="hidden-nested-link")
            )
            company = company_elem.get_text(strip=True) if company_elem else "Unknown"

            location_elem = card.find("span", class_="job-search-card__location")
            location = location_elem.get_text(strip=True) if location_elem else "Unknown"

            url = f"https://www.linkedin.com{job_link}" if job_link.startswith("/") else job_link

            return {
                "job_id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "url": url,
            }
        except Exception as e:
            print(f"Error parsing job card: {e}")
            return None

    def search_jobs(self, keywords: List[str], location: str, limit: int = 25) -> List[Dict]:
        """
        Search for jobs on LinkedIn's public jobs page.

        Args:
            keywords: List of keyword strings
            location: Location string
            limit: Max number of jobs to return

        Returns:
            List of new job dicts (not already in DB)
        """
        params = {
            "keywords": " ".join(keywords),
            "location": location,
            "f_TPR": "r604800",  # Past week
            "start": 0,
        }

        jobs = []
        page = 0

        while len(jobs) < limit:
            params["start"] = page * 25

            try:
                response = self.session.get(self.base_url, params=params, timeout=15)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "html.parser")
                job_cards = soup.find_all("div", class_="base-card") or \
                            soup.find_all("div", class_="job-search-card")

                if not job_cards:
                    break
                for card in job_cards:
                    if len(jobs) >= limit:
                        break
                    job = self._parse_job_card(card)
                    if job:
                        jobs.append(job)

                page += 1
                time.sleep(2)

            except requests.exceptions.RequestException as e:
                print(f"Request error: {e}")
                break

        return jobs[:limit]


def scrape_new_jobs(keywords: List[str], location: str, limit: int = 25) -> List[Dict]:
    """Top-level function called by main.py — matches the old interface."""
    scraper = LinkedInJobScraper()
    jobs = scraper.search_jobs(keywords, location, limit)
    print(f"Found {len(jobs)} new jobs")
    return jobs


if __name__ == "__main__":
    db.init_db()
    jobs = scrape_new_jobs(["AI Engineer"], "Singapore", limit=5)
    for job in jobs:
        print(f"  {job['title']} — {job['company']} ({job['location']})")
        print(f"    {job['url']}")
