FROM python:3.13-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .
RUN uv sync --no-dev

COPY . .

EXPOSE 8000

CMD ["uv", "run", "gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "run:app"]
