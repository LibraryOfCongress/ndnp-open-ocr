# # # Use the Amazon Linux 2 image with Python 3.8 as the base image
# # FROM public.ecr.aws/lambda/python:3.8

# # # Install system packages for Tesseract, Exiftool, and QPDF
# # RUN rpm -Uvh https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm
# # RUN yum -y update
# # RUN yum install -y exiftool qpdf
# # RUN yum install -y \
# #     wget \
# #     tar \
# #     make \
# #     automake \
# #     autoconf \
# #     gcc \
# #     gcc-c++ \
# #     cairo-devel \
# #     icu-devel \
# #     icu \
# #     pango-devel \
# #     icu \
# #     leptonica leptonica-devel \
# #     cairo cairo-devel \
# #     icu libicu libicu-devel

# # RUN wget http://www.leptonica.org/source/leptonica-1.80.0.tar.gz && \
# #     tar -zxvf leptonica-1.80.0.tar.gz && \
# #     cd leptonica-1.80.0 && \
# #     ./configure && \
# #     make && \
# #     make install

# # RUN wget https://github.com/tesseract-ocr/tesseract/archive/5.0.0-alpha.tar.gz && \
# #     tar -zxvf 5.0.0-alpha.tar.gz && \
# #     cd tesseract-5.0.0-alpha && \
# #     ./autogen.sh && \
# #     ./configure && \
# #     make && \
# #     make install && \
# #     ldconfig


# # # Copy the requirements.txt file into the container
# # COPY requirements.txt ./

# # # Install Python packages from the requirements.txt file
# # RUN pip install --no-cache-dir -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

# # # Add Ghostscript repository and install Ghostscript
# # RUN yum install -y ghostscript

# # # Copy the Lambda function handler into the container
# # COPY ./ ${LAMBDA_TASK_ROOT}

# # ENTRYPOINT [ "python", "-m", "awslambdaric" ]

# # # Set the CMD to your handler (could also be done as a parameter override outside of the Dockerfile)
# # CMD ["lambda.handler"]

# # Use the Amazon Linux 2 image with Python 3.8 as the base image
# # FROM public.ecr.aws/lambda/python:3.11

# # # Install system packages for Tesseract, Exiftool, and QPDF
# # # RUN rpm -Uvh https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm
# # RUN yum -y update
# # RUN yum install -y exiftool qpdf
# # RUN yum install -y \
# #     wget \
# #     tar \
# #     make \
# #     automake \
# #     autoconf \
# #     gcc \
# #     gcc-c++ \
# #     cairo-devel \
# #     icu-devel \
# #     icu \
# #     pango-devel \
# #     icu \
# #     leptonica leptonica-devel \
# #     cairo cairo-devel \
# #     icu libicu libicu-devel \
# #     libtoolize

# # RUN wget https://github.com/tesseract-ocr/tesseract/archive/5.0.0-alpha.tar.gz && \
# #     tar -zxvf 5.0.0-alpha.tar.gz && \
# #     cd tesseract-5.0.0-alpha && \
# #     ./autogen.sh && \
# #     ./configure && \
# #     make && \
# #     make install && \
# #     ldconfig


# # RUN tesseract -v # <-- Add this line to verify tesseract installation

# ## Builds binaries for Amazonlinux 2
# # FROM public.ecr.aws/sam/build-provided.al2:1.97

# # ARG LEPTONICA_VERSION=1.83.1
# # ARG TESSERACT_VERSION=5.3.2
# # ARG AUTOCONF_ARCHIVE_VERSION=2017.09.28
# # ARG TMP_BUILD=/tmp
# # ARG TESSERACT=/opt/tesseract
# # ARG LEPTONICA=/opt/leptonica
# # ARG DIST=/opt/build-dist
# # # change OCR_LANG to enable the layer for different languages
# # ARG OCR_LANG=deu
# # # change TESSERACT_DATA_SUFFIX to use different datafiles (options: "_best", "_fast" and "")
# # ARG TESSERACT_DATA_SUFFIX=_fast
# # ARG TESSERACT_DATA_VERSION=4.1.0
# # ARG COMPILER_OPTIONS='CXXFLAGS=-mavx2'

# # RUN yum makecache fast; yum clean all && yum -y update && yum -y upgrade; yum clean all && \
# #     yum install -y yum-plugin-ovl; yum clean all && yum -y groupinstall "Development Tools"; yum clean all

# # RUN yum -y install clang gcc-c++ make autoconf aclocal automake libtool \
# #     libjpeg-devel libpng-devel libtiff-devel zlib-devel \
# #     libzip-devel freetype-devel lcms2-devel libwebp-devel \
# #     libicu-devel tcl-devel tk-devel pango-devel cairo-devel; yum clean all

# # WORKDIR ${TMP_BUILD}/leptonica-build
# # RUN curl -L https://github.com/DanBloomberg/leptonica/releases/download/${LEPTONICA_VERSION}/leptonica-${LEPTONICA_VERSION}.tar.gz | tar xz && cd ${TMP_BUILD}/leptonica-build/leptonica-${LEPTONICA_VERSION} && \
# #     ./configure --prefix=${LEPTONICA} && make && make install && cp -r ./src/.libs /opt/liblept

# # RUN echo "/opt/leptonica/lib" > /etc/ld.so.conf.d/leptonica.conf && /usr/sbin/ldconfig

# # WORKDIR ${TMP_BUILD}/autoconf-build
# # RUN curl https://ftp.gnu.org/gnu/autoconf-archive/autoconf-archive-${AUTOCONF_ARCHIVE_VERSION}.tar.xz | tar xJ && \
# #     cd autoconf-archive-${AUTOCONF_ARCHIVE_VERSION} && ./configure && make && make install && cp ./m4/* /usr/share/aclocal/

