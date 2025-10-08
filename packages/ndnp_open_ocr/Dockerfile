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
      libleptonica-dev libpng-dev libjpeg62-turbo-dev libtiff-dev libicu-dev libpango1.0-dev; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN wget -O tesseract-${TESSERACT_VERSION}.tar.gz \
         https://github.com/tesseract-ocr/tesseract/archive/refs/tags/${TESSERACT_VERSION}.tar.gz && \
    tar xzf tesseract-${TESSERACT_VERSION}.tar.gz && \
    cd tesseract-${TESSERACT_VERSION} && \
    ./autogen.sh && ./configure && make -j"$(nproc)" && make install

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
      default-jre-headless; \
    rm -rf /var/lib/apt/lists/*

# Copy the built Tesseract from builder
COPY --from=builder /usr/local/bin/tesseract /usr/local/bin/tesseract
COPY --from=builder /usr/local/lib/ /usr/local/lib/
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
