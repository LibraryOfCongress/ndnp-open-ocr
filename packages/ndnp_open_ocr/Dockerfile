FROM python:3.8.0

RUN apt-get update
RUN apt-get install -y ghostscript
RUN apt-get install -y qpdf

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

# Install Exiftool
RUN apt-get install perl make
#RUN apt-get install -y exiftool
RUN wget https://exiftool.org/Image-ExifTool-12.58.tar.gz && tar xvf Image-ExifTool-12.58.tar.gz && cd Image-ExifTool-12.58/ && perl Makefile.PL && make && make test && make install


# Copy files from same directory as Dockerfile to /app
WORKDIR /app
COPY . .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt
