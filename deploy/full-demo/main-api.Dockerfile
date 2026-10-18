FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/backend:/support
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./backend/app
COPY agent_code ./agent_code
COPY deploy/full-demo/support /support
RUN useradd --uid 10001 --create-home demo && mkdir /state /limits && chown demo:demo /state /limits
USER demo
EXPOSE 8000
# One process: the current event bus/job runner are process-local.
CMD ["uvicorn", "main_entry:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
