build_x86:
	docker build --platform linux/amd64 -t chronam_deploy:latest .
	docker create --name artifacts chronam_deploy:latest
	docker cp artifacts:/tmp/layer.zip .
	docker rm artifacts

build_arm:
	docker build --platform linux/arm64 -t chronam_deploy_arm:latest .
	docker create --name artifacts chronam_deploy_arm:latest
	docker cp artifacts:/tmp/layer.zip .
	docker rm artifacts

# -----------------------------------------------------------------------------
# Defaults for URI runs and downloads
INPUT_GLOB_DEFAULT ?= **/0602.jp2
USE_SEGMENTATION   ?=
OUT_DIR            ?= $(CURDIR)/packages/output

 

# Build platform (override on Apple Silicon with PLATFORM=linux/arm64)
PLATFORM ?= linux/amd64
# Optional: run the container as root for local dev (set RUN_AS_ROOT=1)
RUN_AS_ROOT ?=
RUN_USER_FLAG := $(if $(RUN_AS_ROOT),--user 0,)
# Mount AWS credentials for both root and appuser; pass profile/config env
AWS_MOUNT_FLAGS := -v $$HOME/.aws:/root/.aws:ro -v $$HOME/.aws:/home/appuser/.aws:ro
AWS_ENV_FLAGS := $(if $(AWS_PROFILE),-e AWS_PROFILE=$(AWS_PROFILE),) -e AWS_SDK_LOAD_CONFIG=1

# Build the NDNP Open OCR library image (used for local runs)
.PHONY: build-ocr-image
build-ocr-image:
	docker build --platform $(PLATFORM) -t ndnp_open_ocr:latest packages/ndnp_open_ocr

# Run the local batch inside Docker against mounted input/output directories.
# Usage:
#   make run-local-batch SOURCE_DIR="/Volumes/PRO-G40/VA JP2 files" \
#                        OUT_DIR="$$HOME/Desktop/ndnp_open_ocr_out" \
#                        [INPUT_GLOB='**/0602.jp2'] \
#                        USE_SEGMENTATION=false
 

# Simulate the Fargate/Batch worker end-to-end against local files.
# Note: build the images once with `make build_fargate` before running.
# Usage examples:
#   make run-fargate-deployment-example \
#        SOURCE_DIR="$(PWD)/openocr/packages/ndnp_open_ocr" \
#        OUT_DIR="$(PWD)/openocr/packages/output" \
#        INPUT_GLOB='0602.jp2' \
#        USE_SEGMENTATION=false
# Notes:
#   - If INPUT_GLOB is omitted, we default to **/0602.jp2 (the representative sample).
#   - Outputs are written under OUT_DIR preserving relative paths.
 

# Simulate the Fargate/Batch worker using S3 as source/sink without deploying.
# Note: build the images once with `make build_fargate` before running.
# Requires AWS credentials; set AWS_PROFILE (or env creds). Example:
#   make run-fargate-deployment-s3-example \
#        SOURCE_URI='s3://my-bucket/data/ndnp/va/batch_foo/data' \
#        SINK_URI='file:///data/out' \
#        OUT_DIR='$(PWD)/openocr/packages/output' \
#        INPUT_GLOB='**/*.jp2' \
#        USE_SEGMENTATION=false
 

