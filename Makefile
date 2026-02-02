# Load .env and export all variables
ifneq (,$(wildcard ./.env))
    include .env
    export
endif

# Terraform variable exports
export TF_VAR_region=$(AWS_REGION)
export TF_VAR_env=$(ENVIRONMENT)
export TF_VAR_batch_image_tag=$(BATCH_IMAGE_TAG)
export TF_VAR_s3_bucket_name=$(S3_OUTPUT_BUCKET_PREFIX)

# Build config
PLATFORM ?= linux/amd64
IMAGE_NAME ?= ndnp_open_ocr:opensource1.1
AWS_MOUNT_FLAGS := -v $$HOME/.aws:/root/.aws:ro -v $$HOME/.aws:/home/appuser/.aws:ro
AWS_ENV_FLAGS := $(if $(AWS_PROFILE),-e AWS_PROFILE=$(AWS_PROFILE),) -e AWS_SDK_LOAD_CONFIG=1
AWS_REGION ?= us-east-2
ECR_REGISTRY ?= $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com
ECR_REPO ?= $(ECR_REPO_PREFIX)-$(ENVIRONMENT)
ECR_IMAGE_TAG ?= $(BATCH_IMAGE_TAG)
ECR_LOGIN_PROFILE ?= NDNP_OPEN_OCR_DEVELOPER_DEV-$(AWS_ACCOUNT_ID)

help:
	@echo "check-env        Show .env configuration"
	@echo "terraform-init   Initialize Terraform"
	@echo "terraform-plan   Plan Terraform changes"
	@echo "terraform-apply  Apply Terraform changes"
	@echo "terraform-destroy Destroy Terraform resources"
	@echo "build-ocr-image  Build OCR Docker image"
	@echo "build_fargate    Build Fargate images"
	@echo "push_fargate     Push to ECR"
	@echo "ocr-shell        Interactive container shell"
	@echo "install-cli      Install CLI tool"

build-ocr-image:
	docker build --platform $(PLATFORM) -t $(IMAGE_NAME) packages/ndnp_open_ocr

build_fargate:
	docker build --platform $(PLATFORM) -t ndnp_open_ocr:latest packages/ndnp_open_ocr
	docker build --platform $(PLATFORM) -t ndnp_open_ocr_deploy:latest packages/ndnp_open_ocr_fargate_deployment

push_fargate: build_fargate
	aws ecr get-login-password --region $(AWS_REGION) $(if $(ECR_LOGIN_PROFILE),--profile $(ECR_LOGIN_PROFILE),) | docker login --username AWS --password-stdin $(ECR_REGISTRY)
	docker tag ndnp_open_ocr_deploy:latest $(ECR_REGISTRY)/$(ECR_REPO):$(ECR_IMAGE_TAG)
	docker push $(ECR_REGISTRY)/$(ECR_REPO):$(ECR_IMAGE_TAG)

prep-testdata:
	@mkdir -p $(CURDIR)/testdata/issue0602
	@cp -f $(CURDIR)/packages/ndnp_open_ocr/0602.jp2 $(CURDIR)/testdata/issue0602/ 2>/dev/null || true
	@cp -f $(CURDIR)/packages/ndnp_open_ocr/0602.pdf $(CURDIR)/testdata/issue0602/ 2>/dev/null || true

ocr-shell: build-ocr-image
	@if [ -n "$$MOUNT_OUT" ]; then mkdir -p "$$MOUNT_OUT"; fi; \
	 docker run --rm -it --platform $(PLATFORM) $(RUN_USER_FLAG) \
	  -v "$(CURDIR)":/app \
	  $${MOUNT_IN:+-v "$$MOUNT_IN":/data/in} \
	  $${MOUNT_OUT:+-v "$$MOUNT_OUT":/data/out} \
	  $(AWS_MOUNT_FLAGS) $(AWS_ENV_FLAGS) \
	  -e TESSDATA_PREFIX=/usr/local/share/tessdata \
	  -e LD_LIBRARY_PATH=/usr/local/lib \
	  -e PYTHONPATH=/app/packages:/app \
	  -w /app $(IMAGE_NAME) bash

check-env:
	@if [ ! -f .env ]; then echo "ERROR: .env not found. Run: cp .env.example .env"; exit 1; fi
	@echo "AWS_ACCOUNT_ID=$(AWS_ACCOUNT_ID)"
	@echo "AWS_REGION=$(AWS_REGION)"
	@echo "ENVIRONMENT=$(ENVIRONMENT)"
	@echo "S3_OUTPUT_BUCKET_PREFIX=$(S3_OUTPUT_BUCKET_PREFIX)"
	@echo "BATCH_IMAGE_TAG=$(BATCH_IMAGE_TAG)"
	@echo "ECR_REPO_PREFIX=$(ECR_REPO_PREFIX)"

terraform-init:
	terraform init
	@if terraform workspace list | grep -q "$(ENVIRONMENT)"; then \
		terraform workspace select $(ENVIRONMENT); \
	else \
		terraform workspace new $(ENVIRONMENT); \
	fi

terraform-plan: check-env
	terraform plan

terraform-apply: check-env
	terraform apply

terraform-destroy: check-env
	terraform destroy

install-cli:
	pip install packages/cli

.PHONY: help build-ocr-image build_fargate push_fargate prep-testdata ocr-shell check-env terraform-init terraform-plan terraform-apply terraform-destroy install-cli
