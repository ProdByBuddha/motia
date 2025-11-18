FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl bash ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY agents/self_adapt/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY agents/self_adapt /app/agents/self_adapt

EXPOSE 4010

CMD ["uvicorn", "agents.self_adapt.builder_api:app", "--host", "0.0.0.0", "--port", "4010"]

