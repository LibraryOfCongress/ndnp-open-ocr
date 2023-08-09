import boto3
import logging
import os
import json

dynamodb = boto3.resource("dynamodb")
sqs = boto3.client("sqs")

# DynamoDB table and SQS queue details
table_name = "ndnp-open-ocr-table" #os.environ.get("TABLE_NAME")
queue_url = "https://sqs.us-east-2.amazonaws.com/342134162356/ndnp-open-ocr-queue" #os.environ.get("QUEUE_URL")
alto_queue_url = "https://sqs.us-east-2.amazonaws.com/342134162356/ndnp-open-ocr-alto-consumer-queue"

def resubmit_message_to_sqs(message_body):
    """Resubmit the failed message back to the original SQS queue."""
    sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(message_body)
    )

    sqs.send_message(
        QueueUrl=alto_queue_url,
        MessageBody=json.dumps(message_body)
    )

job_id = "45dd32bf-9b77-41c6-a17d-4333eebe8636" #event.get("job_id")
if not job_id:
    logging.error("job_id not provided in the event.")
    # return {"statusCode": 400, "body": "job_id is required"}

table = dynamodb.Table(table_name)

# Query DynamoDB table for the specific job_id
response = table.query(
    KeyConditionExpression="pk = :pk and sk = :sk",
    ExpressionAttributeValues={
        ":pk": "JOB",
        ":sk": job_id
    }
)

for item in response["Items"]:
    # items = list(set(item.get("failed_messages", [])))
    keys = []
    messages = []
    for failed_message in item.get("failed_messages", []):
        try:
            # Resubmit the failed message to SQS
            print(failed_message)
            if failed_message['Key'] in keys:
                pass
            else:
                keys.append(failed_message['Key'])
                resubmit_message_to_sqs(failed_message)
                messages.append(failed_message)
            print(len(messages))

            # You can additionally delete or mark the message as reprocessed, if desired.

        except Exception as e:
            logging.error(f"Failed to resubmit message {failed_message['MessageId']}: {e}")

# return {"statusCode": 200, "body": "Job restart processing complete"}
