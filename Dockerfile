FROM python:3.11-slim

WORKDIR /app

# Copy application files
COPY . /app

# Ensure Python outputs logs immediately without buffering
ENV PYTHONUNBUFFERED=1

# Default port
ENV PORT=9000
EXPOSE 9000

CMD ["python", "mobile_server.py"]
