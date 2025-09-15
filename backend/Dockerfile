# Use modern Python so Django 5.x and friends work
FROM python:3.12-slim

# Saner defaults
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /backend

# (Optional) system deps — uncomment only if you compile wheels
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential libpq-dev gcc \
#  && rm -rf /var/lib/apt/lists/*

# Copy and install deps first (better layer caching)
COPY ./requirements.txt /backend/requirements.txt
RUN python -m pip install --upgrade pip \
 && pip install -r requirements.txt

# Copy app code
COPY . /backend

# Expose API port
EXPOSE 8000

# NOTE: For production, prefer gunicorn without --reload.
# This dev-friendly command runs DB migrations then starts the server.
CMD ["bash", "-lc", "alembic upgrade head && uvicorn app.api.server:app --host 0.0.0.0 --port 8000"]
