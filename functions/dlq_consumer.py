import boto3

dynamodb = boto3.client('dynamodb')
queue_url = os.environ.get('QUEUE_URL')
def lambda_handler(event, context):
    for record in event['Records']:
        message_body = record['body']
        receipt_handle = record['receiptHandle']

        # Assuming the message body contains the job ID
        job_id = message_body

        # Update DynamoDB entry for the job ID
        update_dynamodb_entry(job_id)

        # Delete the message from the DLQ
        delete_message_from_dlq(receipt_handle)

            response = dynamodb.update_item(
        TableName='your-dynamodb-table-name',
        Key={
            'job_id': {'S': job_id}
        },
        UpdateExpression='SET status = :status',
        ExpressionAttributeValues={
            ':status': {'S': 'Failed'}
        }
    )



def update_dynamodb_entry(job_id):
    # Update the DynamoDB table with the necessary changes for the job ID
    response = dynamodb.update_item(
        TableName='your-dynamodb-table-name',
        Key={
            'job_id': {'S': job_id}
        },
        UpdateExpression='SET status = :status',
        ExpressionAttributeValues={
            ':status': {'S': 'Failed'}
        }
    )

    print(f"Updated DynamoDB entry for job ID {job_id}")

def delete_message_from_dlq(receipt_handle):
    # Delete the message from the Dead Letter Queue (DLQ)
    sqs = boto3.client('sqs')
    sqs.delete_message(
        QueueUrl='your-dlq-queue-url',
        ReceiptHandle=receipt_handle
    )

    print("Deleted message from DLQ")
