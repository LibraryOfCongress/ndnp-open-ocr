# -----------------------------------------------------------------------------
# Fargate image build + ECR push helpers
# -----------------------------------------------------------------------------
ECR_IMAGE_TAG ?= opensource1.1

.PHONY: build_fargate run_fargate push_fargate

build_fargate:
	docker build --platform $(PLATFORM) -t ndnp_open_ocr:latest ./packages/ndnp_open_ocr
	docker build --platform $(PLATFORM) -t ndnp_open_ocr_deploy:latest ./packages/ndnp_open_ocr_fargate_deployment

run_fargate: build_fargate
	docker run -it --platform $(PLATFORM) \
		$(RUN_USER_FLAG) \
		-v "$(CURDIR)":/app \
		$(AWS_MOUNT_FLAGS) \
		$(AWS_ENV_FLAGS) \
		-e PYTHONPATH=packages \
		-e TABLE_NAME=ndnp-open-ocr-table \
		-e OUTPUT_BUCKET_NAME=ndnp-open-ocr-output-bucket-test \
		-w /app \
		ndnp_open_ocr_deploy:latest \
		bash

push_fargate: build_fargate
	aws ecr get-login-password --region us-east-2 --profile NDNP_OPEN_OCR_DEVELOPER_DEV-342134162356 | docker login --username AWS --password-stdin 342134162356.dkr.ecr.us-east-2.amazonaws.com
	docker tag ndnp_open_ocr_deploy:latest 342134162356.dkr.ecr.us-east-2.amazonaws.com/ndnp-open-ocr-container-repo-development-deployment:$(ECR_IMAGE_TAG)
	docker push 342134162356.dkr.ecr.us-east-2.amazonaws.com/ndnp-open-ocr-container-repo-development-deployment:$(ECR_IMAGE_TAG)

# -----------------------------------------------------------------------------

OUT_DIR            ?= $(CURDIR)/packages/output
PLATFORM ?= linux/amd64
# Mount AWS credentials for both root and appuser; pass profile/config env
AWS_MOUNT_FLAGS := -v $$HOME/.aws:/root/.aws:ro -v $$HOME/.aws:/home/appuser/.aws:ro
AWS_ENV_FLAGS := $(if $(AWS_PROFILE),-e AWS_PROFILE=$(AWS_PROFILE),) -e AWS_SDK_LOAD_CONFIG=1

# Build the NDNP Open OCR library image (used for local runs)
.PHONY: build-ocr-image
build-ocr-image:
	docker build --platform $(PLATFORM) -t ndnp_open_ocr:latest packages/ndnp_open_ocr


# Copy a small local test set (0602 sample only) to the OUTPUT bucket under a deterministic prefix.
# Requires: OUTPUT_BUCKET_NAME (e.g., export OUTPUT_BUCKET_NAME=my-bucket)
# Optional: TEST_INPUT_PREFIX (default: ndnp_open_ocr_test/input)
.PHONY: s3-seed-test-inputs
s3-seed-test-inputs:
	@[ -n "$(OUTPUT_BUCKET_NAME)" ] || (echo "Set OUTPUT_BUCKET_NAME to your target bucket." >&2; exit 1)
	@echo "Seeding 0602 sample inputs to s3://$(OUTPUT_BUCKET_NAME)/$(TEST_INPUT_PREFIX)"
	aws s3 cp "$(CURDIR)/packages/ndnp_open_ocr/0602.jp2" s3://$(OUTPUT_BUCKET_NAME)/$(TEST_INPUT_PREFIX)/issue0602/0602.jp2
	-aws s3 cp "$(CURDIR)/packages/ndnp_open_ocr/0602.pdf" s3://$(OUTPUT_BUCKET_NAME)/$(TEST_INPUT_PREFIX)/issue0602/0602.pdf
	@echo "Seed complete."

# Run the deployment container against the seeded S3 input and write to a unique
# job output prefix. Cleans the outputs afterward by default.
#
# Requires: OUTPUT_BUCKET_NAME; AWS credentials
# Optional: TEST_INPUT_PREFIX (default: ndnp_open_ocr_test/input)
#           JOB_PREFIX (default: ndnp_open_ocr_test/output/<timestamp>)
#           INPUT_GLOB (default: **/0602.jp2)
#           USE_SEGMENTATION (default: empty/false)
#           ARRAY_INDEX (default: 0)
#           CLEAN_AFTER (default: true)
 

# Manually remove a job output prefix if you kept it around.
# Usage: make s3-clean-job-output JOB_PREFIX=ndnp_open_ocr_test/output/20250101...
 

# Download a job's outputs from S3 to a local directory for inspection.
# Usage:
#   make s3-download-job-output \
#        OUTPUT_BUCKET_NAME=my-bucket \
#        JOB_PREFIX=ndnp_open_ocr_test/output/20250928204246 \
#        OUT_DIR=$(CURDIR)/packages/output/inspect
.PHONY: s3-download-job-output
s3-download-job-output:
	@[ -n "$(OUTPUT_BUCKET_NAME)" ] || (echo "Set OUTPUT_BUCKET_NAME." >&2; exit 1)
	@[ -n "$(JOB_PREFIX)" ] || (echo "Set JOB_PREFIX (e.g., ndnp_open_ocr_test/output/2025...)." >&2; exit 1)
	@mkdir -p "$(OUT_DIR)"
	@echo "Downloading s3://$(OUTPUT_BUCKET_NAME)/$(JOB_PREFIX) -> $(OUT_DIR)"
	aws s3 sync --no-progress s3://$(OUTPUT_BUCKET_NAME)/$(JOB_PREFIX) "$(OUT_DIR)"

# Prepare local test data (copies 0602 samples into openocr/testdata/issue0602)
.PHONY: prep-testdata
prep-testdata:
	@mkdir -p $(CURDIR)/testdata/issue0602
	@cp -f $(CURDIR)/packages/ndnp_open_ocr/0602.jp2 $(CURDIR)/testdata/issue0602/ 2>/dev/null || true
	@cp -f $(CURDIR)/packages/ndnp_open_ocr/0602.pdf $(CURDIR)/testdata/issue0602/ 2>/dev/null || true
	@echo "Prepared test data at $(CURDIR)/testdata/issue0602"

# -----------------------------------------------------------------------------
# Open an interactive shell inside the OCR image with URIs pre-wired.
# Examples:
#   make ocr-shell SOURCE_URI='file:///ABS/PATH/in' SINK_URI='file:///ABS/PATH/out'
#   AWS_PROFILE=dev make ocr-shell SOURCE_URI='s3://bucket/in' SINK_URI='s3://bucket/out'
# Inside the shell, run:
#   PYTHONPATH=/app python -m ndnp_open_ocr.run_local --glob '**/*.tif' --segmentation true
.PHONY: ocr-shell
ocr-shell:
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
	  ndnp_open_ocr:latest \
	  bash
