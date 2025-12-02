build:
	docker build -t ndnp_open_ocr:latest .

run:
	docker run -it -v $(PWD):/app -w /app ndnp_open_ocr:latest bash

test:
	docker build --build-arg INCLUDE_TEST_DEPS=true -t ndnp_open_ocr:test .
	docker run --rm ndnp_open_ocr:test pytest
