FROM python:3.14-slim

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends openssl ca-certificates \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY web ./web
COPY config.example.yaml ./config.example.yaml
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

ENV CONFIG_PATH=/app/config.yaml
ENV DATA_DIR=/app/data
EXPOSE 6443

CMD ["./entrypoint.sh"]
