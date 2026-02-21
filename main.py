import asyncio
import logging
import signal
import sys

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
import db
import resume_parser
import scraper
import telegram_bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def run_job_scan(application):
    """Scrape LinkedIn, save new jobs, and send Telegram alerts."""
    # Read live settings from DB each scan
    keywords_str = db.get_setting("keywords")
    location = db.get_setting("location")

    if not keywords_str:
        logger.warning("No keywords set. Skipping scan. Use /keywords in Telegram.")
        return
    if not location:
        logger.warning("No location set. Skipping scan. Use /location in Telegram.")
        return

    keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
    logger.info(f"Starting job scan — keywords: {keywords}, location: {location}")

    try:
        new_jobs = await scraper.scrape_new_jobs(keywords, location)
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        return

    sent = 0
    for job in new_jobs:
        db.insert_job(
            job_id=job["job_id"],
            title=job["title"],
            company=job["company"],
            location=job["location"],
            url=job["url"],
            description=job.get("description", ""),
            status="pending",
        )

        try:
            await telegram_bot.send_job_alert(application, job)
            sent += 1
        except Exception as e:
            logger.error(f"Failed to send alert for {job['title']}: {e}")

    logger.info(f"Scan complete. Found {len(new_jobs)} new jobs, sent {sent} alerts.")


async def main():
    # 1. Initialize database
    db.init_db()
    logger.info("Database initialized.")

    # 2. Parse resume and seed initial settings
    logger.info("Loading candidate profile...")
    try:
        profile, keywords = resume_parser.get_or_create_profile()
    except FileNotFoundError:
        logger.error(
            f"Resume not found at '{config.RESUME_PATH}'. "
            f"Place your PDF resume there and restart."
        )
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to parse resume: {e}")
        sys.exit(1)

    # Seed keywords from resume if not already set
    if not db.get_setting("keywords"):
        db.set_setting("keywords", ",".join(keywords))
        logger.info(f"Initial keywords from resume: {keywords}")
    else:
        logger.info(f"Using existing keywords: {db.get_setting('keywords')}")

    # Seed location from config if not already set
    if not db.get_setting("location"):
        db.set_setting("location", config.JOB_LOCATION)
        logger.info(f"Initial location: {config.JOB_LOCATION}")
    else:
        logger.info(f"Using existing location: {db.get_setting('location')}")

    # 3. Create Telegram bot application
    application = telegram_bot.create_application()

    # 4. Set up scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_job_scan,
        "interval",
        minutes=config.SCRAPE_INTERVAL_MINUTES,
        args=[application],
    )

    # 5. Start everything
    async with application:
        await application.start()
        await application.updater.start_polling()
        logger.info("Telegram bot started.")

        scheduler.start()
        logger.info(
            f"Scheduler started. Scanning every {config.SCRAPE_INTERVAL_MINUTES} minutes."
        )

        # Run first scan immediately
        await run_job_scan(application)

        # Keep running until interrupted
        stop_event = asyncio.Event()

        def _handle_signal():
            logger.info("Shutting down...")
            stop_event.set()

        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _handle_signal)

        await stop_event.wait()

        # Cleanup
        scheduler.shutdown()
        await application.updater.stop()
        await application.stop()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
