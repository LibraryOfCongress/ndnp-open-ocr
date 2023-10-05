import os
import boto3
import json
import uuid
from datetime import datetime
import logging
import os
import boto3


def handler(event, context):
    dynamodb = boto3.resource("dynamodb")

    table_name = os.getenv("TABLE_NAME")

    table = dynamodb.Table(table_name)
    response = table.get_item(Key={"pk": "JOB", "sk": event["pathParameters"]["JobId"]})

    # Fetch item from the response
    item = response.get("Item", {})

    # Print the item
    print(item)
    return item
