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
ECR_LOGIN_PROFILE ?= NDNP_OPEN_OCR_DEVELOPER_DEV-$(AWS_ACCOUNT_ID)

help:
	@echo "Common targets:"
	@echo "  check-env        Show .env configuration and TF_VAR exports"
	@echo "  build-ocr-image  Build the local OCR runtime Docker image ($(IMAGE_NAME))"
	@echo "  prep-testdata    Copy bundled sample into testdata/issue0602"
	@echo "  ocr-shell        Open an interactive container; set MOUNT_IN/MOUNT_OUT to mount paths"
	@echo "  build_fargate    Build Fargate/Batch images (runtime + deploy wrapper)"
	@echo "  push_fargate     Build and push deploy image to ECR ($(ECR_REGISTRY)/$(ECR_REPO):$(ECR_IMAGE_TAG))"
	@echo "  install-cli      Install CLI tool via pip"

# Build the NDNP Open OCR library image (used for local runs)
build-ocr-image:
	docker build --platform $(PLATFORM) -t $(IMAGE_NAME) packages/ndnp_open_ocr

# Build the runtime image and the deploy wrapper used by Fargate/Batch
build_fargate:
	docker build --platform $(PLATFORM) -t ndnp_open_ocr:latest packages/ndnp_open_ocr
	docker build --platform $(PLATFORM) -t ndnp_open_ocr_deploy:latest packages/ndnp_open_ocr_fargate_deployment

# Push the deploy wrapper image to ECR
push_fargate: build_fargate
	aws ecr get-login-password --region $(AWS_REGION) $(if $(ECR_LOGIN_PROFILE),--profile $(ECR_LOGIN_PROFILE),) | docker login --username AWS --password-stdin $(ECR_REGISTRY)
	docker tag ndnp_open_ocr_deploy:latest $(ECR_REGISTRY)/$(ECR_REPO):$(ECR_IMAGE_TAG)
	docker push $(ECR_REGISTRY)/$(ECR_REPO):$(ECR_IMAGE_TAG)

# Prepare local test data (copies 0602 samples into openocr/testdata/issue0602)
prep-testdata:
	@mkdir -p $(CURDIR)/testdata/issue0602
	@cp -f $(CURDIR)/packages/ndnp_open_ocr/0602.jp2 $(CURDIR)/testdata/issue0602/ 2>/dev/null || true
	@cp -f $(CURDIR)/packages/ndnp_open_ocr/0602.pdf $(CURDIR)/testdata/issue0602/ 2>/dev/null || true
	@echo "Prepared test data at $(CURDIR)/testdata/issue0602"

# Open an interactive shell inside the OCR image with optional host mounts
ocr-shell: build-ocr-image
	@if [ -n "$$MOUNT_OUT" ]; then mkdir -p "$$MOUNT_OUT"; fi; \
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

.PHONY: help build-ocr-image build_fargate push_fargate prep-testdata ocr-shell check-env install-cli
