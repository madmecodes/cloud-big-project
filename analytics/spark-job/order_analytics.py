#!/usr/bin/env python3
"""
PySpark Structured Streaming Analytics Job for Real-time Order Analytics

Runs on GCP Dataproc cluster.
Consumes order events from AWS MSK Kafka 'orders' topic.
Performs 1-minute tumbling window aggregations:
- Count of orders per window
- Count of unique users per window (stateful aggregation)
- Total revenue per window

Publishes aggregated results to 'analytics-results' Kafka topic.

Usage:
    spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.3.0 order_analytics.py
"""

import os
import json
from datetime import datetime

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, to_json, struct, window,
    count, sum as spark_sum, approx_count_distinct,
    current_timestamp, lit, expr
)
from pyspark.sql.types import (
    StructType, StructField, StringType, FloatType,
    IntegerType, TimestampType, ArrayType
)


# Configuration from environment variables
KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "pkc-41p56.asia-south1.gcp.confluent.cloud:9092"
)
KAFKA_API_KEY = os.getenv("KAFKA_API_KEY", "I3XN2DJTHYXGK2EN")
KAFKA_API_SECRET = os.getenv("KAFKA_API_SECRET", "")
ORDERS_TOPIC = os.getenv("KAFKA_ORDERS_TOPIC", "orders")
RESULTS_TOPIC = os.getenv("KAFKA_RESULTS_TOPIC", "analytics-results")
CHECKPOINT_LOCATION = os.getenv("CHECKPOINT_LOCATION", "gs://ecommerce-analytics-checkpoints/order-analytics")

# Order event schema
ORDER_SCHEMA = StructType([
    StructField("id", StringType(), True),
    StructField("order_id", StringType(), True),
    StructField("user_id", StringType(), True),
    StructField("total_amount", FloatType(), True),
    StructField("status", StringType(), True),
    StructField("items_count", IntegerType(), True),
    StructField("event_type", StringType(), True),
    StructField("created_at", StringType(), True),
    StructField("items", ArrayType(StructType([
        StructField("product_id", StringType(), True),
        StructField("quantity", IntegerType(), True),
        StructField("price", FloatType(), True)
    ])), True)
])


def create_spark_session():
    """Create and configure Spark session"""
    return SparkSession.builder \
        .appName("E-Commerce Order Analytics") \
        .config("spark.sql.streaming.checkpointLocation", CHECKPOINT_LOCATION) \
        .config("spark.streaming.stopGracefullyOnShutdown", "true") \
        .config("spark.sql.shuffle.partitions", "4") \
        .getOrCreate()


def run_analytics():
    """Main analytics job"""
    print("=" * 60)
    print("E-Commerce Order Analytics - PySpark Structured Streaming")
    print("=" * 60)
    print(f"Kafka Bootstrap Servers: {KAFKA_BOOTSTRAP_SERVERS}")
    print(f"Input Topic: {ORDERS_TOPIC}")
    print(f"Output Topic: {RESULTS_TOPIC}")
    print(f"Window Size: 1 minute (tumbling)")
    print("=" * 60)

    # Create Spark session
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    print("Reading from Kafka topic...")

    # Read from Kafka with SASL/SSL configuration for Confluent Cloud
    kafka_df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("subscribe", ORDERS_TOPIC) \
        .option("startingOffsets", "latest") \
        .option("kafka.security.protocol", "SASL_SSL") \
        .option("kafka.sasl.mechanism", "PLAIN") \
        .option("kafka.sasl.jaas.config", f"org.apache.kafka.common.security.plain.PlainLoginModule required username='{KAFKA_API_KEY}' password='{KAFKA_API_SECRET}';") \
        .load()

    # Parse JSON from Kafka value
    orders_df = kafka_df \
        .selectExpr("CAST(value AS STRING) as json_value", "timestamp as kafka_timestamp") \
        .select(
            from_json(col("json_value"), ORDER_SCHEMA).alias("order"),
            col("kafka_timestamp")
        ) \
        .select(
            col("order.id").alias("order_id"),
            col("order.user_id").alias("user_id"),
            col("order.total_amount").alias("total_amount"),
            col("order.status").alias("status"),
            col("order.event_type").alias("event_type"),
            col("kafka_timestamp").alias("event_time")
        ) \
        .filter(col("order_id").isNotNull())

    print("Setting up 1-minute tumbling window aggregation...")

    # Perform 1-minute tumbling window aggregation
    # Key metric: Approximate count of unique users per window (approx required for streaming)
    windowed_aggregation = orders_df \
        .withWatermark("event_time", "30 seconds") \
        .groupBy(
            window(col("event_time"), "1 minute")  # 1-minute tumbling window
        ) \
        .agg(
            count("*").alias("order_count"),
            approx_count_distinct("user_id").alias("unique_users"),  # Approximate unique user count for streaming
            spark_sum("total_amount").alias("total_revenue")
        ) \
        .select(
            col("window.start").alias("window_start"),
            col("window.end").alias("window_end"),
            col("order_count"),
            col("unique_users"),
            col("total_revenue"),
            (col("total_revenue") / col("order_count")).alias("avg_order_value"),
            current_timestamp().alias("processed_at")
        )

    # Format output as JSON for Kafka
    output_df = windowed_aggregation \
        .select(
            to_json(struct(
                col("window_start").cast("string"),
                col("window_end").cast("string"),
                col("order_count"),
                col("unique_users"),
                col("total_revenue"),
                col("avg_order_value"),
                col("processed_at").cast("string"),
                lit("order_analytics").alias("metric_type"),
                lit("1_minute_window").alias("window_type")
            )).alias("value")
        )

    print("Writing aggregated results to Kafka...")

    # Write to Kafka results topic with SASL/SSL configuration for Confluent Cloud
    kafka_query = output_df.writeStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("kafka.security.protocol", "SASL_SSL") \
        .option("kafka.sasl.mechanism", "PLAIN") \
        .option("kafka.sasl.jaas.config", f"org.apache.kafka.common.security.plain.PlainLoginModule required username='{KAFKA_API_KEY}' password='{KAFKA_API_SECRET}';") \
        .option("topic", RESULTS_TOPIC) \
        .option("checkpointLocation", f"{CHECKPOINT_LOCATION}/kafka") \
        .outputMode("update") \
        .start()

    # Also write to console for debugging
    console_query = windowed_aggregation.writeStream \
        .format("console") \
        .option("truncate", "false") \
        .outputMode("update") \
        .start()

    print("Analytics job started. Processing order events...")
    print("Aggregating: order_count, unique_users, total_revenue per 1-minute window")

    # Wait for termination
    kafka_query.awaitTermination()


if __name__ == "__main__":
    import sys

    # Accept API secret as command-line argument
    if len(sys.argv) > 1:
        globals()['KAFKA_API_SECRET'] = sys.argv[1]

    print("\n" + "=" * 60)
    print("Starting E-Commerce Order Analytics Service")
    print("Platform: GCP Dataproc (PySpark Structured Streaming)")
    print("Source: Confluent Cloud Kafka")
    print("=" * 60 + "\n")

    run_analytics()
