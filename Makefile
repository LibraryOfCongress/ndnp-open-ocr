build:
	docker build -t chronam_deploy:latest .
	docker create --name artifacts chronam_deploy:latest
	docker cp artifacts:/tmp/layer.zip .
	docker rm artifacts