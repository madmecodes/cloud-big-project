# GCP Dataproc to AWS MSK Kafka Integration Guide

## Problem
Connecting GCP Dataproc (PySpark) to AWS MSK (Managed Streaming for Kafka) with SSL/TLS encryption across cloud boundaries.

## Solution Architecture

### 1. MSK Configuration (AWS Side)
- **Public Access**: Enabled with `SERVICE_PROVIDED_EIPS`
- **Encryption**: TLS enabled (port 9094)
- **Certificates**: AWS Certificate Manager (ACM) - automatically handled by MSK
- **Bootstrap Servers** (TLS):
  ```
  b-1.ecommercekafka.13b4qv.c2.kafka.ap-south-1.amazonaws.com:9094
  b-2.ecommercekafka.13b4qv.c2.kafka.ap-south-1.amazonaws.com:9094
  b-3.ecommercekafka.13b4qv.c2.kafka.ap-south-1.amazonaws.com:9094
  ```

### 2. Dataproc Configuration (GCP Side)
- **Java Version**: OpenJDK 11 (default in Dataproc)
- **Truststore**: System default Java CA certificates (`/usr/lib/jvm/java-11-openjdk-amd64/lib/security/cacerts`)
- **SSL Protocol**: TLS with endpoint verification enabled

## Correct Spark-Kafka SSL Configuration

### Recommended Configuration (Simple & Reliable)
```python
# Read from Kafka - Let JVM automatically find default truststore
kafka_df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
    .option("subscribe", ORDERS_TOPIC) \
    .option("startingOffsets", "latest") \
    .option("kafka.security.protocol", "SSL") \
    .option("kafka.ssl.endpoint.identification.algorithm", "HTTPS") \
    .load()

# Write to Kafka
kafka_query = output_df.writeStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
    .option("kafka.security.protocol", "SSL") \
    .option("kafka.ssl.endpoint.identification.algorithm", "HTTPS") \
    .option("topic", RESULTS_TOPIC) \
    .option("checkpointLocation", CHECKPOINT_LOCATION) \
    .outputMode("update") \
    .start()
```

### Alternative Configuration (Explicit Truststore)
If the simple config doesn't work, explicitly specify the system truststore:
```python
# Add these options if default truststore discovery fails
.option("kafka.ssl.truststore.location", "/usr/lib/jvm/java-11-openjdk-amd64/lib/security/cacerts") \
.option("kafka.ssl.truststore.password", "changeit") \
```

### Parameter Explanation

| Parameter | Value | Reason |
|-----------|-------|--------|
| `kafka.security.protocol` | `SSL` | Enables TLS encryption for Kafka communication |
| `kafka.ssl.truststore.location` | `/usr/lib/jvm/java-11-openjdk-amd64/lib/security/cacerts` | Points to system Java truststore that includes AWS CA certificates |
| `kafka.ssl.truststore.password` | `changeit` | Default password for Java cacerts (DO NOT use in production) |
| `kafka.ssl.endpoint.identification.algorithm` | `HTTPS` | Enables hostname verification - validates MSK broker certificates |

## Important Notes

### Why This Works
- **AWS MSK uses public certificates** from AWS Certificate Manager
- These certificates are signed by AWS Certificate Authority
- The default Java truststore (`cacerts`) includes AWS CA root certificates
- Therefore, no custom certificate creation or upload is needed

### What NOT to Do
- ❌ Don't omit `kafka.ssl.endpoint.identification.algorithm` or set it to empty string
- ❌ Don't try to create custom keystores/truststores for server validation (not needed)
- ❌ Don't use `kafka.ssl.truststore.type=JKS` without providing actual truststore location
- ❌ Don't use PLAINTEXT protocol (port 9092) for production - always use TLS

### Troubleshooting

**Error: "Failed to load SSL keystore"**
- Ensure truststore path is correct for your Java version
- Default locations:
  - Java 11: `/usr/lib/jvm/java-11-openjdk-amd64/lib/security/cacerts`
  - Java 8: `/usr/lib/jvm/java-8-openjdk-amd64/lib/security/cacerts`

**Error: "hostname verification failed"**
- Make sure `endpoint.identification.algorithm` is set to `HTTPS`
- Verify bootstrap servers use correct domain names (not IP addresses)

**Error: "Connection refused"**
- Check network connectivity: GCP Dataproc → AWS MSK brokers
- Verify MSK security groups allow traffic from Dataproc VPC/IPs
- Ensure MSK cluster is in ACTIVE state

## Testing the Connection

### Manual Test with Kafka Tools
```bash
# From Dataproc cluster
gcloud compute ssh <dataproc-instance> --zone=asia-south1-b

# Inside the instance, test connectivity
kafka-console-producer --broker-list <MSK_TLS_BOOTSTRAP_SERVERS> \
  --topic orders \
  --security-protocol SSL \
  --producer-property ssl.truststore.location=/usr/lib/jvm/java-11-openjdk-amd64/lib/security/cacerts \
  --producer-property ssl.truststore.password=changeit
```

## References
- AWS MSK Documentation: https://docs.aws.amazon.com/msk/
- GCP Dataproc Documentation: https://cloud.google.com/dataproc/docs
- Apache Spark Kafka Integration: https://spark.apache.org/docs/latest/structured-streaming-kafka-integration.html
