FROM lambci/lambda-base-2:build

# Update the package listing and install basic dependencies
RUN yum -y update && \
    yum -y install qpdf wget make gcc-c++ autoconf automake libtool pkgconfig \
    libpng-devel libjpeg-turbo-devel libtiff-devel icu libicu libicu-devel pango pango-devel unzip libxml2 libxslt

# Install Leptonica from source
WORKDIR /opt
RUN wget http://www.leptonica.org/source/leptonica-1.80.0.tar.gz && \
    tar -zxvf leptonica-1.80.0.tar.gz && \
    cd leptonica-1.80.0 && \
    ./configure && make && make install


#### TESSERACT INSTALL #####

ARG TESSERACT_DATA_SUFFIX=_fast
ARG TESSERACT_DATA_VERSION=4.1.0

# Update library paths
ENV LD_LIBRARY_PATH /usr/local/lib:$LD_LIBRARY_PATH
ENV PKG_CONFIG_PATH /usr/local/lib/pkgconfig:$PKG_CONFIG_PATH

# Install Tesseract (compiling from source as it may not be available in Amazon Linux repositories)
WORKDIR /opt
RUN wget https://github.com/tesseract-ocr/tesseract/archive/refs/heads/main.zip && \
    unzip main.zip && cd tesseract-main && \
    ./autogen.sh && ./configure && make && make install

# Install dependencies required for ExifTool
RUN yum -y install perl-ExtUtils-MakeMaker

# Install Exiftool (compiling from source)
WORKDIR /opt
RUN wget https://exiftool.org/Image-ExifTool-12.58.tar.gz && \
    tar xvf Image-ExifTool-12.58.tar.gz && cd Image-ExifTool-12.58/ && \
    perl Makefile.PL && make && make test && make install

RUN yum -y install libxml2-devel libxslt-devel
RUN yum install zip -y
RUN yum install qpdf-devel -y
RUN yum install libjpeg-turbo -y

RUN yum -y install clang gcc-c++ make autoconf aclocal automake libtool \
    libjpeg-devel libpng-devel libtiff-devel zlib-devel \
    libzip-devel freetype-devel lcms2-devel libwebp-devel \
    libicu-devel tcl-devel tk-devel pango-devel cairo-devel; yum clean all

# Update library paths
ENV LD_LIBRARY_PATH /usr/local/lib:/opt/layer/lib:$LD_LIBRARY_PATH
ENV PKG_CONFIG_PATH /usr/local/lib/pkgconfig:$PKG_CONFIG_PATH


WORKDIR /opt/layer
# Layer directory
# Create necessary directories
RUN mkdir -p bin lib python share/tessdata local
COPY requirements.txt .
RUN cp -r /usr/local/bin/* bin/ && \
    cp /usr/local/bin/tesseract bin/ && \
    cp /usr/local/lib/libtesseract.so.5 lib/libtesseract.so.5 && \
    cp /usr/local/lib/liblept.so.5 lib/liblept.so.5 && \
    cp /usr/local/lib/liblept.so lib/liblept.so && \
    cp /usr/lib64/libgomp.so.1 lib/ && \
    cp /usr/lib64/libpng15.so.15 lib/ && \
    cp /usr/lib64/libjpeg.so.62 lib/ && \
    cp /usr/lib64/libtiff.so.5 lib/ && \
    cp /usr/lib64/libjbig.so.2.0 lib/

RUN cp -r /usr/local/share/tessdata/* share/tessdata/

RUN curl -L https://github.com/tesseract-ocr/tessdata${TESSERACT_DATA_SUFFIX}/raw/${TESSERACT_DATA_VERSION}/osd.traineddata > share/tessdata/osd.traineddata && \
    curl -L https://github.com/tesseract-ocr/tessdata${TESSERACT_DATA_SUFFIX}/raw/${TESSERACT_DATA_VERSION}/eng.traineddata > share/tessdata/eng.traineddata

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# COPY ./gs /opt/layer/bin/
# COPY packages/ndnp_open_ocr /opt/layer/python/lib/python3.8/site-packages/ndnp_open_ocr
RUN yum install ghostscript -y

# ZIP the layer
WORKDIR /opt/layer
RUN zip -r /tmp/layer.zip .
