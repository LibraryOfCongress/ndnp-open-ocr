

# NDNP Open OCR - Library of Congress

This repository contains a Terraform module for creating resources required for deploying the NDNP Open OCR application into an AWS account. The application uses Lambda for processing and SQS message creation, SQS for keeping track of which files need to be processed and lining them up for ingest by worker Lambdas, and S3 for storing outputs.

There are 3 primary components that need to be treated on an individual basis:

1. NDNP Open OCR (currently in functions/src). This is the NDNP Open OCR pipeline that can be run locally or at scale in AWS. It has all of the OCR logic in it.
2. Terraform Deployment. This deploys NDNP Open OCR to AWS to run at scale.
3. Command Line Interface. This is the local CLI tool that can be used and distributed to control the AWS infrastructure laid out by Terraform.



# Deployment
## AWS Resources

The module creates AWS resources for the application including:

- **IAM Roles and Policies**: To allow the Lambdas/Fargate tasks to access S3, use DynamoDB table, etc...
- **Lambda Functions**: Includes scheduler function for creating SQS messages.
- **SQS Queue**: For storing a message for each TIFF that needs to be processed by the Fargate tasks that hold NDNP Open OCR library.
- **S3 Bucket**: For storing the PDF and ALTO outputs from NDNP Open OCR.
- **Cloudwatch Log Groups**: For storing logs of the Lambda functions and ECS/Fargate tasks.

## Prerequisites

- Terraform v1.4.6
- AWS CLI already configured with sufficient permissions to deploy and maintain resources mentioned above. Currently we are using the NDNP_OPEN_OCR_DEVELOPMENT_DEV role to deploy these resources as we build the project forward.


## Deployment

To use this module:
1. Authenticate with AWS via idaptive CLI tool and set environment variables as follows:

```sh
idaptive-aws-cli-login -u USERNAME_HERE -t loc.my.idaptive.app -r us-east-2\
```
Select "6" (NDNP_OPEN_OCR_DEVELOPER_DEV), then set the AWS_PROFILE environment variable as follows:
```sh
export AWS_PROFILE=NDNP_OPEN_OCR_DEVELOPER_DEV_profile
```

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
