import boto3
import os


def handler(event, context):
    job_id = event["pathParameters"]["jobId"]
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(os.getenv("TABLE_NAME"))
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("pk").eq('JOB')
            & boto3.dynamodb.conditions.Key("sk").eq(job_id)
        )
        return response["Items"]
    except Exception as e:
        print("Error fetching items from DynamoDB: %s", e)
        return None
