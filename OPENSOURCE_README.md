# NDNP Open OCR (Open-Source Guide)

This document captures the pieces that matter most when running NDNP Open OCR outside of the Library of Congress network. It focuses on the local developer loop, the AWS deployment path, and the CLI workflow used to orchestrate OCR jobs.

## Quick Start

### Local batch testing (file:// inputs or S3)

1. **Build the runtime container** (installs Tesseract and all Python deps):
   ```bash
   make build-ocr-image
   ```
2. **(Optional) stage sample data** so you have a known-good TIFF/JP2 pair:
   ```bash
   make prep-testdata
   ```
3. **Open an OCR shell** that mounts your input/output directories:
   ```bash
   make ocr-shell \
     MOUNT_IN=/ABS/PATH/to/tifs \
     MOUNT_OUT=/ABS/PATH/to/out \
     SOURCE_URI='file:///data/in' \
     SINK_URI='file:///data/out'
   ```
4. **Run the pipeline** from inside the shell:
   ```bash
   python -m ndnp_open_ocr.run_local --glob '**/*.tif' --segmentation true
   ```
   `SOURCE_URI`/`SINK_URI` accept both `file://` and `s3://` URIs, so you can pull directly from S3 if desired.

### AWS deployment + CLI workflow

1. **Configure AWS credentials** for the target account (environment variables, shared config/credentials file, SSO, etc.).
2. **Provision infrastructure**:
   ```bash
   terraform init
   terraform plan
   terraform apply
   ```
   Customize variables such as `s3_bucket_name`, `env`, `batch_image_tag`, or the backend configuration so the stack names match your environment.
3. **Wire the CLI to your deployment** by editing `packages/cli/ndnp_openocr/config.py` (bucket name + Lambda ARNs). If you publish the CLI, regenerate this file per environment or inject it during your build.
4. **Install the CLI**:
   ```bash
   cd packages/cli
   poetry install
   # or: poetry build && pip install dist/ndnp_openocr-*.whl
   ```
5. **Run jobs end-to-end**:
   ```bash
   # Kick off a Batch-backed OCR job
   ndnp_openocr reprocess --batch_name batch_example --bucket my-ingest-bucket --segmentation

   # Poll for status
   ndnp_openocr get --job JOB_ID

   # Sync S3 outputs into a local batch for validation
   ndnp_openocr sync --job JOB_ID \
     --local-batch /path/to/original_batch \
     --output-dir /path/to/output_batch
   ```
   Clean up with `ndnp_openocr delete --job-id JOB_ID --output-dir /path/to/output_batch` when you are finished.

## Infrastructure Overview

Terraform creates the AWS resources NDNP Open OCR needs to run at scale:

- **S3** for OCR outputs and, optionally, source inputs.
- **AWS Batch/ECS** for the heavy OCR workers.
- **Lambda** functions that back the CLI/API for job submission and status checks.
- **IAM roles/policies** that grant the workers access to S3, Batch, CloudWatch, etc.
- **CloudWatch log groups** for Lambdas and Batch jobs.

Deploy into a dedicated AWS account or VPC to keep costs and permissions isolated per project.

## Deployment Details

1. Set Terraform variables via `terraform.tfvars`, environment variables, or `-var` flags (e.g., `s3_bucket_name`, `env`, backend bucket/key).
2. Run `terraform init/plan/apply` as shown above.
3. Push the container image that AWS Batch references (see `Makefile` targets `build_fargate`, `push_fargate`, or adapt them to your registry/credentials).
4. Update any automation or CI pipelines to inject the correct `ndnp_openocr/config.py` before building the CLI.

## CLI Reference

`ndnp_openocr` exposes the following commands:

| Command    | Description |
|------------|-------------|
| `reprocess` | Invoke the scheduler Lambda to submit an AWS Batch array job. |
| `get`       | Fetch job status JSON from the get-job Lambda. |
| `sync`      | Merge Batch outputs from S3 into a local batch folder. |
| `delete`    | Remove job outputs from S3 and/or local disk. |
| `job_info`  | Display the last job/output directory stored in the OS keyring. |

The CLI stores the most recent `job_id` and `output_dir` in the OS keyring so you can omit `--job`/`--output-dir` after the first run. Use `ndnp_openocr --help` or `ndnp_openocr <command> --help` for option details.

## Next Steps

- Use `scripts/gen_python_licenses.sh` to refresh THIRD_PARTY_NOTICES when dependencies change.
- Keep Terraform state and backend configuration outside of this repository (e.g., remote state in your own S3 bucket).

