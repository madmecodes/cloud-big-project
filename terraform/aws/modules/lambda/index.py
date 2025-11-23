import json
import boto3
import os

sns = boto3.client('sns')

def handler(event, context):
    """
    Lambda function for sending notifications
    Triggered by events from Kafka
    """
    try:
        sns_topic_arn = os.environ.get('SNS_TOPIC_ARN')
        
        message = {
            'status': 'success',
            'message': 'Notification sent',
            'event': event
        }
        
        if sns_topic_arn:
            sns.publish(
                TopicArn=sns_topic_arn,
                Message=json.dumps(message),
                Subject='E-commerce Notification'
            )
        
        return {
            'statusCode': 200,
            'body': json.dumps(message)
        }
    except Exception as e:
        print(f'Error: {str(e)}')
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
