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
sns_client = boto3.client('sns')
ses_client = boto3.client('ses')
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
    Process an order event and send appropriate notifications.

    Returns True if notification was sent successfully.
    """
    order_id = event.get('order_id')
    user_id = event.get('user_id')
    event_type = event.get('event_type', 'order.created')
    total_amount = event.get('total_amount', 0)
    items_count = event.get('items_count', 0)

    if not all([order_id, user_id]):
        logger.warning("Missing required fields in event")
        return False

    # Determine notification type based on event
    notification_data = {
        'order_id': order_id,
        'user_id': user_id,
        'event_type': event_type,
        'timestamp': datetime.now().isoformat(),
        'sent': False
    }

    try:
        # Get user details (in real scenario, call user service)
        user_email = get_user_email(user_id)
        user_phone = get_user_phone(user_id)

        # Send notifications based on event type
        if event_type == 'order.created':
            send_order_confirmation(user_email, order_id, total_amount, items_count)
            notification_data['notification_type'] = 'order_confirmation'

        elif event_type == 'order.shipped':
            send_shipment_notification(user_email, order_id)
            notification_data['notification_type'] = 'shipment_notification'

        elif event_type == 'order.delivered':
            send_delivery_notification(user_email, order_id)
            notification_data['notification_type'] = 'delivery_notification'

        elif event_type == 'order.cancelled':
            send_cancellation_notification(user_email, order_id)
            notification_data['notification_type'] = 'cancellation_notification'

        elif event_type == 'payment.failed':
            send_payment_failure_notification(user_email, order_id)
            notification_data['notification_type'] = 'payment_failure'

        notification_data['sent'] = True

        # Store notification record
        store_notification(notification_data)

        # Publish to SNS for additional processing
        publish_to_sns(notification_data)

        logger.info(f"Successfully processed event: {event_type} for order {order_id}")
        return True

    except Exception as e:
        logger.error(f"Error processing order event: {str(e)}")
        notification_data['error'] = str(e)
        store_notification(notification_data)
        return False


def send_order_confirmation(email: str, order_id: str, total_amount: float, items_count: int) -> None:
    """Send order confirmation email."""
    subject = f"Order Confirmation - {order_id}"
    body = f"""
    Dear Customer,

    Thank you for your order!

    Order ID: {order_id}
    Total Amount: ${total_amount:.2f}
    Items: {items_count}

    Your order will be shipped soon.

    Best regards,
    E-Commerce Team
    """

    send_email(email, subject, body)
    logger.info(f"Order confirmation sent to {email} for order {order_id}")


def send_shipment_notification(email: str, order_id: str) -> None:
    """Send shipment notification."""
    subject = f"Your Order {order_id} Has Been Shipped!"
    body = f"""
    Dear Customer,

    Your order {order_id} has been shipped!

    You can track your shipment using the link below:
    [Tracking Link]

    Best regards,
    E-Commerce Team
    """

    send_email(email, subject, body)
    logger.info(f"Shipment notification sent to {email} for order {order_id}")


def send_delivery_notification(email: str, order_id: str) -> None:
    """Send delivery notification."""
    subject = f"Your Order {order_id} Has Been Delivered!"
    body = f"""
    Dear Customer,

    Your order {order_id} has been delivered!

    We hope you are satisfied with your purchase.
    Please rate your experience: [Rating Link]

    Best regards,
    E-Commerce Team
    """

    send_email(email, subject, body)
    logger.info(f"Delivery notification sent to {email} for order {order_id}")


def send_cancellation_notification(email: str, order_id: str) -> None:
    """Send order cancellation notification."""
    subject = f"Order {order_id} Cancelled"
    body = f"""
    Dear Customer,

    Your order {order_id} has been cancelled as requested.

    If you have any questions, please contact our support team.

    Best regards,
    E-Commerce Team
    """

    send_email(email, subject, body)
    logger.info(f"Cancellation notification sent to {email} for order {order_id}")


def send_payment_failure_notification(email: str, order_id: str) -> None:
    """Send payment failure notification."""
    subject = f"Payment Failed for Order {order_id}"
    body = f"""
    Dear Customer,

    We were unable to process the payment for your order {order_id}.

    Please try again: [Retry Payment Link]

    Best regards,
    E-Commerce Team
    """

    send_email(email, subject, body)
    logger.info(f"Payment failure notification sent to {email} for order {order_id}")


def send_email(to_email: str, subject: str, body: str) -> None:
    """Send email using SES."""
    try:
        response = ses_client.send_email(
            Source=SES_SENDER_EMAIL,
            Destination={
                'ToAddresses': [to_email]
            },
            Message={
                'Subject': {
                    'Data': subject,
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Text': {
                        'Data': body,
                        'Charset': 'UTF-8'
                    }
                }
            }
        )
        logger.info(f"Email sent successfully to {to_email}. MessageId: {response['MessageId']}")

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        raise


def publish_to_sns(notification_data: Dict[str, Any]) -> None:
    """Publish notification to SNS topic."""
    try:
        if SNS_TOPIC_ARN:
            sns_client.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=f"Notification: {notification_data.get('notification_type', 'Unknown')}",
                Message=json.dumps(notification_data)
            )
            logger.info(f"Published to SNS: {notification_data['order_id']}")
    except Exception as e:
        logger.error(f"Failed to publish to SNS: {str(e)}")


def store_notification(notification_data: Dict[str, Any]) -> None:
    """Store notification record in DynamoDB."""
    try:
        table = dynamodb.Table(NOTIFICATIONS_TABLE)
        table.put_item(Item=notification_data)
        logger.info(f"Notification stored for order {notification_data['order_id']}")
    except Exception as e:
        logger.error(f"Failed to store notification: {str(e)}")


def get_user_email(user_id: str) -> str:
    """Get user email address. In production, call user service."""
    # TODO: Call User Service gRPC to get user details
    # For now, return mock email
    return f"user_{user_id}@example.com"


def get_user_phone(user_id: str) -> str:
    """Get user phone number. In production, call user service."""
    # TODO: Call User Service gRPC to get user details
    # For now, return empty string
    return ""
