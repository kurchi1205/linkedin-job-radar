import asyncio
import random
import re
import urllib.parse

from playwright.async_api import async_playwright

import config
import db


async def create_browser_context(playwright):
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    )
    # Inject LinkedIn session cookie
    await context.add_cookies([
        {
            "name": "li_at",
            "value": config.LINKEDIN_COOKIE,
            "domain": ".linkedin.com",
            "path": "/",
        }
    ])
    return browser, context


async def _random_delay(min_s=2, max_s=5):
    await asyncio.sleep(random.uniform(min_s, max_s))


def _extract_job_id(url):
    """Extract job ID from a LinkedIn job URL."""
    match = re.search(r"/view/(\d+)", url)
    if match:
        return match.group(1)
    match = re.search(r"currentJobId=(\d+)", url)
    if match:
        return match.group(1)
    return None


async def search_jobs(page, keywords, location):
    """Search LinkedIn jobs and return list of job card data."""
    query = urllib.parse.quote(" ".join(keywords))
    loc = urllib.parse.quote(location)
    url = (
        f"https://www.linkedin.com/jobs/search/"
        f"?keywords={query}&location={loc}&f_TPR=r604800"
    )

    await page.goto(url, wait_until="domcontentloaded")
    await _random_delay(3, 6)

    jobs = []

    # Scroll to load more job cards
    for _ in range(3):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await _random_delay(1, 2)

    # Extract job cards from the search results
    job_cards = await page.query_selector_all(
        "div.job-card-container, li.jobs-search-results__list-item"
    )

    for card in job_cards:
        try:
            # Try to get the job link
            link_el = await card.query_selector("a.job-card-container__link, a.job-card-list__title")
            if not link_el:
                continue

            href = await link_el.get_attribute("href")
            if not href:
                continue

            job_id = _extract_job_id(href)
            if not job_id:
                continue

            # Skip if already in DB
            if db.job_exists(job_id):
                continue

            title_text = (await link_el.inner_text()).strip()

            # Company name
            company_el = await card.query_selector(
                "span.job-card-container__primary-description, "
                "span.job-card-container__company-name"
            )
            company = (await company_el.inner_text()).strip() if company_el else "Unknown"

            # Location
            loc_el = await card.query_selector(
                "li.job-card-container__metadata-item, "
                "span.job-card-container__metadata-wrapper"
            )
            job_location = (await loc_el.inner_text()).strip() if loc_el else "Unknown"

            job_url = f"https://www.linkedin.com/jobs/view/{job_id}/"

            jobs.append({
                "job_id": job_id,
                "title": title_text,
                "company": company,
                "location": job_location,
                "url": job_url,
            })

        except Exception:
            continue

    return jobs


async def fetch_job_description(page, job_url):
    """Navigate to a job page and extract the full description."""
    await page.goto(job_url, wait_until="domcontentloaded")
    await _random_delay(2, 4)

    # Try to click "See more" to expand description
    try:
        see_more = await page.query_selector(
            "button.jobs-description__footer-button, "
            "button[aria-label='Show more']"
        )
        if see_more:
            await see_more.click()
            await _random_delay(0.5, 1)
    except Exception:
        pass

    # Extract description text
    desc_el = await page.query_selector(
        "div.jobs-description__content, "
        "div.jobs-box__html-content, "
        "div#job-details"
    )
    if desc_el:
        return (await desc_el.inner_text()).strip()
    return ""


async def scrape_new_jobs(keywords, location):
    """Full scraping pipeline: search -> filter new -> fetch descriptions."""
    async with async_playwright() as p:
        browser, context = await create_browser_context(p)
        page = await context.new_page()

        try:
            # Search for jobs
            job_cards = await search_jobs(page, keywords, location)
            print(f"Found {len(job_cards)} new job cards")

            # Fetch full descriptions for new jobs
            for job in job_cards:
                await _random_delay(2, 4)
                description = await fetch_job_description(page, job["url"])
                job["description"] = description
                print(f"  Fetched JD: {job['title']} at {job['company']}")

        finally:
            await browser.close()

    return job_cards
