

# NDNP-Open-OCR

## Download Pre-Made Lambda Layer
https://ndnp-open-ocr-dependencies.s3.amazonaws.com/layers.zip

## Generating Lambda Layer Instructions

### Tesseract
https://github.com/bweigel/aws-lambda-tesseract-layer

Use ready-made AWS Linux 2 AMI Tesseract Lambda Layer with config files and tess data stored as in the current layers directory.

### Python Dependencies
Pip install Python dependencies in an AWS Python 3.8 runtime docker image and copy the contents of the Python packages into the layers/python/lib/pythonVER.X/site-packages directory. The AWS Lambda function will know to look for these dependencies here.

We used public Perl and Ghostscript Lambda layers to mount those dependencies (see SST.Config.Ts folder) -- we may consider doing our own if needed; However, I have no concerns about using these at the moment. They seem fairly widely used/supported.
