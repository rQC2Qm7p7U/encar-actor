# Apify Python actor
FROM python:3.12-slim

WORKDIR /usr/src/app

RUN apt-get update -qq && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY parser.py main.py ./

CMD ["python", "-m", "main"]
