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