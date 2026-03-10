# NDNP Open OCR

**NDNP-Open-OCR** is an open-source pipeline developed by the Library of Congress to reprocess and improve the quality of Optical Character Recognition (OCR) text from digitized historical newspapers.

This software is designed to work specifically with data produced under the [National Digital Newspaper Program (NDNP)](https://www.loc.gov/ndnp/) technical specification. NDNP is a collaborative partnership involving the National Endowment for the Humanities (NEH), the Library of Congress, and various participating institutions, all of which contribute to the [Chronicling America Historic Newspaper](https://www.loc.gov/collections/chronicling-america/about-this-collection/) website. Library of Congress staff have added NDNP data processed with this pipeline to Chronicling America since 2024.


## What does the **NDNP-Open-OCR** pipeline do?
**At a high level, NDNP-Open-OCR...**
- works with existing NDNP data packages (batches) as its input, 
- creates new ALTO XML and PDF files for every newspaper scan in a batch,
- can be deployed locally or in common cloud environments,
- uses the Tesseract OCR engine and custom post-processing steps,
- is accessed via a command line interface (CLI), and
- has potential to be adapted for other data.

While **NDNP-Open-OCR** is most relevant for parties using the NDNP technical specification, we envision the pipeline to be useful for a number of other use cases. 


[Read more about the Library of Congress' newspaper OCR reprocessing effort here](https://guides.loc.gov/chronicling-america/improved-text).

[Read more about the NDNP Technical Specification here](https://www.loc.gov/ndnp/).

## Advanced Segmentation Setting
Historical newspapers are complex documents with a variety of page and column layouts that can be challenging for OCR engines to parse. All versions of **NDNP-Open-OCR** use Tesseract's generalized layout detection model. **NDNP-Open-OCR** version 1.1 and later includes an option to use an advanced segmentation setting that more accurately identifies columns, text, and other regions on historical newspaper scans. This setting incorporates newspaper layout detection modeling from the American Stories (Harvard) dataset. 
[Read more about Harvard's American Stories project here](https://dell-research-harvard.github.io/resources/americanstories).

## Contact
We are sharing this pipeline to advance a core objective of the NDNP: improving access to historical American newspapers. We encourage you to share with us how you are using the code and welcome your feedback.

For questions or support, contact NDNP staff at the Library of Congress (ndnptech@loc.gov).

## Quick Start (Open-Source Guide for Developers)
This document captures the pieces that matter most when running **NDNP-Open-OCR** outside of the Library of Congress network. It focuses on the local developer loop, the AWS deployment path, and the CLI workflow used to orchestrate OCR jobs.

### Note

- These instructions currently use AWS as the cloud environment.
  

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
     MOUNT_OUT=/ABS/PATH/to/out
   ```
4. **Run the pipeline** from inside the shell:
   ```bash
   python -m ndnp_open_ocr.run_local \
     --source file:///data/in \
     --sink file:///data/out \
     --glob '**/*.tif' \
     --segmentation true
   ```
   `--source`/`--sink` accept both `file://` and `s3://` URIs, so you can pull directly from S3 if desired.

### AWS deployment + CLI workflow

### 1. Configure AWS credentials
 for the target account (environment variables, shared config/credentials file, SSO, etc.).
### 2. Configure environment-specific Terraform variables
   Before deploying, update the following varibales in `variables.tf` to match your environment **or** override them at runtime using `-var`
   ```hcl
   s3_bucketname
   env
   batch_image_tag
   ```
   These values control resource naming/isolation and the tagging container image used by openocr

### 3. Provision infrastructure:
   Run `make check-env` to verify your `.env` values and TF_VAR exports before running Terraform.

   If this a **fresh install in a new AWS account** (ie. you are not using an existing Terraform state)
   1. **Update the Terraform backend configuration**
      Configure the backend to use an **s3 bucket and key** owned by this AWS account.
      You may do this in **one of two ways**:
      **Option A - Edit the backend configuration in code**
      Update `backend "s3" configuration to point to the correct bucket and key for this account.
      **Option B - Override the backends at initilization time**
      Supply backend values using `-backend-config` during initialization.

   2. **Initialize Terraform**
   ```bash
   terraform init --reconfigure
   ```
   Or when overriding backend values explicitly:

   ```bash
      terraform init -reconfigure \
      -backend-config="bucket=<state-bucket-name>" \
      -backend-config="key=<state-key-path>" \
      -backend-config="region=<aws-region>"
      ```

   the `--reconfigure` ensures Terraform does not attempt to read or migrate an existing remote state. If this not a new AWS account, ommit the `--reconfigure` flag.

   3. **Review and apply the plan**
   ```bash
      terraform plan
      terraform apply
   ```

   4. **Build fargate image for ndnp openocr**
      1. **Update Makefile variables**
         * AWS Account ID
         * region
         * Any other environment-specific values

      2. **Build and push image**
         ```bash
            make build_fargate  # This takes about 15 minutes
            make push_fargate
         ```

### 4. Wire the CLI to your deployment
 By editing `packages/cli/ndnp_openocr/config.py` (bucket name + Lambda ARNs). If you publish the CLI, regenerate this file per environment or inject it during your build.
5. **Install the CLI** (from the repository root):
   ```bash
   make install-cli
   ```
6. **Run jobs end-to-end** (from the repository root):
   ```bash
   # Kick off a Batch-backed OCR job (processes TIF files by default)
   ndnp_openocr process --batch_name <batch_prefix_in_input_bucket> --bucket <input_bucket_name> --segmentation

   # To process JP2 files instead of TIF
   ndnp_openocr process --batch_name <batch_prefix_in_input_bucket> --bucket <input_bucket_name> --img-extension=jp2

   # Poll for status
   ndnp_openocr get --job JOB_ID

   # Sync S3 outputs into a local batch for validation
   ndnp_openocr sync --job JOB_ID \
     --local-batch /path/to/original_batch \
     --output-dir /path/to/output_batch
   ```
   Clean up with `ndnp_openocr delete --job-id JOB_ID --output-dir /path/to/output_batch` when you are finished.
   Notes:
   - `batch_name` is the prefix of the batch in the input bucket you want to process.
   - `bucket` is the S3 bucket containing that batch.
   - `--segmentation` enables the AmericanStories segmentation model for improved layout detection (omit to use baseline Tesseract layout).
   - `--img-extension` specifies the image file type to process: `tif` (default) or `jp2`.

## AmericanStories Assets (optional)

AmericanStories models power the optional segmentation path (e.g., `--segmentation` in the CLI) and are pulled into the Docker image during the build. Licensing and model refresh notes for those assets are tracked in `OPENSOURCE_README.md` in the AmericanStories project.

If you omit the AmericanStories code/models, NDNP Open OCR still builds and runs the core Tesseract-based pipeline. The trade-off is limited functionality: segmentation-aware features are disabled and outputs remain page-level rather than article-aware. Use this mode when licensing constraints prevent bundling the AmericanStories assets.

## Infrastructure Overview

Terraform creates the AWS resources NDNP Open OCR needs to run at scale:

- **S3** for OCR outputs and, optionally, source inputs.
- **AWS Batch/ECS** for the heavy OCR workers.
- **Lambda** functions that back the CLI/API for job submission and status checks.
- **IAM roles/policies** that grant the workers access to S3, Batch, CloudWatch, etc.
- **CloudWatch log groups** for Lambdas and Batch jobs.

Deploy into a dedicated AWS account or VPC to keep costs and permissions isolated per project.

## Deployment Details

1. Configure `.env` (see `.env.example`) and run `make check-env` to verify values. Terraform picks up `TF_VAR_*` exports from `.env` via the Makefile.
2. Run `terraform init/plan/apply` as shown above.
3. Build the Batch container image (`make build-ocr-image` or `docker build ...`) and push it to your registry for the target environment.
4. Update any automation or CI pipelines to inject the correct `ndnp_openocr/config.py` before building the CLI.

## CLI Reference

**Note:** Run all CLI commands from the repository root directory where `.env` is located.

`ndnp_openocr` exposes the following commands:

| Command    | Description |
|------------|-------------|
| `process` | Invoke the scheduler Lambda to submit an AWS Batch array job. |
| `get`       | Fetch job status JSON from the get-job Lambda. |
| `sync`      | Merge Batch outputs from S3 into a local batch folder. |
| `delete`    | Remove job outputs from S3 and/or local disk. |
| `job_info`  | Display the last job/output directory stored in the OS keyring. |

The CLI stores the most recent `job_id` and `output_dir` in the OS keyring so you can omit `--job`/`--output-dir` after the first run. Use `ndnp_openocr --help` or `ndnp_openocr <command> --help` for option details.

## Next Steps

- Use `scripts/gen_python_licenses.sh` to refresh THIRD_PARTY_NOTICES when dependencies change.
- Keep Terraform state and backend configuration outside of this repository (e.g., remote state in your own S3 bucket).
