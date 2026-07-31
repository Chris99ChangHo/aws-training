# Fixture only -- never built. Deliberately missing operability controls:
# floating base tag, no HEALTHCHECK, no pinned versions. Used to measure what
# Trivy already reports so the operability checker does not duplicate it.
FROM python:latest

RUN pip install requests

COPY . /app
WORKDIR /app

CMD ["python", "app.py"]
