FROM ndnp_open_ocr:latest

WORKDIR /app
COPY main.py main.py

CMD [ "python", "main.py" ]