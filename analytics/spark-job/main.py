#!/usr/bin/env python3
"""
Apache Flink Analytics Job for Real-time Order Analytics

Consumes order events from Kafka 'orders' topic
Performs 1-minute tumbling window aggregations:
- Count of orders per window
- Total revenue per window
- Unique user count per window

Publishes aggregated results to 'analytics-results' Kafka topic
"""

import json
import logging
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple

from pyflink.datastream import StreamExecutionEnvironment, KeyedStream
from pyflink.datastream.functions import MapFunction, ReduceFunction, WindowFunction
from pyflink.datastream.windowed_stream import WindowedStream
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.typeinfo import Types
from pyflink.datastream.connectors.kafka import KafkaSource, KafkaProducer
from pyflink.datastream.windowing.time_window import TimeWindow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OrderEvent:
    """Represents an order event"""

    def __init__(self, order_id: str, user_id: str, amount: float,
                 items_count: int, timestamp: datetime):
        self.order_id = order_id
        self.user_id = user_id
        self.amount = amount
        self.items_count = items_count
        self.timestamp = timestamp

    @staticmethod
    def from_json(json_str: str) -> 'OrderEvent':
        """Parse OrderEvent from JSON"""
        try:
            data = json.loads(json_str)
            return OrderEvent(
                order_id=data.get('order_id'),
                user_id=data.get('user_id'),
                amount=float(data.get('total_amount', 0)),
                items_count=int(data.get('items_count', 0)),
                timestamp=datetime.fromisoformat(data.get('created_at'))
            )
        except Exception as e:
            logger.error(f"Failed to parse order event: {e}")
            raise

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'order_id': self.order_id,
            'user_id': self.user_id,
            'amount': self.amount,
            'items_count': self.items_count,
            'timestamp': self.timestamp.isoformat()
        }


class AggregationState:
    """Accumulates aggregation state during window"""

    def __init__(self):
        self.order_count = 0
        self.total_revenue = 0.0
        self.total_items = 0
        self.unique_users = set()
        self.window_start = None
        self.window_end = None

    def add_order(self, event: OrderEvent):
        """Add an order to the aggregation"""
        self.order_count += 1
        self.total_revenue += event.amount
        self.total_items += event.items_count
        self.unique_users.add(event.user_id)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'order_count': self.order_count,
            'total_revenue': round(self.total_revenue, 2),
            'total_items': self.total_items,
            'unique_users': len(self.unique_users),
            'average_order_value': round(
                self.total_revenue / self.order_count, 2
            ) if self.order_count > 0 else 0,
            'window_start': self.window_start.isoformat() if self.window_start else None,
            'window_end': self.window_end.isoformat() if self.window_end else None,
            'timestamp': datetime.now().isoformat()
        }


class OrderEventParser(MapFunction):
    """Parse JSON strings into OrderEvent objects"""

    def map(self, value: str) -> OrderEvent:
        try:
            return OrderEvent.from_json(value)
        except Exception as e:
            logger.error(f"Failed to parse order event: {e}")
            # Return None for invalid events (will be filtered out)
            return None


class OrderAggregator(ReduceFunction):
    """Aggregate order events"""

    def reduce(self, event1: OrderEvent, event2: OrderEvent) -> OrderEvent:
        """Combine two order events"""
        # Return the later event (maintains latest state)
        if event1.timestamp >= event2.timestamp:
            return event1
        else:
            return event2


class WindowAggregator(WindowFunction):
    """Aggregate orders within a time window"""

    def apply(self, window: TimeWindow, elements: Iterable, out) -> None:
        """Apply window aggregation"""
        try:
            state = AggregationState()
            state.window_start = datetime.fromtimestamp(window.start / 1000)
            state.window_end = datetime.fromtimestamp(window.end / 1000)

            # Collect all orders in the window
            for element in elements:
                if element is not None:
                    state.add_order(element)

            # Only emit if there are orders in the window
            if state.order_count > 0:
                result = {
                    'metric_name': 'order_aggregation',
                    'data': state.to_dict(),
                    'window_duration_minutes': 1
                }
                out.collect(json.dumps(result))
                logger.info(f"Window aggregation: {state.order_count} orders, "
                           f"${state.total_revenue:.2f} revenue, "
                           f"{len(state.unique_users)} unique users")

        except Exception as e:
            logger.error(f"Error in window aggregation: {e}", exc_info=True)


