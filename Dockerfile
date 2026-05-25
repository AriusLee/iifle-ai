FROM python:3.12-slim-bookworm

WORKDIR /app

# Install system dependencies for weasyprint and other packages.
# Chinese fonts are NOT installed here — WeasyPrint loads the bundled SC fonts
# in app/assets/fonts/ via @font-face instead (the system fonts-noto-cjk
# super-collection is 110 MB+ and made CJK rendering take minutes). fontconfig
# is kept so Pango can still discover the base Latin fonts.
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libcairo2 \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# Copy all source code first, then install
COPY . .
RUN pip install --no-cache-dir .

# Run migrations and seed on startup
CMD bash -c "alembic upgrade head && python -m scripts.seed_demo && uvicorn app.main:app --host 0.0.0.0 --port 10000"
