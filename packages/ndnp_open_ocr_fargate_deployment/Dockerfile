# FARGATE DEPLOYMENT IMAGE
ARG BASE_TAG=latest
FROM ndnp_open_ocr:${BASE_TAG}

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

WORKDIR /app
COPY main.py main.py

# Flask App runs on Port 8080 to respond
# to health check HTTP requests
EXPOSE 8080
CMD [ "python", "main.py" ]
