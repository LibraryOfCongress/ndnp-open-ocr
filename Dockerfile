# Use the Amazon Linux 2 image with Python 3.8 as the base image
FROM public.ecr.aws/lambda/python:3.8

# Install system packages for Tesseract, Exiftool, and QPDF
RUN rpm -Uvh https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm
RUN yum -y update
RUN yum install -y exiftool qpdf
# RUN yum install -y \
#     wget \
#     tar \
#     make \
#     automake \
#     autoconf \
#     gcc \
#     gcc-c++ \
#     cairo-devel \
#     icu-devel \
#     icu \
#     pango-devel \
#     icu \
#     leptonica leptonica-devel \
#     cairo cairo-devel \
#     icu libicu libicu-devel

# RUN wget http://www.leptonica.org/source/leptonica-1.80.0.tar.gz && \
#     tar -zxvf leptonica-1.80.0.tar.gz && \
#     cd leptonica-1.80.0 && \
#     ./configure && \
#     make && \
#     make install

# RUN wget https://github.com/tesseract-ocr/tesseract/archive/5.0.0-alpha.tar.gz && \
#     tar -zxvf 5.0.0-alpha.tar.gz && \
#     cd tesseract-5.0.0-alpha && \
#     ./autogen.sh && \
#     ./configure && \
#     make && \
#     make install && \
#     ldconfig


# Copy the requirements.txt file into the container
COPY requirements.txt ./

# Install Python packages from the requirements.txt file
RUN pip install --no-cache-dir -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

# Add Ghostscript repository and install Ghostscript
RUN yum install -y ghostscript

# Copy the Lambda function handler into the container
COPY ./ ${LAMBDA_TASK_ROOT}

ENTRYPOINT [ "python", "-m", "awslambdaric" ]

# Set the CMD to your handler (could also be done as a parameter override outside of the Dockerfile)
CMD ["lambda.handler"]