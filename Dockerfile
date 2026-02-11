FROM python:3.11-slim

WORKDIR /opt/telecodex

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

EXPOSE 8080
