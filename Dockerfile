FROM public.ecr.aws/lambda/python:3.9

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


# Copy application code and install Python dependencies
COPY packages/ndnp_open_ocr /var/task/
WORKDIR /var/task
COPY . .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

RUN ls

# Set the CMD to your handler (adjust the file and method names accordingly)
CMD ["lambdas/scheduler.handler"]