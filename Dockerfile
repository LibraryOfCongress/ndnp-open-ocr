FROM public.ecr.aws/lambda/python:3.8

# Update the package listing and install basic dependencies
RUN yum -y update && \
    yum -y install ghostscript qpdf wget make gcc-c++ autoconf automake libtool pkgconfig \
    libpng-devel libjpeg-turbo-devel libtiff-devel icu libicu libicu-devel pango pango-devel unzip libxml2 libxslt

# Install Leptonica from source
WORKDIR /opt
RUN wget http://www.leptonica.org/source/leptonica-1.80.0.tar.gz && \
    tar -zxvf leptonica-1.80.0.tar.gz && \
    cd leptonica-1.80.0 && \
    ./configure && make && make install

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

# Layer directory
# Create necessary directories
RUN mkdir -p bin lib python share/tessdata
COPY requirements.txt .
RUN cp -r /usr/local/bin/* bin/ && \
    cp /usr/local/bin/tesseract bin/ && \
    cp /usr/local/lib/libtesseract.so lib/libtesseract.so && \
    cp /usr/local/lib/liblept.so lib/liblept.so

#find /usr/local/lib/ -name '*.so' -exec cp --parents \{\} lib/ \;

RUN cp -r /usr/local/share/tessdata/* share/tessdata/


# Install Python dependencies
COPY requirements.txt .
RUN pip install --target "${LAMBDA_TASK_ROOT}" -r requirements.txt


# Copy the contents of the Lambda function directory into the container
COPY lambdas/. ${LAMBDA_TASK_ROOT}/

# Copy binaries and libraries
# RUN cp /usr/local/bin/* bin/ && \
#     cp -r /usr/local/lib/* lib/
# Copy the specific binaries and libraries
# Copy binaries and libraries

# COPY packages/ndnp_open_ocr /opt/layer/python/lib/python3.8/site-packages/ndnp_open_ocr

# ZIP the layer
RUN zip -r /tmp/layer.zip .