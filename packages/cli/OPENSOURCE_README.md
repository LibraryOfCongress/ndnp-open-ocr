# NDNP Open OCR CLI — Open Source Guide

The CLI submits jobs to the NDNP Open OCR stack, checks job status, and syncs AWS Batch outputs from S3 into a local batch directory. This guide assumes you are running outside Library of Congress networks.

## Install from source

Prereqs: Python 3.12+ and [Poetry](https://python-poetry.org/docs/#installation).

```sh
cd packages/cli
make install
```

Run commands from the same shell: `ndnp_openocr --help`.

## Configure

Set the environment-specific values in `ndnp_openocr/config.py`:
- `OUTPUT_BUCKET_NAME`
- `SCHEDULER_ARN` (Lambda that submits Batch jobs)
- `GET_JOB_ARN` (Lambda that returns job status)

## Authenticate to AWS

Ensure your AWS CLI is logged in and can assume the right roles. Any standard method works: `aws configure`, `aws sso login --profile <profile>`, or environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_PROFILE`, `AWS_REGION`).

## Common commands

`ndnp_openocr reprocess --batch_name BATCH --bucket BUCKET --segmentation`
: Submit a job for a batch in S3. Stores the `job_id` in your OS keyring. `BATCH` is the prefix of the batch in the input bucket; `BUCKET` is that input bucket. `--segmentation` uses the AmericanStories segmentation model for improved layout detection (omit to use baseline Tesseract layout).

`ndnp_openocr get --job JOB_ID`
: Fetch job status (default: last job from keyring if `--job` omitted).

`ndnp_openocr sync --job JOB_ID --local-batch /path/to/local_batch --output-dir /path/to/output_batch`
: Copy a local batch and replace PDFs/ALTO with outputs from S3. Remembers `job_id`/`output_dir` in keyring for reuse.

`ndnp_openocr delete --job-id JOB_ID --output-dir /path/to/output_batch`
: Delete the S3 job prefix and the local output directory.

`ndnp_openocr job_info`
: Print the currently remembered `job_id` and `output_dir`.

## Typical workflow

```sh
ndnp_openocr reprocess --batch_name my_batch --bucket my-bucket --segmentation
ndnp_openocr get                              # optional: check status (uses stored job_id)
ndnp_openocr sync --local-batch /data/batch   --output-dir /data/batch_out
ndnp_openocr delete --job-id JOB_ID --output-dir /data/batch_out   # cleanup when done
```

Notes:
- `batch_name` is the prefix in the input bucket you want to reprocess.
- `bucket` is the S3 bucket that holds that batch.
- `--segmentation` enables the AmericanStories segmentation model for better layout detection; drop it to use basic Tesseract layout.
