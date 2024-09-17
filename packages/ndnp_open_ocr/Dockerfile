FROM python:3.12.0

RUN apt-get update
RUN apt-get install -y ghostscript -y qpdf
# Update and install depedencies
RUN apt-get update && \
    apt-get install -y wget unzip bc vim python3-pip libleptonica-dev git
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

#### ExifTool INSTALL #####
RUN wget --no-check-certificate https://exiftool.org/Image-ExifTool-12.87.tar.gz && tar xvf Image-ExifTool-12.87.tar.gz && cd Image-ExifTool-12.87/ && perl Makefile.PL && make && make test && make install


# Copy files from same directory as Dockerfile to /app
WORKDIR /app/ndnp_open_ocr
COPY . .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

ENV LD_LIBRARY_PATH $LD_LIBRARY_PATH:/usr/local/lib
ENV TESSDATA_PREFIX /usr/local/share/tessdata