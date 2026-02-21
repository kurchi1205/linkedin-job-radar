import pytest
from scraper import _extract_job_id


# --- _extract_job_id (pure function, no mocking needed) ---

def test_extract_job_id_from_view_url():
    url = "https://www.linkedin.com/jobs/view/3812345678/"
    assert _extract_job_id(url) == "3812345678"


def test_extract_job_id_from_view_url_no_trailing_slash():
    url = "https://www.linkedin.com/jobs/view/3812345678"
    assert _extract_job_id(url) == "3812345678"


def test_extract_job_id_from_current_job_id_param():
    url = "https://www.linkedin.com/jobs/search/?currentJobId=9876543210&keywords=python"
    assert _extract_job_id(url) == "9876543210"


def test_extract_job_id_returns_none_for_invalid_url():
    assert _extract_job_id("https://www.linkedin.com/jobs/search/") is None


def test_extract_job_id_returns_none_for_empty():
    assert _extract_job_id("") is None


def test_extract_job_id_returns_none_for_non_linkedin():
    assert _extract_job_id("https://example.com/jobs/123") is None


# --- search_jobs and fetch_job_description (async, need mocking) ---

@pytest.mark.asyncio
async def test_search_jobs_skips_existing_jobs():
    """Jobs already in DB should be skipped."""
    import db
    db.insert_job("111", "Old Job", "Co", "SG", "https://link", "desc")

    from unittest.mock import AsyncMock, MagicMock, patch

    # Mock a page with one job card whose job_id is already in DB
    mock_link = AsyncMock()
    mock_link.get_attribute = AsyncMock(return_value="/jobs/view/111/")
    mock_link.inner_text = AsyncMock(return_value="Old Job")

    mock_card = AsyncMock()
    mock_card.query_selector = AsyncMock(return_value=mock_link)

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.evaluate = AsyncMock()
    mock_page.query_selector_all = AsyncMock(return_value=[mock_card])

    with patch("scraper._random_delay", new_callable=lambda: AsyncMock):
        from scraper import search_jobs
        jobs = await search_jobs(mock_page, ["Python"], "Singapore")

    assert len(jobs) == 0  # Should be skipped


@pytest.mark.asyncio
async def test_search_jobs_returns_new_jobs():
    """New jobs not in DB should be returned."""
    from unittest.mock import AsyncMock, patch

    mock_link = AsyncMock()
    mock_link.get_attribute = AsyncMock(return_value="/jobs/view/222/")
    mock_link.inner_text = AsyncMock(return_value="New Job")

    mock_company = AsyncMock()
    mock_company.inner_text = AsyncMock(return_value="Acme Corp")

    mock_loc = AsyncMock()
    mock_loc.inner_text = AsyncMock(return_value="Singapore")

    mock_card = AsyncMock()
    async def card_query_selector(selector):
        if "link" in selector or "title" in selector:
            return mock_link
        if "company" in selector or "primary-description" in selector:
            return mock_company
        if "metadata" in selector:
            return mock_loc
        return None
    mock_card.query_selector = AsyncMock(side_effect=card_query_selector)

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.evaluate = AsyncMock()
    mock_page.query_selector_all = AsyncMock(return_value=[mock_card])

    with patch("scraper._random_delay", new_callable=lambda: AsyncMock):
        from scraper import search_jobs
        jobs = await search_jobs(mock_page, ["Python"], "Singapore")

    assert len(jobs) == 1
    assert jobs[0]["job_id"] == "222"
    assert jobs[0]["title"] == "New Job"


@pytest.mark.asyncio
async def test_fetch_job_description_returns_text():
    """fetch_job_description should return the JD text."""
    from unittest.mock import AsyncMock, patch

    mock_desc = AsyncMock()
    mock_desc.inner_text = AsyncMock(return_value="We are looking for a Python dev...")

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.query_selector = AsyncMock(side_effect=[None, mock_desc])
    # First call: see_more button (None), second call: description element

    # Need to handle the two query_selector calls properly
    call_count = 0
    async def mock_qs(selector):
        nonlocal call_count
        call_count += 1
        if call_count == 1:  # see_more button
            return None
        return mock_desc  # description element

    mock_page.query_selector = AsyncMock(side_effect=mock_qs)

    with patch("scraper._random_delay", new_callable=lambda: AsyncMock):
        from scraper import fetch_job_description
        desc = await fetch_job_description(mock_page, "https://linkedin.com/jobs/view/123/")

    assert "Python dev" in desc


@pytest.mark.asyncio
async def test_fetch_job_description_returns_empty_when_no_element():
    """If no description element found, return empty string."""
    from unittest.mock import AsyncMock, patch

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.query_selector = AsyncMock(return_value=None)

    with patch("scraper._random_delay", new_callable=lambda: AsyncMock):
        from scraper import fetch_job_description
        desc = await fetch_job_description(mock_page, "https://linkedin.com/jobs/view/123/")

    assert desc == ""
