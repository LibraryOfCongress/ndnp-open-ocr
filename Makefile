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

build_fargate:
	docker build --platform linux/arm64 -t ndnp_open_ocr:latest ./packages/ndnp_open_ocr
	docker build --platform linux/arm64 -t ndnp_open_ocr_deploy:latest .

run_fargate:
	docker run -it -v /Volumes/ExtremeSSD/:/Volumes/ExtremeSSD -w /app ndnp_open_ocr_deploy:latest bash

push_fargate:
	docker build -t ndnp-open-ocr-container-repo .
	docker tag ndnp-open-ocr-container-repo:latest 420280634985.dkr.ecr.us-east-2.amazonaws.com/ndnp-open-ocr-container-repo:latest
	docker push 420280634985.dkr.ecr.us-east-2.amazonaws.com/ndnp-open-ocr-container-repo:latest