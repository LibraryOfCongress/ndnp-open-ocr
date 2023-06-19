import os
import boto3
import json
import uuid

# Create Scheduler SQS messages to line out all the files that need to be processed in parallel.
def handler(event, context):
    # Get S3 bucket from environment variable
    # os.getenv('S3_BUCKET_NAME')
    bucket_name = os.getenv('OUTPUT_BUCKET_NAME')
    prefix = event['pathParameters']['prefix']
    if bucket_name is None:
        raise Exception("No S3_BUCKET_NAME environment variable set")

    # Create S3 resource and SQS client
    s3 = boto3.resource('s3')
    sqs = boto3.client('sqs')

    # print environment variables
    print(os.environ)

    # Set your SQS queue URL
    queue_url = os.environ.get('QUEUE_URL')

    print(queue_url)
    total_files = 0
    try:
        # Generate a unique UUID for the output path
        output_prefix = str(uuid.uuid4())
        # List all files in the bucket
        # List all files in the bucket
        messages = []
        for object_summary in s3.Bucket(bucket_name).objects.filter(Prefix=prefix):
            file_name = object_summary.key

            # Check if the file is a TIFF file
            if file_name.lower().endswith('.tif'):
                # Prepare message
                message = {
                    'Bucket': bucket_name,
                    'Key': file_name,
                    'OutputPrefix': output_prefix,
                    'InputPrefix': prefix,
                }

                messages.append({
                    'Id': str(uuid.uuid4()),
                    'MessageBody': json.dumps(message)
                })

                total_files += 1

            # Send batch of messages to SQS queue if length is 10
            if len(messages) == 10:
                response = sqs.send_message_batch(
                    QueueUrl=queue_url,
                    Entries=messages
                )
                messages = []

        # Send remaining messages, if any
        if messages:
            response = sqs.send_message_batch(
                QueueUrl=queue_url,
                Entries=messages
            )

        return {
            "statusCode": 200,
            "body": "NDNP Open OCR Job Successfully Scheduled. The output prefix in S3 is {}, and we are going to process {} files".format(output_prefix, total_files)
        }
    except Exception as e:
        print(e)
