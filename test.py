import boto3
import uuid
import json

"""
To submit test queue message to test Fargate task...
"""

# Initialization
sqs = boto3.client("sqs", region_name="us-east-2")
sqs_queue_url = "https://sqs.us-east-2.amazonaws.com/420280634985/ndnp-open-ocr-consumer-sqs-queue" #os.getenv("SQS_QUEUE_URL")
dynamodb = boto3.resource("dynamodb")
# table = 'ndnp-open-ocr-table' #dynamodb.Table(os.getenv("TABLE_NAME"))

messages = []

# SQS Send Message
bucket_name = "ndnp-open-ocr-output-bucket-test-2"
prefix = "notvalidated_small"
output_prefix = "notvalidated__72a7cebc-18ea-4aee-9120-717601f823fa"
job_id = "TEST"


message = {
    "Bucket": bucket_name,
    "Key": "notvalidated_small/batch_dlc_sampleissue/2010270501/00237285074/0000.tif",
    "OutputPrefix": output_prefix,
    "InputPrefix": prefix,
    "JobId": "TEST"
}

messages.append(
    {"Id": str(uuid.uuid4()), "MessageBody": json.dumps(message)}
)

# Send Messages to PDF Queue
response = sqs.send_message_batch(QueueUrl=sqs_queue_url, Entries=messages)

print(response)