# # WORKDIR ${TMP_BUILD}/tesseract-build
# # RUN curl -L https://github.com/tesseract-ocr/tesseract/archive/${TESSERACT_VERSION}.tar.gz | tar xz && \
# #     cd tesseract-${TESSERACT_VERSION} && ./autogen.sh  && PKG_CONFIG_PATH=/opt/leptonica/lib/pkgconfig LIBLEPT_HEADERSDIR=/opt/leptonica/include \
# #     ./configure --prefix=${TESSERACT} --with-extra-includes=/opt/leptonica/include --with-extra-libraries=/opt/leptonica/lib ${COMPILER_OPTIONS}  && make && make install

# # WORKDIR /opt
# # RUN mkdir -p ${DIST}/lib && mkdir -p ${DIST}/bin && \
# #     cp ${TESSERACT}/bin/tesseract ${DIST}/bin/ && \
# #     cp ${TESSERACT}/lib/libtesseract.so.5  ${DIST}/lib/ && \
# #     cp ${LEPTONICA}/lib/libleptonica.so.6.0.0 ${DIST}/lib/libleptonica.so.6 && \
# #     cp /usr/lib64/libgomp.so.1 ${DIST}/lib/ && \
# #     cp /usr/lib64/libwebp.so.4 ${DIST}/lib/ && \
# #     cp /usr/lib64/libpng15.so.15 ${DIST}/lib/ && \
# #     cp /usr/lib64/libjpeg.so.62 ${DIST}/lib/ && \
# #     cp /usr/lib64/libtiff.so.5 ${DIST}/lib/ && \
# #     cp /usr/lib64/libjbig.so.2.0 ${DIST}/lib/ && \
# #     echo -e "LEPTONICA_VERSION=${LEPTONICA_VERSION}\nTESSERACT_VERSION=${TESSERACT_VERSION}\nTESSERACT_DATA_FILES=tessdata${TESSERACT_DATA_SUFFIX}/${TESSERACT_DATA_VERSION}\nTESSERACT_DATA_LANGUAGES=osd,eng,${OCR_LANG}" > ${DIST}/TESSERACT-README.md && \
# #     find ${DIST}/lib -name '*.so*' | xargs strip -s

# # WORKDIR ${DIST}/tesseract/share/tessdata
# # RUN curl -L https://github.com/tesseract-ocr/tessdata${TESSERACT_DATA_SUFFIX}/raw/${TESSERACT_DATA_VERSION}/osd.traineddata > osd.traineddata && \
# #     curl -L https://github.com/tesseract-ocr/tessdata${TESSERACT_DATA_SUFFIX}/raw/${TESSERACT_DATA_VERSION}/eng.traineddata > eng.traineddata && \
# #     curl -L https://github.com/tesseract-ocr/tessdata${TESSERACT_DATA_SUFFIX}/raw/${TESSERACT_DATA_VERSION}/${OCR_LANG}.traineddata > ${OCR_LANG}.traineddata

# # WORKDIR /var/task
# FROM public.ecr.aws/lambda/python:3.11

# RUN yum -y update
# RUN yum -y install wget libstdc++ autoconf automake libtool autoconf-archive pkg-config gcc gcc-c++ make libjpeg-devel libpng-devel libtiff-devel zlib-devel
# RUN yum group install -y "Development Tools"

# # Build leptonica
# WORKDIR /opt
# RUN wget http://www.leptonica.org/source/leptonica-1.82.0.tar.gz
# RUN ls -la
# RUN tar -zxvf leptonica-1.82.0.tar.gz
# WORKDIR ./leptonica-1.82.0
# RUN ./configure
# RUN make -j
# RUN make install
# RUN cd .. && rm leptonica-1.82.0.tar.gz

# # Build tesseract
# RUN wget https://github.com/tesseract-ocr/tesseract/archive/refs/tags/5.2.0.tar.gz
# RUN tar -zxvf 5.2.0.tar.gz
# WORKDIR ./tesseract-5.2.0
# RUN ./autogen.sh
# RUN PKG_CONFIG_PATH=/usr/local/lib/pkgconfig LIBLEPT_HEADERSDIR=/usr/local/include ./configure --with-extra-includes=/usr/local/include --with-extra-libraries=/usr/local/lib
# RUN LDFLAGS="-L/usr/local/lib" CFLAGS="-I/usr/local/include" make -j
# RUN make install
# RUN /sbin/ldconfig
# RUN cd .. && rm 5.2.0.tar.gz

# # Optional: install language packs
# RUN wget https://github.com/tesseract-ocr/tessdata/raw/main/deu.traineddata
# RUN wget https://github.com/tesseract-ocr/tessdata/raw/main/eng.traineddata
# RUN mv *.traineddata /usr/local/share/tessdata

# # Install Ghostscript and QPDF
# RUN yum install -y ghostscript
# RUN yum install -y qpdf

# # Install Exiftool
# RUN yum install perl-devel -y make
# #RUN apt-get install -y exiftool
# RUN wget https://exiftool.org/Image-ExifTool-12.58.tar.gz && tar xvf Image-ExifTool-12.58.tar.gz && cd Image-ExifTool-12.58/ && perl Makefile.PL && make && make test && make install


# # Copy files from same directory as Dockerfile to /app
# WORKDIR /app
# COPY . .

# # Install pre-build dependencies

# RUN pip install -r requirements.txt

# WORKDIR /root

# ENTRYPOINT [ "tesseract", "--version" ]

FROM python:3.9.0

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

# Run the application -- any command line args will carry over from the CLI command
# used to run the Docker container.
# ENTRYPOINT [ "python", "-u", "src/main.py" ]
