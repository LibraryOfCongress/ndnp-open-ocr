

# NDNP Open OCR - Library of Congress

This repository contains a Terraform module for creating resources required for deploying the NDNP Open OCR application into an AWS account. The application uses Lambda for processing and SQS message creation, SQS for keeping track of which files need to be processed and lining them up for ingest by worker Lambdas, and S3 for storing outputs.

There are 3 primary components that need to be treated on an individual basis:

1. NDNP Open OCR (currently in packages/ndnp_open_ocr). This is the NDNP Open OCR pipeline that can be run locally or at scale in AWS. It has all of the OCR logic in it.
2. Terraform Deployment. This deploys NDNP Open OCR to AWS to run at scale.
3. Command Line Interface. This is the local CLI tool that can be used and distributed to control the AWS infrastructure laid out by Terraform.


## Quick Start

### Local batch testing (file:// inputs)

1. Build the runtime image (installs Tesseract, Python deps, etc.):

   ```bash
   make build-ocr-image
   ```

2. (Optional) copy the bundled sample issue into `testdata/issue0602` to have a known-good TIFF/JP2 pair handy:

   ```bash
   make prep-testdata
   ```

3. Open an interactive shell with optional host mounts that expose your local TIFF directory and the destination for results. Any absolute paths work; the snippet below assumes `/ABS/PATH/to/tifs` contains NDNP-format issues.

   ```bash
   make ocr-shell \
     MOUNT_IN=/ABS/PATH/to/tifs \
     MOUNT_OUT=/ABS/PATH/to/out
   ```

   Inside the shell (which already has `PYTHONPATH` and Tesseract wired up), run:

   ```bash
   python -m ndnp_open_ocr.run_local \
     --source file:///data/in \
     --sink file:///data/out \
     --glob '**/*.tif' \
     --segmentation true
   ```

   The runner lists inputs under `/data/in`, processes each in a temp directory, and writes PDFs/ALTOS to `/data/out`. Swap `file://` for `s3://` URIs if you prefer to read/write directly from S3.

### AWS deployment + CLI workflow

1. Configure AWS credentials for the account where you want to host NDNP Open OCR. Export an `AWS_PROFILE`, `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`, or rely on SSO—Terraform and the CLI use the standard AWS SDK chain.

2. Provision the infrastructure:

   ```bash
   terraform init
   terraform plan
   terraform apply
   ```

   Customize any variables (e.g., `s3_bucket_name`, `env`, `batch_image_tag`) via `terraform.tfvars` or `-var` flags so the stack names match your account.

3. Point the CLI at your deployment by editing `packages/cli/ndnp_openocr/config.py` (bucket name plus Lambda ARNs) or by injecting those values during your build process.

4. Install the CLI:

   **From the GitLab Package Registry** (recommended):
   ```bash
   pip install ndnp_openocr --index-url https://gitlab-ci-token:<your_personal_token>@git.loc.gov/api/v4/projects/2983/packages/pypi/simple
   ```

   **From source** (requires [Poetry](https://python-poetry.org/docs/#installation)):
   ```bash
   cd packages/cli
   poetry install
   ```

5. Use the CLI to exercise the pipeline end to end:

   ```bash
   # Kick off a job against an S3 batch (processes TIF files by default)
   ndnp_openocr process --batch_name=batch_example --bucket=my-ingest-bucket --segmentation

   # To process JP2 files instead of TIF
   ndnp_openocr process --batch_name=batch_example --bucket=my-ingest-bucket --img-extension=jp2

   # Poll for status (uses stored job id if --job omitted)
   ndnp_openocr get --job JOB_ID_FROM_REPROCESS

   # Download the outputs and merge with a local batch for validation
   ndnp_openocr sync --job JOB_ID_FROM_REPROCESS \
     --local-batch /path/to/original_batch \
     --output-dir /path/to/output_batch
   ```

   Additional helpers such as `ndnp_openocr delete` (cleanup) and `ndnp_openocr job_info` (current config snapshot) are available; run `ndnp_openocr --help` for the full list.



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

passing that as the "prefix" will only process batches in the 1877083101 directory.
