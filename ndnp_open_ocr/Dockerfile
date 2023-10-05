FROM python:3.8.0

RUN apt-get update
RUN apt-get install -y ghostscript
RUN apt-get install -y qpdf

# Update and install depedencies
# RUN apt-get update && \
#     apt-get install -y wget unzip bc vim python3-pip libleptonica-dev git
RUN apt-get install -y software-properties-common

# Packages to complie Tesseract
RUN apt-get install -y --reinstall make && \
    apt-get install -y g++ autoconf automake libtool pkg-config \
     libpng-dev libjpeg62-turbo-dev libtiff5-dev libicu-dev \
     libpango1.0-dev autoconf-archive

# Install Tesseract 5 by adding Tesseract OCR 5 PPA to the system
# RUN add-apt-repository ppa:alex-p/tesseract-ocr-devel
RUN apt-get install apt-transport-https
RUN echo "deb https://notesalexp.org/tesseract-ocr5/$(lsb_release -cs)/ $(lsb_release -cs) main" \
tee /etc/apt/sources.list.d/notesalexp.list > /dev/null
RUN echo "deb https://notesalexp.org/tesseract-ocr-dev/$(lsb_release -cs)/ $(lsb_release -cs) main" \
| tee /etc/apt/sources.list.d/notesalexp.list > /dev/null

RUN wget -O - https://notesalexp.org/debian/alexp_key.asc | apt-key add -
RUN apt-get update
# RUN apt-get update -oAcquire::AllowInsecureRepositories=true
# RUN apt-get install notesalexp-keyring -oAcquire::AllowInsecureRepositories=true
RUN apt-get install -y tesseract-ocr

# Install Exiftool
RUN apt-get install perl make
#RUN apt-get install -y exiftool
RUN wget https://exiftool.org/Image-ExifTool-12.58.tar.gz && tar xvf Image-ExifTool-12.58.tar.gz && cd Image-ExifTool-12.58/ && perl Makefile.PL && make && make test && make install


# Copy files from same directory as Dockerfile to /app
WORKDIR /app
COPY . .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt
