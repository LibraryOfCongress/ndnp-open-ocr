

# NDNP-Open-OCR

## Download Pre-Made Lambda Layer
https://ndnp-open-ocr-dependencies.s3.amazonaws.com/layers.zip

# NDNP Open OCR Terraform Module

This repository contains a Terraform module for creating resources required for deploying the NDNP Open OCR application into an AWS account.

## Overview

The module creates AWS resources for the application including:

- **IAM Roles and Policies**: To allow services like Lambda functions and the API gateway to interact with other AWS services.
- **Lambda Layers**: Used to provide library code and dependencies for the Lambda functions.
- **Lambda Functions**: Includes the scheduler function and worker function.
- **API Gateway**: For HTTP access to the application.
- **SQS Queue**: For message queueing between the functions.
- **S3 Bucket**: For storing the application outputs.
- **Cloudwatch Log Groups**: For storing logs of the Lambda functions.

## Prerequisites

- Terraform 0.14.x
- AWS CLI already configured with sufficient permissions to deploy and maintain resources mentioned above. Currently we are using the NDNP_OPEN_OCR_DEVELOPMENT_DEV role to deploy these resources as we build the project forward.
- Downloaded Pre-Made Lambda Layer (https://ndnp-open-ocr-dependencies.s3.amazonaws.com/layers.zip)

## Getting Started

To use this module:
1. Download pre-made Lambda Layer: https://ndnp-open-ocr-dependencies.s3.amazonaws.com/layers.zip from the NDNP bucket we setup to temporarily store these dependencies. In the future we will automate layer building as part of the Terraform file.

2. Initialize the correct Terraform workspace - our current work takes place in us-east-2 region.

```bash
terraform workspace select us-east-2
```

3. Create an execution plan.

```bash
terraform plan
```

4. Apply the plan to create resources.

```bash
terraform apply
```

## Inputs

See main.tf for adjustable values for each module stored in resource folder.

## Outputs

| Name | Description |
|------|-------------|
| api_endpoint | The API endpoint URL of the API Gateway. |
| bucket_name | The name of the created S3 bucket. |

## Resources

The following resources are created by this module:

- AWS IAM roles
- AWS IAM policies
- AWS S3 bucket
- AWS Lambda layers
- AWS Lambda functions
- AWS SQS queue
- AWS API Gateway
- AWS CloudWatch log groups

## Notes

- Please make sure you have the necessary AWS permissions to create and manage these resources.
- Make sure your AWS CLI is correctly configured with the correct profile or AWS access keys.

## Appendix: Generating Lambda Layer Instructions

### Tesseract
https://github.com/bweigel/aws-lambda-tesseract-layer

Use ready-made AWS Linux 2 AMI Tesseract Lambda Layer with config files and tess data stored as in the current layers directory.

### Python Dependencies
Pip install Python dependencies in an AWS Python 3.8 runtime docker image and copy the contents of the Python packages into the layers/python/lib/pythonVER.X/site-packages directory. The AWS Lambda function will know to look for these dependencies here.

We used public Perl and Ghostscript Lambda layers to mount those dependencies (see SST.Config.Ts folder) -- we may consider doing our own if needed; However, I have no concerns about using these at the moment. They seem fairly widely used/supported.