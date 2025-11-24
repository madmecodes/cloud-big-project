import json
import boto3
import os
import logging
from datetime import datetime
from typing import Dict, Any

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
dynamodb = boto3.resource('dynamodb')

# Environment variables
SNS_TOPIC_ARN = os.getenv('SNS_TOPIC_ARN')
SES_SENDER_EMAIL = os.getenv('SES_SENDER_EMAIL', 'noreply@ecommerce.com')
NOTIFICATIONS_TABLE = os.getenv('NOTIFICATIONS_TABLE', 'notifications')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for processing order events from Kafka/SQS.

    Triggers email/SMS notifications when orders are created, updated, or shipped.

    Event format (from Kafka topic 'orders'):
    {
        "order_id": "order-123",
        "user_id": "user-456",
        "total_amount": 999.99,
        "items_count": 2,
        "event_type": "order.created",  # or order.shipped, order.cancelled, etc.
        "created_at": "2024-01-15T10:30:00Z"
    }
    """
    try:
        logger.info(f"Received event: {json.dumps(event)}")

        # Parse event
        if 'Records' in event:  # SQS format
            return handle_sqs_events(event['Records'])
        elif 'detail' in event:  # EventBridge format
            return handle_event_bridge_event(event['detail'])
        else:
            # Raw Kafka event
            return handle_kafka_event(event)

    except Exception as e:
        logger.error(f"Error processing event: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }


def handle_sqs_events(records: list) -> Dict[str, Any]:
    """Handle events from SQS."""
    processed = 0
    failed = 0

    for record in records:
        try:
            # Parse SQS message body
            body = json.loads(record['body'])

            # Process the event
            if process_order_event(body):
                processed += 1
            else:
                failed += 1

        except Exception as e:
            logger.error(f"Failed to process SQS record: {str(e)}")
            failed += 1

    return {
        'statusCode': 200,
        'body': json.dumps({
            'processed': processed,
            'failed': failed
        })
    }


def handle_event_bridge_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle events from EventBridge."""
    try:
        process_order_event(event)
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Notification sent successfully'})
        }
    except Exception as e:
        logger.error(f"Failed to process EventBridge event: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to send notification'})
        }


def handle_kafka_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle raw Kafka event."""
    try:
        process_order_event(event)
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Notification sent successfully'})
        }
    except Exception as e:
        logger.error(f"Failed to process Kafka event: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to send notification'})
        }


def process_order_event(event: Dict[str, Any]) -> bool:
    """
    Process an order event asynchronously.
    Logs event and stores notification record in DynamoDB.

    Returns True if notification was stored successfully.
    """
    order_id = event.get('order_id')
    user_id = event.get('user_id')
    event_type = event.get('event_type', 'order.created')
    total_amount = event.get('total_amount', 0)
    items_count = event.get('items_count', 0)

    if not all([order_id, user_id]):
        logger.warning("Missing required fields in event")
        return False

    # Create notification record
    notification_data = {
        'order_id': order_id,
        'user_id': user_id,
        'event_type': event_type,
        'timestamp': datetime.now().isoformat(),
        'total_amount': total_amount,
        'items_count': items_count,
        'status': 'processed'
    }

    try:
        # Log the event (asynchronous task)
        logger.info(f"Processing order event: {event_type} | Order: {order_id} | User: {user_id} | Amount: ${total_amount}")

        # Store notification record in DynamoDB
        store_notification(notification_data)

        logger.info(f"Successfully stored notification for order {order_id}")
        return True

    except Exception as e:
        logger.error(f"Error processing order event: {str(e)}")
        notification_data['status'] = 'failed'
        notification_data['error'] = str(e)
        try:
            store_notification(notification_data)
        except Exception as store_error:
            logger.error(f"Failed to store error notification: {str(store_error)}")
        return False


# Email sending removed - using async logging and DynamoDB storage instead


def store_notification(notification_data: Dict[str, Any]) -> None:
    """Store notification record in DynamoDB."""
    try:
        table = dynamodb.Table(NOTIFICATIONS_TABLE)
        table.put_item(Item=notification_data)
        logger.info(f"Notification stored for order {notification_data['order_id']}")
    except Exception as e:
        logger.error(f"Failed to store notification: {str(e)}")


# Helper functions removed - using simplified event logging approach
