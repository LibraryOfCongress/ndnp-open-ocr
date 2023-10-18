

# NDNP Open OCR - Library of Congress

This repository contains a Terraform module for creating resources required for deploying the NDNP Open OCR application into an AWS account. The application uses Lambda for processing and SQS message creation, SQS for keeping track of which files need to be processed and lining them up for ingest by worker Lambdas, and S3 for storing outputs.

There are 3 primary components that need to be treated on an individual basis:

1. NDNP Open OCR (currently in functions/src). This is the NDNP Open OCR pipeline that can be run locally or at scale in AWS. It has all of the OCR logic in it.
2. Terraform Deployment. This deploys NDNP Open OCR to AWS to run at scale.
3. Command Line Interface. This is the local CLI tool that can be used and distributed to control the AWS infrastructure laid out by Terraform.



# Deployment
## AWS Resources

The module creates AWS resources for the application including:

- **IAM Roles and Policies**: To allow the Lambdas to access S3, use DynamoDB table, etc...
- **Lambda Layers**: Used to provide library code and dependencies for the Lambda functions including the Python dependencies, Tesseract,
- **Lambda Functions**: Includes the scheduler function for creating SQS messages and the consumer functions for ingesting them and processing them.
- **SQS Queue**: For storing a message for each TIFF that needs to be processed by the Lambda functions that hold NDNP Open OCR library. Currently there is a queue for ALTO files, and a queue for PDF files. The ALTO queue links up to the alto_consumer script which solely generates ALTO files and saves in S3. The other queue (for PDFs) does the exact same thing, but it solely creates and saves the OCR PDFs into the S3 output bucket.
- **S3 Bucket**: For storing the PDF and ALTO outputs from NDNP Open OCR.
- **Cloudwatch Log Groups**: For storing logs of the Lambda functions.

## Prerequisites

- Terraform v1.4.6
- AWS CLI already configured with sufficient permissions to deploy and maintain resources mentioned above. Currently we are using the NDNP_OPEN_OCR_DEVELOPMENT_DEV role to deploy these resources as we build the project forward.
- Downloaded Pre-Made Lambda Layer (https://ndnp-open-ocr-dependencies.s3.amazonaws.com/layers.zip)

## Deployment

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

## Notes

- Please make sure you have the necessary AWS permissions to create and manage these resources.
- Make sure your AWS CLI is correctly configured with the correct profile or AWS access keys.

## Usage

To run the pipeline on a full batch, run this as a test event in the AWS Lambda console on the **ndnp-open-ocr-scheduler-lambda-function-dev** Lambda function.

```json
{
  "pathParameters": {
    "prefix": "loc-preservation/lcbp/ndnp/dlc/batch_dlc_kite_ver01"
  },
}
```
The pipeline will work on any subdirectories too; With that, for testing purposes, it is alright to provide a greater path that goes into the batch further so that as many files don't get processed during testing, for instance:

```json
{
  "pathParameters": {
    "prefix": "loc-preservation/lcbp/ndnp/dlc/batch_dlc_kite_ver01/data/sn83030214/00206531290/1877083101"
  },
}
```

passing that as the "prefix" will only reprocess batches in the 1877083101 directory.

### To Retry Job (Needs work)

To retry the failed messages in a job, simply cd into the functions directory and run the retry_job.py script, replacing the job_id with the job_id of the job you want to re-run failed messages on.





## Appendix: Generating Lambda Layer Instructions

### DynamoDB (NoSQL) Design



### Tesseract
https://github.com/bweigel/aws-lambda-tesseract-layer

Use ready-made AWS Linux 2 AMI Tesseract Lambda Layer with config files and tess data stored as in the current layers directory.

### Python Dependencies
Pip install Python dependencies in an AWS Python 3.8 runtime docker image and copy the contents of the Python packages into the layers/python/lib/pythonVER.X/site-packages directory. The AWS Lambda function will know to look for these dependencies here.

We used public Perl and Ghostscript Lambda layers to mount those dependencies (see SST.Config.Ts folder) -- we may consider doing our own if needed; However, I have no concerns about using these at the moment. They seem fairly widely used/supported.