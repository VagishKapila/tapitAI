from apscheduler.schedulers.background import BackgroundScheduler
from app.modules.frequent.engine import run_frequency_engine


scheduler = BackgroundScheduler()


def start_frequency_scheduler():
    scheduler.add_job(run_frequency_engine, "interval", hours=24)
    scheduler.start()
