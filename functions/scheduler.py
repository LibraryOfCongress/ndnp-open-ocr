import os
import boto3
import json
import uuid
from datetime import datetime
import logging

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Sends out SQS messages to the ALTO and PDF Generation Queues to kickoff reprocessing job, where the consumers pick up
# the SQS messages and process them independently, Lambda by Lambda, TIFF by TIFF.
def handler(event, context):
    # Generate a new job id
    job_id = str(uuid.uuid4())
    bucket_name = os.getenv('INPUT_BUCKET_NAME')
    # Prefix to the "batch" data in INPUT_BUCKET, which for our cases is loc-preservation.
    prefix = event['pathParameters']['prefix']
    if bucket_name is None:
        raise Exception("No S3_BUCKET_NAME environment variable set")

    s3 = boto3.resource('s3')
    sqs = boto3.client('sqs')
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.getenv('TABLE_NAME'))

    logger.info('Environment variables: %s', os.environ)

    queue_url = os.environ.get('QUEUE_URL')
    alto_queue_url = os.environ.get('ALTO_QUEUE_URL')

    logger.info('Queue URL: %s', queue_url)
    total_files = 0
    try:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

        # Get top-level directory input name
        output_prefix = os.path.split(prefix)[1] + "__" + job_id
        messages = []

        keys = []
        for object_summary in s3.Bucket(bucket_name).objects.filter(Prefix=prefix):
            file_name = object_summary.key

            if file_name.lower().endswith('.tif'):
                keys.append(file_name)

        table.put_item(
            Item={
                'pk': 'JOB',
                'sk': job_id,
                'TotalMessages': len(keys),
                'RemainingMessages': len(keys),
                'Timestamp': timestamp
            }
        )

        # Loop through all TIFFs in the bucket.
        for key in keys:
            message = {
                'Bucket': bucket_name,
                'Key': key,
                'OutputPrefix': output_prefix,
                'InputPrefix': prefix,
                'JobId': job_id
            }

            messages.append({
                'Id': str(uuid.uuid4()),
                'MessageBody': json.dumps(message)
            })

            # Send messages in batches of 10 to speed up execution.
            if len(messages) == 10:
                # Send Messages to PDF Queue
                response = sqs.send_message_batch(
                    QueueUrl=queue_url,
                    Entries=messages
                )

                # Send Messages to ALTO Queue
                response_alto = sqs.send_message_batch (
                    QueueUrl=alto_queue_url,
                    Entries=messages
                )

                messages = []

        if messages:
            # Send Messages to PDF Queue
            response = sqs.send_message_batch(
                QueueUrl=queue_url,
                Entries=messages
            )
            # Send Messages to ALTO Queue
            response_alto = sqs.send_message_batch (
                QueueUrl=alto_queue_url,
                Entries=messages
            )

        return {
            "statusCode": 200,
            "body": json.dumps({
                "job_id": job_id,
                "prefix": output_prefix,
                "num_issues": total_files
            })
        }
    except Exception as e:
        logger.error("Error occurred: %s", e)