# -----------------------------------------------------------------------------
# S3 seeding and smoke test helpers
# -----------------------------------------------------------------------------

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
# Universal runner: pass INPUT_URI/OUTPUT_URI (file:// or s3://)
# Examples:
#   make run-uris INPUT_URI='file:///abs/path/in' \
#                  OUTPUT_URI='file:///abs/path/out' \
#                  INPUT_GLOB='**/0602.jp2' USE_SEGMENTATION=true
#
#   AWS_PROFILE=dev make run-uris INPUT_URI='s3://bucket/in/prefix' \
#                                 OUTPUT_URI='s3://bucket/out/prefix' \
#                                 INPUT_GLOB='**/*.tif' USE_SEGMENTATION=false
#
# If a URI is file://, this target bind-mounts the host path into the container
# and rewrites the URI to file:///data/in or file:///data/out accordingly.
.PHONY: run-uris
run-uris:
	@in_uri='$(or $(INPUT_URI),$(SOURCE_URI))'; out_uri='$(or $(OUTPUT_URI),$(SINK_URI))'; \
	 [ -n "$$in_uri" ] || { echo "Provide INPUT_URI (or legacy SOURCE_URI)" >&2; exit 1; }; \
	 [ -n "$$out_uri" ] || { echo "Provide OUTPUT_URI (or legacy SINK_URI)" >&2; exit 1; }; \
	 src_uri="$$in_uri"; sink_uri="$$out_uri"; \
	 in_mount=""; out_mount=""; env_src_uri="$$src_uri"; env_sink_uri="$$sink_uri"; \
	 if echo "$$src_uri" | grep -q '^file://'; then \
	   host_in=$${src_uri#file://}; \
	   env_src_uri='file:///data/in'; \
	   in_mount="-v \"$$host_in\":/data/in"; \
	 fi; \
	 if echo "$$sink_uri" | grep -q '^file://'; then \
	   host_out=$${sink_uri#file://}; \
	   mkdir -p "$$host_out"; \
	   env_sink_uri='file:///data/out'; \
	   out_mount="-v \"$$host_out\":/data/out"; \
	 fi; \
	 echo "Running with:"; \
	 echo "  SOURCE_URI=$$env_src_uri"; \
	 echo "  SINK_URI=$$env_sink_uri"; \
	 docker run --rm -it --platform $(PLATFORM) $(RUN_USER_FLAG) \
	  -v "$(CURDIR)":/app \
	  $$in_mount $$out_mount \
	  $(AWS_MOUNT_FLAGS) \
	  $(AWS_ENV_FLAGS) \
	  -e TESSDATA_PREFIX=/usr/local/share/tessdata \
	  -e LD_LIBRARY_PATH=/usr/local/lib \
	  -e PYTHONPATH=/app/packages:/app \
	  -w /app \
	  ndnp_open_ocr:latest \
	  bash -lc "python -m ndnp_open_ocr.run_local --input '$$env_src_uri' --output '$$env_sink_uri' --glob '$(if $(INPUT_GLOB),$(INPUT_GLOB),$(INPUT_GLOB_DEFAULT))' --segmentation '$(USE_SEGMENTATION)'"

# -----------------------------------------------------------------------------
# Open an interactive shell inside the OCR image with URIs pre-wired.
# Examples:
#   make ocr-shell SOURCE_URI='file:///ABS/PATH/in' SINK_URI='file:///ABS/PATH/out'
#   AWS_PROFILE=dev make ocr-shell SOURCE_URI='s3://bucket/in' SINK_URI='s3://bucket/out'
# Inside the shell, run:
#   PYTHONPATH=/app python -m ndnp_open_ocr.run_local --glob '**/*.tif' --segmentation true
.PHONY: ocr-shell
ocr-shell:
	@in_mount=""; out_mount=""; \
	 if [ -n "$(MOUNT_IN)" ]; then in_mount="-v \"$(MOUNT_IN)\":/data/in"; fi; \
	 if [ -n "$(MOUNT_OUT)" ]; then mkdir -p "$(MOUNT_OUT)"; out_mount="-v \"$(MOUNT_OUT)\":/data/out"; fi; \
	 echo "Opening OCR shell (optional mounts: MOUNT_IN, MOUNT_OUT)."; \
	 docker run --rm -it --platform $(PLATFORM) $(RUN_USER_FLAG) \
	  -v "$(CURDIR)":/app \
	  $$in_mount $$out_mount \
	  $(AWS_MOUNT_FLAGS) \
	  $(AWS_ENV_FLAGS) \
	  -e TESSDATA_PREFIX=/usr/local/share/tessdata \
	  -e LD_LIBRARY_PATH=/usr/local/lib \
	  -e PYTHONPATH=/app/packages:/app \
	  -w /app \
	  ndnp_open_ocr:latest \
	  bash
