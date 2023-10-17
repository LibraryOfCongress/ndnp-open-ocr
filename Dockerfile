FROM ndnp_open_ocr:latest

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

WORKDIR /app
COPY main.py main.py


EXPOSE 8080
CMD [ "python", "main.py" ]
