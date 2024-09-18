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
	docker build --platform linux/arm64 -t ndnp_open_ocr_deploy:latest ./packages/ndnp_open_ocr_fargate_deployment

run_fargate:
	docker run -it -e AWS_PROFILE=loc1 -e PYTHONPATH=packages -e TABLE_NAME=ndnp-open-ocr-table -e OUTPUT_BUCKET_NAME=ndnp-open-ocr-output-bucket-test -v ~/.aws:/root/.aws -v $(PWD):/app -w /app ndnp-open-ocr-container-repo:latest bash

push_fargate:
	aws ecr get-login-password --region us-east-2 --profile loc1 | docker login --username AWS --password-stdin 420280634985.dkr.ecr.us-east-2.amazonaws.com
	docker build --platform linux/amd64 -t ndnp_open_ocr:latest ./packages/ndnp_open_ocr
	docker build --platform linux/amd64 -t ndnp-open-ocr-container-repo:latest ./packages/ndnp_open_ocr_fargate_deployment
	docker tag ndnp-open-ocr-container-repo:latest 420280634985.dkr.ecr.us-east-2.amazonaws.com/ndnp-open-ocr-container-repo:latest
	docker push 420280634985.dkr.ecr.us-east-2.amazonaws.com/ndnp-open-ocr-container-repo:latest