FROM python:3.13-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .
RUN uv sync --no-dev

COPY . .

EXPOSE 8000

RUN chmod +x scripts/start.sh

CMD ["bash", "scripts/start.sh"]
