############################################
# Builder: build Tesseract from source tag #
############################################
FROM python:3.11.10-slim-bookworm AS builder

ARG TESSERACT_VERSION=5.4.1
RUN set -eux; \
    apt-get update; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates curl wget unzip \
      make g++ autoconf automake libtool pkg-config autoconf-archive \
      libleptonica-dev libpng-dev libjpeg62-turbo-dev libtiff-dev libicu-dev libpango1.0-dev \
      libopenjp2-7-dev; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN wget -O tesseract-${TESSERACT_VERSION}.tar.gz \
         https://github.com/tesseract-ocr/tesseract/archive/refs/tags/${TESSERACT_VERSION}.tar.gz && \
    tar xzf tesseract-${TESSERACT_VERSION}.tar.gz && \
    cd tesseract-${TESSERACT_VERSION} && \
    ./autogen.sh && ./configure && make -j"$(nproc)" && make install

##############################################################
# AmericanStories assets: clone repo + download model weights #
##############################################################
FROM python:3.11.10-slim-bookworm AS americanstories-assets

# URL published in the upstream AmericanStories README
ARG AMERICANSTORIES_REPO_URL="https://github.com/dell-research-harvard/AmericanStories.git"
ARG AMERICANSTORIES_MODELS_URL="https://www.dropbox.com/sh/sfaf1nmuji9yhu6/AAAj1UGrPmCWFJUiTSP41ihpa?dl=1"
# Optional extra flags for curl (e.g., --insecure when behind a TLS-intercepting proxy)
ARG AMERICANSTORIES_CURL_FLAGS=""

RUN set -eux; \
    apt-get update; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates curl git unzip; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN set -eux; \
    git clone --depth 1 "${AMERICANSTORIES_REPO_URL}" AmericanStories; \
    mkdir -p AmericanStories/american_stories_models; \
    curl -fsSL ${AMERICANSTORIES_CURL_FLAGS} -o /tmp/american_stories_models.zip "${AMERICANSTORIES_MODELS_URL}"; \
    python - <<'PY'
import os, pathlib, shutil, zipfile

zip_path = "/tmp/american_stories_models.zip"
dest = "/tmp/american_models"
os.makedirs(dest, exist_ok=True)

with zipfile.ZipFile(zip_path) as zf:
    for info in zf.infolist():
        name = info.filename.lstrip("/")
        if not name:
            continue
        target = pathlib.Path(dest) / name
        if info.is_dir() or name.endswith("/"):
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info) as src, open(target, "wb") as dst:
            shutil.copyfileobj(src, dst)
PY

RUN set -eux; \
    if [ -d /tmp/american_models/american_stories_models ]; then \
      mv /tmp/american_models/american_stories_models/* /opt/AmericanStories/american_stories_models/; \
    else \
      mv /tmp/american_models/* /opt/AmericanStories/american_stories_models/; \
    fi; \
    rm -rf /tmp/american_stories_models.zip /tmp/american_models

############################################
# Runtime: slim, copy built Tesseract      #
############################################
FROM python:3.11.10-slim-bookworm

ARG INCLUDE_TEST_DEPS="false"

RUN set -eux; \
    apt-get update; \
    apt-get -y upgrade; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates curl wget unzip bc \
      # ExifTool (Debian package)
      libimage-exiftool-perl \
      # PDF utilities (only if used at runtime)
      ghostscript qpdf \
      # runtime libs for Tesseract
      liblept5 libjpeg62-turbo libtiff6 libpng16-16 libpango-1.0-0 libicu72 libgomp1 \
      libopenjp2-7 \
      default-jre-headless; \
    rm -rf /var/lib/apt/lists/*

# Copy the built Tesseract from builder
COPY --from=builder /usr/local/bin/tesseract /usr/local/bin/tesseract
COPY --from=builder /usr/local/lib/ /usr/local/lib/
COPY --from=builder /usr/local/share/tessdata /usr/local/share/tessdata
ENV LD_LIBRARY_PATH=/usr/local/lib

# Install traineddata under a controlled prefix
ENV TESSDATA_PREFIX=/usr/local/share/tessdata
RUN set -eux; \
    mkdir -p "$TESSDATA_PREFIX"; \
    curl -fsSL -o "$TESSDATA_PREFIX/osd.traineddata" \
      https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/4.1.0/osd.traineddata; \
    curl -fsSL -o "$TESSDATA_PREFIX/eng.traineddata" \
      https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/4.1.0/eng.traineddata

# App files
WORKDIR /app/ndnp_open_ocr
COPY . .

# AmericanStories segmentation assets (code + ONNX weights)
# These are obtained at build time from the upstream project and model host
# so that the open-source repo does not vendor them.
RUN rm -rf vendor/AmericanStories || true
COPY --from=americanstories-assets /opt/AmericanStories /app/ndnp_open_ocr/vendor/AmericanStories

# Python deps
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/packages:/app
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    if [ "$INCLUDE_TEST_DEPS" = "true" ]; then \
      pip install --no-cache-dir -r requirements-test.txt; \
    fi

# Non-root user for runtime
RUN useradd -m -u 10001 appuser && chown -R appuser:appuser /app /usr/local/share/tessdata
USER appuser
