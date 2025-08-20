#--------------------------------------------------------------------------------
# Stage 1: grab OCR-Fileformat CLI and assets from the official image
#--------------------------------------------------------------------------------
FROM ubma/ocr-fileformat:latest AS ocr

#--------------------------------------------------------------------------------
# Stage 2: NDNP Open OCR Image Building
#--------------------------------------------------------------------------------
FROM python:3.11.0


ARG EXIFTOOL_VERSION=13.27

# ExifTool does not maintain old versions of the tarball on their website
# which is why we are copying the tarball from the vendor directory.
# This is a workaround until we can find a better solution.
COPY vendor/Image-ExifTool-${EXIFTOOL_VERSION}.tar.gz /tmp/
RUN cd /tmp \
 && tar xzf Image-ExifTool-13.27.tar.gz \
 && cd Image-ExifTool-13.27 \
 && perl Makefile.PL \
 && make \
 && make install \
 && exiftool -ver

RUN apt-get update
RUN apt-get install -y ghostscript -y qpdf

# Update and install depedencies
RUN apt-get update && \
    apt-get install -y wget unzip bc vim python3-pip libleptonica-dev git cmake
RUN apt-get install -y software-properties-common

# Packages to complie Tesseract
RUN apt-get install -y --reinstall make && \
    apt-get install -y g++ autoconf automake libtool pkg-config \
    libpng-dev libjpeg62-turbo-dev libtiff5-dev libicu-dev \
    libpango1.0-dev autoconf-archive

# Install Tesseract (compiling from source as it may not be available in Amazon Linux repositories)
WORKDIR /opt
RUN wget https://github.com/tesseract-ocr/tesseract/archive/refs/heads/main.zip && \
    unzip main.zip && cd tesseract-main && \
    ./autogen.sh && ./configure && make && make install

#### TESSERACT INSTALL #####
ARG TESSERACT_DATA_SUFFIX=_best
ARG TESSERACT_DATA_VERSION=4.1.0

RUN curl -L https://github.com/tesseract-ocr/tessdata${TESSERACT_DATA_SUFFIX}/raw/${TESSERACT_DATA_VERSION}/osd.traineddata > /usr/local/share/tessdata/osd.traineddata && \
    curl -L https://github.com/tesseract-ocr/tessdata${TESSERACT_DATA_SUFFIX}/raw/${TESSERACT_DATA_VERSION}/eng.traineddata > /usr/local/share/tessdata/eng.traineddata

RUN apt-get install  protobuf-compiler \
      libprotobuf-dev -y

COPY --from=ocr /usr/local/bin/ocr-*       /usr/local/bin/
COPY --from=ocr /usr/local/share/ocr-fileformat /usr/local/share/ocr-fileformat

# Copy files from same directory as Dockerfile to /app
WORKDIR /app/ndnp_open_ocr
COPY . .

ENV CMAKE_ARGS="-DBUILD_SHARED_LIBS=ON"

RUN rm -f /usr/lib/x86_64-linux-gnu/libprotobuf.a \
          /usr/lib/x86_64-linux-gnu/libprotoc.a

RUN pip install --upgrade pip
RUN pip install -r requirements.txt && \
    apt-get update && \
    apt-get install -y --no-install-recommends default-jre-headless && \
    rm -rf /var/lib/apt/lists/*


ENV LD_LIBRARY_PATH $LD_LIBRARY_PATH:/usr/local/lib
ENV TESSDATA_PREFIX /usr/local/share/tessdata