class AnalyticsResult:
    """Represents analytics results"""

    def __init__(self, window_start: datetime, window_end: datetime,
                 order_count: int, total_revenue: float, unique_users: int):
        self.window_start = window_start
        self.window_end = window_end
        self.order_count = order_count
        self.total_revenue = total_revenue
        self.unique_users = unique_users
        self.processed_at = datetime.now()

    def to_json(self) -> str:
        """Convert to JSON"""
        return json.dumps({
            'window_start': self.window_start.isoformat(),
            'window_end': self.window_end.isoformat(),
            'order_count': self.order_count,
            'total_revenue': round(self.total_revenue, 2),
            'unique_users': self.unique_users,
            'average_order_value': round(
                self.total_revenue / self.order_count, 2
            ) if self.order_count > 0 else 0,
            'processed_at': self.processed_at.isoformat()
        })


def get_kafka_source(bootstrap_servers: str, topic: str) -> KafkaSource:
    """Create Kafka source"""
    return KafkaSource.builder() \
        .set_bootstrap_servers(bootstrap_servers) \
        .set_topics(topic) \
        .set_group_id('flink-analytics') \
        .set_starting_offsets('latest') \
        .set_value_only_deserializer(SimpleStringSchema()) \
        .set_property('security.protocol', 'PLAINTEXT') \
        .build()


def get_kafka_sink(bootstrap_servers: str, topic: str) -> KafkaProducer:
    """Create Kafka sink"""
    return KafkaProducer.builder() \
        .set_bootstrap_servers(bootstrap_servers) \
        .set_value_serializer(SimpleStringSchema()) \
        .set_topic(topic) \
        .set_property('acks', 'all') \
        .set_property('retries', '3') \
        .build()


def run_analytics_job():
    """Run the Flink analytics job"""
    try:
        # Get Kafka configuration
        bootstrap_servers = 'msk-kafka-cluster:9092'  # Will be overridden by env var
        orders_topic = 'orders'
        results_topic = 'analytics-results'

        # Create execution environment
        env = StreamExecutionEnvironment.get_execution_environment()

        # Set parallelism
        env.set_parallelism(4)

        # Enable checkpointing for fault tolerance
        env.enable_changelog_timestamp_watermarking()
        env.set_state_backend('rocksdb')

        logger.info("Creating Kafka source...")

        # Create source
        kafka_source = get_kafka_source(bootstrap_servers, orders_topic)

        # Add source to environment
        order_stream = env.add_source(kafka_source)

        # Parse events
        parsed_stream = order_stream \
            .map(OrderEventParser(), output_type=Types.POJO(OrderEvent)) \
            .filter(lambda event: event is not None)  # Filter out invalid events

        # Extract event time and add watermark
        parsed_stream = parsed_stream \
            .assign_timestamps_and_watermarks(
                SimpleTimestampAssigner()
            )

        logger.info("Setting up 1-minute tumbling window...")

        # Create 1-minute tumbling windows
        # Each window is 60 seconds
        windowed_stream = parsed_stream \
            .key_by(lambda event: 'all_orders') \
            .window(TumblingEventTimeWindow.of(TimeUnit.SECONDS, 60)) \
            .reduce(
                OrderAggregator(),
                WindowAggregator()
            )

        logger.info("Creating Kafka sink...")

        # Create sink
        kafka_sink = get_kafka_sink(bootstrap_servers, results_topic)

        # Add sink
        windowed_stream \
            .sink_to(kafka_sink) \
            .name('Analytics Results to Kafka')

        # Add console sink for debugging
        windowed_stream \
            .print() \
            .set_parallelism(1)

        logger.info("Starting Flink job: ecommerce-analytics")

        # Execute
        env.execute("E-Commerce Order Analytics")

    except Exception as e:
        logger.error(f"Error running analytics job: {e}", exc_info=True)
        sys.exit(1)


class SimpleTimestampAssigner:
    """Simple timestamp assigner for testing"""

    def extract_timestamp(self, element: OrderEvent) -> int:
        """Extract timestamp in milliseconds"""
        return int(element.timestamp.timestamp() * 1000)

    def current_watermark(self) -> int:
        """Return current watermark"""
        return int((datetime.now().timestamp() - 10) * 1000)  # 10 sec lag


if __name__ == '__main__':
    logger.info("E-Commerce Analytics Service starting")
    logger.info("Job: Real-time order aggregation with 1-minute tumbling windows")
    logger.info("Input: Kafka topic 'orders'")
    logger.info("Output: Kafka topic 'analytics-results'")

    run_analytics_job()
