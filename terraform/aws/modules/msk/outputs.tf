output "cluster_arn" {
  value       = aws_msk_cluster.main.arn
  description = "MSK cluster ARN"
}

output "bootstrap_servers" {
  value       = aws_msk_cluster.main.bootstrap_brokers
  description = "MSK bootstrap servers (plaintext)"
}

output "bootstrap_servers_tls" {
  value       = aws_msk_cluster.main.bootstrap_brokers_tls
  description = "MSK bootstrap servers (TLS)"
}

output "zookeeper_connect_string" {
  value       = aws_msk_cluster.main.zookeeper_connect_string
  description = "ZooKeeper connection string"
}
