# FARGATE DEPLOYMENT IMAGE
FROM ndnp_open_ocr:latest

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

WORKDIR /app
COPY main.py main.py

# Flask App runs on Port 8080 to respond
# to health check HTTP requests
EXPOSE 8080
CMD [ "python", "main.py" ]
