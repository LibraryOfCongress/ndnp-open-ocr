import os
import boto3
import json
import uuid
import logging

logger = logging.getLogger()
# logger.setLevel(logging.DEBUG)

def main():
    sqs = boto3.client("sqs")

    # Sample SQS message
    custom_message = {
        "Bucket": "loc-preservation",
        "InputPrefix": "loc-preservation/lcbp/ndnp/dlc/batch_dlc_kite_ver01",
        "JobId": "12ea3b1c-e299-41e3-b427-c2204391601a",
        "Key": "loc-preservation/lcbp/ndnp/dlc/batch_dlc_kite_ver01/data/sn83030214/00206531290/1877050201/0009.tif",
        "OutputPrefix": "batch_dlc_kite_ver01_____12ea3b1c-e299-41e3-b427-c2204391601a"
    }

    queue_url = "https://sqs.us-east-2.amazonaws.com/342134162356/ndnp-open-ocr-pdf-consumer-sqs-queue"
    alto_queue_url = "https://sqs.us-east-2.amazonaws.com/342134162356/ndnp-open-ocr-alto-consumer-sqs-queue"

    logger.info("Queue URL: %s", queue_url)

    try:
        message_entry = {
            "Id": str(uuid.uuid4()),
            "MessageBody": json.dumps(custom_message)
        }

        # Send Message to PDF Queue
        response = sqs.send_message_batch(QueueUrl=queue_url, Entries=[message_entry])

        # Send Message to ALTO Queue
        response_alto = sqs.send_message_batch(QueueUrl=alto_queue_url, Entries=[message_entry])

        print("Message sent successfully!")
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Custom message sent successfully!"
            })
        }
    except Exception as e:
        logger.error("Error occurred: %s", e)
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e)
            })
        }

# This is just for standalone testing
if __name__ == "__main__":
     main()