

# NDNP Open OCR - Library of Congress

This repository contains a Terraform module for creating resources required for deploying the NDNP Open OCR application into an AWS account. The application uses Lambda for processing and SQS message creation, SQS for keeping track of which files need to be processed and lining them up for ingest by worker Lambdas, and S3 for storing outputs.

There are 3 primary components that need to be treated on an individual basis:

1. NDNP Open OCR (currently in packages/ndnp_open_ocr). This is the NDNP Open OCR pipeline that can be run locally or at scale in AWS. It has all of the OCR logic in it.
2. Terraform Deployment. This deploys NDNP Open OCR to AWS to run at scale.
3. Command Line Interface. This is the local CLI tool that can be used and distributed to control the AWS infrastructure laid out by Terraform.



# Deployment
## AWS Resources

The module creates AWS resources for the application including:

- **IAM Roles and Policies**: To allow the Lambdas/Fargate tasks to access S3, trigger AWS Batch, etc...
- **Lambda Functions**: Includes scheduler function for creating new job in AWS Batch
- **S3 Bucket**: For storing the PDF and ALTO outputs from NDNP Open OCR.
- **Cloudwatch Log Groups**: For storing logs of the Lambda functions and ECS/Fargate tasks.

## Recommended AWS Account Setup

We recommend running NDNP Open OCR in a hermetically sealed AWS account that is a child account within an AWS Organizations parent (management) account. This approach keeps project resources isolated, simplifies lifecycle tasks (fast spin-up, spin-down, and closure), and enables clearer cost allocation and stronger, project-scoped permissions.

- Isolate per project: minimize blast radius and avoid cross-project interference.
- Simplify billing: use consolidated billing to break out costs by account/project.
- Streamline lifecycle: create, suspend, or close entire environments quickly.
- Maximize least privilege: apply policies and guardrails specific to the project.

Helpful AWS guides for setup:

- What is AWS Organizations: https://docs.aws.amazon.com/organizations/latest/userguide/orgs_introduction.html
- Create an organization: https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_org_create.html
- Create an account in your organization (sub-account): https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_accounts_create.html
- Work with organizational units (OUs): https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_ous.html
- Getting started with AWS Organizations: https://docs.aws.amazon.com/organizations/latest/userguide/orgs_getting-started.html


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
