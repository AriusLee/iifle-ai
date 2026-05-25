FROM python:3.12-slim-bookworm

WORKDIR /app

# Install system dependencies for weasyprint and other packages.
# fonts-noto-cjk provides "Noto Sans CJK SC" / "Noto Serif CJK SC" so
# WeasyPrint can render Chinese text — without it CJK glyphs come out blank
# (the slim base image ships no CJK fonts). fontconfig is needed so Pango
# can discover the installed fonts.
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libcairo2 \
    fontconfig \
    fonts-noto-cjk \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

# Copy all source code first, then install
COPY . .
RUN pip install --no-cache-dir .

# Run migrations and seed on startup
CMD bash -c "alembic upgrade head && python -m scripts.seed_demo && uvicorn app.main:app --host 0.0.0.0 --port 10000"
