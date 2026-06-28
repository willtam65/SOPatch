# SOPatch -- production image. Serves the app with gunicorn.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The platform injects PORT; default to 5001 for local `docker run`.
ENV PORT=5001
EXPOSE 5001

# Bind to $PORT and import the Flask `app` object from app.py.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 2 --timeout 120 app:app"]
