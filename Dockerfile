# Dockerfile — no local Postgres (use Neon)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Install system deps needed by Python packages (keep libpq-dev for psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc libpq-dev libjpeg-dev wget curl ca-certificates \
    tesseract-ocr poppler-utils \
    gnupg2 libnss3 libxss1 libasound2 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libpangocairo-1.0-0 \
    # Font packages required by Playwright browsers
    fonts-unifont fonts-dejavu-core fonts-liberation \
    libxfixes3 libxkbcommon0 libgdk-pixbuf-xlib-2.0-0 libfontconfig1 libgtk-3-0 libpng16-16 \
  && rm -rf /var/lib/apt/lists/*

# Copy and install Python requirements
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Optional: install Playwright browsers (if you actually need it)
# Install Playwright's Chromium browser and required OS deps
# Use the Python module entry so the package is available when we run the installer.
# Let the build fail if Playwright browser install fails so missing system deps are noticed.
RUN python -m playwright install chromium
#RUN python -m playwright install --with-deps chromium

# Copy project
COPY . /app

# Create media and runtime_logs directories for local storage
RUN mkdir -p /app/media/uploads && chmod -R 755 /app/media
RUN mkdir -p /app/runtime_logs/procurement && chmod -R 755 /app/runtime_logs

# Entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8080
CMD ["/entrypoint.sh"]
