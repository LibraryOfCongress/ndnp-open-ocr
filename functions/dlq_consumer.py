import boto3
import logging
import os
import json
dynamodb = boto3.resource('dynamodb')
queue_url = os.environ.get('QUEUE_URL')

def handle_failed_message(message, table, job_id):
    # Increment the count of failed messages in the job summary
    table.update_item(
        Key={
            'pk': 'JOB',
            'sk': job_id
        },
        UpdateExpression='ADD #FailureCount :inc',
        ExpressionAttributeNames={
            '#FailureCount': 'FailureCount'
        },
        ExpressionAttributeValues={
            ':inc': 1
        }
    )

    table.update_item(
        Key={
            'pk': 'JOB',
            'sk': job_id
        },
        UpdateExpression='SET #failed_messages = list_append(if_not_exists(#failed_messages, :empty_list), :message)',
        ExpressionAttributeNames={
            '#failed_messages': 'failed_messages'
        },
        ExpressionAttributeValues={
            ':message': message,
            ':empty_list': []
        }
    )

def handler(event, context):
    logging.info("Number of failed messages: {}".format(len(event["Records"])))
    for record in event["Records"]:
        message = json.loads(record["body"])
        print(message)
        job_id = message["JobId"]
        table = dynamodb.Table(os.getenv("TABLE_NAME"))
        try:
            # Log the failed message
            # logging.error(f"Processing of message {message['MessageId']} failed.")
            handle_failed_message(message, table, job_id)
        except Exception as e:
            logging.error(f"Failed to update job summary for message {message}: {e}")

    return {"statusCode": 200, "body": "DLQ processing complete"}