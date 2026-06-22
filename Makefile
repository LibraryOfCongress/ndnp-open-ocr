# Load .env and export all variables for Make targets
ifneq (,$(wildcard ./.env))
    include .env
    export
endif

# Terraform variable exports (so `make check-env` confirms TF will see the right values)
export TF_VAR_region=$(AWS_REGION)
export TF_VAR_env=$(ENVIRONMENT)
export TF_VAR_batch_image_tag=$(BATCH_IMAGE_TAG)
export TF_VAR_s3_bucket_name=$(S3_OUTPUT_BUCKET_PREFIX)

PLATFORM ?= linux/amd64
IMAGE_NAME ?= ndnp_open_ocr:opensource1.1
# Mount AWS credentials for both root and appuser; pass profile/config env
# These are defaults that will be overridden by ENVs 
AWS_MOUNT_FLAGS := -v $$HOME/.aws:/root/.aws:ro -v $$HOME/.aws:/home/appuser/.aws:ro
AWS_ENV_FLAGS := $(if $(AWS_PROFILE),-e AWS_PROFILE=$(AWS_PROFILE),) -e AWS_SDK_LOAD_CONFIG=1
AWS_REGION ?= us-east-2
ECR_REGISTRY ?= $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com
ECR_REPO ?= $(ECR_REPO_PREFIX)-$(ENVIRONMENT)
ECR_IMAGE_TAG ?= $(BATCH_IMAGE_TAG)

# Set ECR_LOGIN_PROFILE (in .env or on the command line) to log in via a named profile.
ECR_LOGIN_PROFILE ?= NDNP_OPEN_OCR_DEVELOPER_DEV-$(AWS_ACCOUNT_ID)

# Sample NDNP pages for local testing: New-York Tribune (LCCN sn83030214), 1898-06-21.
# LOC.gov item page: https://www.loc.gov/item/sn83030214/1898-06-21/ed-1/
SAMPLE_BASE  ?= https://tile.loc.gov/storage-services/service/ndnp/dlc/batch_dlc_universal_ver02/data/sn83030214/00175036866/1898062101
SAMPLE_PAGES ?= 0423 0424
SAMPLE_DIR   := $(CURDIR)/testdata/sample/sn83030214
# tile.loc.gov serves the JP2 openly but gates the page PDF behind a loc.gov Referer;
# send one so the original PDF (used for XMP metadata transfer) downloads.
SAMPLE_CURL  := curl -fsSL --retry 3 -H "Referer: https://www.loc.gov/"

help:
	@echo "Common targets:"
	@echo "  check-env        Show .env configuration and TF_VAR exports"
	@echo "  build-ocr-image  Build the local OCR runtime Docker image ($(IMAGE_NAME))"
	@echo "  prep-testdata    Download sample pages from the Library of Congress"
	@echo "  demo             Build + fetch sample data + run OCR on it (outputs to ./output)"
	@echo "  ocr-shell        Open an interactive container; set MOUNT_IN/MOUNT_OUT to mount paths"
	@echo "  build_fargate    Build Fargate/Batch images (runtime + deploy wrapper)"
	@echo "  push_fargate     Build and push deploy image to ECR ($(ECR_REGISTRY)/$(ECR_REPO):$(ECR_IMAGE_TAG))"
	@echo "  install-cli      Install CLI tool via pip"

# Build the NDNP Open OCR library image (used for local runs)
build-ocr-image:
	docker build --platform $(PLATFORM) -t $(IMAGE_NAME) packages/ndnp_open_ocr

# Build the runtime image and the deploy wrapper used by Fargate/Batch
build_fargate:
	# Build the core OCR runtime image
	docker build --platform $(PLATFORM) -t ndnp_open_ocr:latest packages/ndnp_open_ocr
	# Build the Fargate/Batch wrapper that runs the pipeline
	docker build --platform $(PLATFORM) -t ndnp_open_ocr_deploy:latest packages/ndnp_open_ocr_fargate_deployment

# Push the deploy wrapper image to ECR
push_fargate: build_fargate
	# Log in to ECR using the configured profile/region
	aws ecr get-login-password --region $(AWS_REGION) $(if $(ECR_LOGIN_PROFILE),--profile $(ECR_LOGIN_PROFILE),) | docker login --username AWS --password-stdin $(ECR_REGISTRY)
	# Tag and push the deploy image to the configured repo:tag
	docker tag ndnp_open_ocr_deploy:latest $(ECR_REGISTRY)/$(ECR_REPO):$(ECR_IMAGE_TAG)
	docker push $(ECR_REGISTRY)/$(ECR_REPO):$(ECR_IMAGE_TAG)

