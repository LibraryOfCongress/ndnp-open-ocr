import os
import boto3
import json
import uuid
from datetime import datetime

def handler(event, context):
    job_id = str(uuid.uuid4())  # Generate a new job id
    bucket_name = os.getenv('INPUT_BUCKET_NAME')
    prefix = event['pathParameters']['prefix']
    if bucket_name is None:
        raise Exception("No S3_BUCKET_NAME environment variable set")

    s3 = boto3.resource('s3')
    sqs = boto3.client('sqs')
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.getenv('TABLE_NAME'))

    print(os.environ)

    queue_url = os.environ.get('QUEUE_URL')

    print(queue_url)
    total_files = 0
    try:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        output_prefix = os.path.join(os.path.dirname(prefix), os.path.basename(prefix) + "-" + timestamp)

        messages = []
        for object_summary in s3.Bucket(bucket_name).objects.filter(Prefix=prefix):
            file_name = object_summary.key

            if file_name.lower().endswith('.tif'):
                message = {
                    'Bucket': bucket_name,
                    'Key': file_name,
                    'OutputPrefix': output_prefix,
                    'InputPrefix': prefix,
                    'JobId': job_id
                }

                messages.append({
                    'Id': str(uuid.uuid4()),
                    'MessageBody': json.dumps(message)
                })

                total_files += 1

            if len(messages) == 10:
                response = sqs.send_message_batch(
                    QueueUrl=queue_url,
                    Entries=messages
                )

                # After sending messages to SQS, store them in DynamoDB
                for msg in messages:
                    table.put_item(
                        Item={
                            'pk': job_id,
                            'sk': msg['Id'],
                            'MessageBody': msg['MessageBody'],
                            'Timestamp': timestamp
                        }
                    )

                messages = []

        if messages:
            response = sqs.send_message_batch(
                QueueUrl=queue_url,
                Entries=messages
            )

            # # After sending messages to SQS, store them in DynamoDB
            # for msg in messages:
            #     table.put_item(
            #         Item={
            #                 'pk': job_id,
            #                 'sk': msg['Id'],
            #                 'MessageBody': msg['MessageBody'],
            #                 'Timestamp': timestamp
            #         }
            #     )

        table.put_item(
            Item={
                'pk': 'JOB',
                'sk': job_id,
                'TotalMessages': total_files,
                'RemainingMessages': total_files,
                'Timestamp': timestamp
            }
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
        print(e)