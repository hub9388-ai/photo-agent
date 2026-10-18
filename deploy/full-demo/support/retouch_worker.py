from app.worker import WorkerSettings as BaseSettings


class WorkerSettings(BaseSettings):
    # Large RGBA edits can use significant RAM; invitation demo starts one job at a time.
    max_jobs = 1
