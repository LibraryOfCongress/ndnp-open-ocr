# Use an official Python runtime as a parent image
FROM python:3.9

# Set the working directory in the container to /app
WORKDIR /app

# Add current directory contents into the container at /app
ADD . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir \
    boto3==1.23.10 \
    click==8.0.1 \
    requests==2.26.0 \
    tqdm==4.64.1

# Make port 80 available to the world outside this container
EXPOSE 80

# Run CLI tool when the container launches
CMD ["python", "cli.py"]