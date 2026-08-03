FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    ABLETON_AUTO_MIX_TRANSPORT=http \
    ABLETON_AUTO_MIX_HOST=0.0.0.0 \
    ABLETON_AUTO_MIX_PORT=8000

WORKDIR /app

RUN pip install --no-cache-dir ableton-auto-mix-mcp

EXPOSE 8000

CMD ["python", "-m", "ableton_auto_mix"]