# Download a couple of real NDNP newspaper pages (JP2 + source PDF) so you have
# runnable input without needing your own batch. 
prep-testdata:
	@mkdir -p "$(SAMPLE_DIR)"
	@for p in $(SAMPLE_PAGES); do \
	  [ -s "$(SAMPLE_DIR)/$$p.jp2" ] || $(SAMPLE_CURL) -o "$(SAMPLE_DIR)/$$p.jp2" "$(SAMPLE_BASE)/$$p.jp2"; \
	  [ -s "$(SAMPLE_DIR)/$$p.pdf" ] || $(SAMPLE_CURL) -o "$(SAMPLE_DIR)/$$p.pdf" "$(SAMPLE_BASE)/$$p.pdf"; \
	done
	@echo "Sample data in $(SAMPLE_DIR) — run 'make demo' to OCR it."

# One-shot demo: build the image (if needed), fetch sample data, and run baseline OCR on it.
# The generated PDF + ALTO land in ./output. Quickest way to see the pipeline actually work.
demo: build-ocr-image prep-testdata
	@mkdir -p "$(CURDIR)/output"
	# Mount only the sample input + output dirs and run the image's baked-in code
	docker run --rm --platform $(PLATFORM) $(RUN_USER_FLAG) \
	  -v "$(CURDIR)/testdata/sample":/data/in:ro \
	  -v "$(CURDIR)/output":/data/out \
	  $(IMAGE_NAME) \
	  python -m ndnp_open_ocr.run_local --input file:///data/in --output file:///data/out --glob '**/*.jp2' --segmentation true
	@echo "Output PDF + ALTO are in $(CURDIR)/output"

# Open an interactive shell inside the OCR image with optional host mounts
ocr-shell: build-ocr-image
	# Usage: make ocr-shell MOUNT_IN=/abs/path/to/in MOUNT_OUT=/abs/path/to/out AWS_PROFILE=dev
	# Then inside the container, run: python -m ndnp_open_ocr.run_local --input file:///data/in --output file:///data/out --glob '**/*.tif' --segmentation true
	@if [ -n "$$MOUNT_OUT" ]; then mkdir -p "$$MOUNT_OUT"; fi; \
	 echo "Opening OCR shell (optional mounts: MOUNT_IN, MOUNT_OUT)."; \
	 docker run --rm -it --platform $(PLATFORM) $(RUN_USER_FLAG) \
	  -v "$(CURDIR)":/app \
	  $${MOUNT_IN:+-v "$$MOUNT_IN":/data/in} \
	  $${MOUNT_OUT:+-v "$$MOUNT_OUT":/data/out} \
	  $(AWS_MOUNT_FLAGS) \
	  $(AWS_ENV_FLAGS) \
	  -e TESSDATA_PREFIX=/usr/local/share/tessdata \
	  -e LD_LIBRARY_PATH=/usr/local/lib \
	  -e PYTHONPATH=/app/packages:/app \
	  -w /app \
	  $(IMAGE_NAME) \
	  bash

check-env:
	@if [ ! -f .env ]; then echo "ERROR: .env not found. Run: cp .env.example .env"; exit 1; fi
	@echo "AWS_ACCOUNT_ID=$(AWS_ACCOUNT_ID)"
	@echo "AWS_REGION=$(AWS_REGION)"
	@echo "ENVIRONMENT=$(ENVIRONMENT)"
	@echo "S3_OUTPUT_BUCKET_PREFIX=$(S3_OUTPUT_BUCKET_PREFIX)"
	@echo "BATCH_IMAGE_TAG=$(BATCH_IMAGE_TAG)"
	@echo "ECR_REPO_PREFIX=$(ECR_REPO_PREFIX)"
	@echo "TF_VAR_region=$(TF_VAR_region)"
	@echo "TF_VAR_env=$(TF_VAR_env)"
	@echo "TF_VAR_batch_image_tag=$(TF_VAR_batch_image_tag)"
	@echo "TF_VAR_s3_bucket_name=$(TF_VAR_s3_bucket_name)"

install-cli:
	pip install packages/cli

.PHONY: help build-ocr-image build_fargate push_fargate prep-testdata demo ocr-shell check-env install-cli
