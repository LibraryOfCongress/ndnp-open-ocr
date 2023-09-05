import boto3
import logging
import os
import json

dynamodb = boto3.resource("dynamodb")
sqs = boto3.client("sqs")

# DynamoDB table and SQS queue details
table_name = "ndnp-open-ocr-table"  # os.environ.get("TABLE_NAME")
queue_url = "https://sqs.us-east-2.amazonaws.com/342134162356/ndnp-open-ocr-pdf-consumer-sqs-queue"  # os.environ.get("QUEUE_URL")
alto_queue_url = (
    "https://sqs.us-east-2.amazonaws.com/342134162356/ndnp-open-ocr-alto-consumer-sqs-queue"
)


def resubmit_message_to_sqs(message_body):
    """Resubmit the failed message back to the original SQS queue."""
    sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(message_body))

    sqs.send_message(
        QueueUrl=alto_queue_url,
        MessageBody=json.dumps(message_body)
    )


job_id = "354ad159-b8ba-47ba-a7a5-1de3f28b41c2"  # event.get("job_id")
if not job_id:
    logging.error("job_id not provided in the event.")
    # return {"statusCode": 400, "body": "job_id is required"}

table = dynamodb.Table(table_name)

# Query DynamoDB table for the specific job_id
response = table.query(
    KeyConditionExpression="pk = :pk and sk = :sk",
    ExpressionAttributeValues={":pk": "JOB", ":sk": job_id},
)

for item in response["Items"]:
    # items = list(set(item.get("failed_messages", [])))
    keys = []
    messages = []
    for failed_message in item.get("pdf_failed_messages", []):
        try:
            # Resubmit the failed message to SQS
            if (
                failed_message["Key"] in keys
                or "0001.tif" in failed_message["Key"]
                or "0002.tif" in failed_message["Key"]
                or "0003.tif" in failed_message["Key"]
                or "0004.tif" in failed_message["Key"]
                or "0005.tif" in failed_message["Key"]
                or "0006.tif" in failed_message["Key"]
            ):
                pass
            else:
                keys.append(failed_message["Key"])
                sqs.send_message(
                    QueueUrl=queue_url,
                    MessageBody=json.dumps(failed_message)
                    )
                messages.append(failed_message)
                print(failed_message)
            print(len(messages))

            # You can additionally delete or mark the message as reprocessed, if desired.
        except Exception as e:
            logging.error(
                f"Failed to resubmit message {failed_message['MessageId']}: {e}"
            )
    print("Retrying {} files".format(len(keys)))
    print(keys)

# return {"statusCode": 200, "body": "Job restart processing complete"}
