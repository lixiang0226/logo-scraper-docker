# Dockerfile

# Stage 1: Base Python image and System Dependencies
FROM python:3.9-slim-buster AS base

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Essential tools
    wget \
    gnupg \
    ca-certificates \
    unzip \
    # For cairosvg
    libcairo2-dev libpango1.0-dev libpangocairo-1.0-0 libgdk-pixbuf2.0-dev libffi-dev shared-mime-info \
    # For X Virtual Frame Buffer (robust headless)
    xvfb \
    xauth \ 
    # Curl for potential version detection if needed, though not used for chromedriver in this version
    curl \
    # Dependencies that might be needed by Chromium itself
    libglib2.0-0 libnss3 libfontconfig1 libx11-6 libx11-xcb1 libxcb1 \
    libxcomposite1 libxcursor1 libxdamage1 libxext6 libxfixes3 libxi6 libxrandr2 \
    libxrender1 libxss1 libxtst6 libatk1.0-0 libatk-bridge2.0-0 libgconf-2-4 fonts-liberation \
    libcups2 libdrm2 libgtk-3-0 libgbm1 libasound2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Chromium and its compatible ChromeDriver from Debian repositories
# These packages should be arm64 compatible when building on an arm64 host.
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Verify versions (optional, but good for debugging)
# The executable name might be 'chromium' or 'chromium-browser'.
# 'chromium' is common on Debian for the browser provided by the 'chromium' package.
RUN echo "Verifying installed versions:" \
    && (chromium --version || chromium-browser --version || echo "Chromium browser command not found or failed") \
    && (chromedriver --version || echo "Chromedriver command not found or failed")

# Stage 2: Application Stage (using a non-root user)
RUN useradd --create-home appuser
USER appuser
WORKDIR /home/appuser/app

# Add user's local bin to PATH. This is often where pip installs executables for user.
ENV PATH="/home/appuser/.local/bin:${PATH}"

# Copy requirements and install Python dependencies as non-root user
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY --chown=appuser:appuser . .

# Expose the port Gunicorn will run on
EXPOSE 8000

# ... (all previous Dockerfile content) ...

# Healthcheck (optional, good for platforms like Render)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8000/ || exit 1

# FINAL CMD: Run Gunicorn directly
CMD ["gunicorn", "--workers=2", "--threads=2", "--timeout=120", "--bind=0.0.0.0:8000", "app:app", "--log-level=info"]
# CMD ["sh", "-c", "which chromedriver"]
