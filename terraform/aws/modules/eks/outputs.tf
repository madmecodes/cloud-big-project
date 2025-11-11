output "cluster_name" {
  value       = aws_eks_cluster.main.name
  description = "EKS cluster name"
}

output "cluster_endpoint" {
  value       = aws_eks_cluster.main.endpoint
  description = "EKS cluster API endpoint"
}

output "cluster_version" {
  value       = aws_eks_cluster.main.version
  description = "EKS cluster version"
}

output "cluster_ca_certificate" {
  value       = aws_eks_cluster.main.certificate_authority[0].data
  description = "Base64 encoded certificate data required to communicate with the cluster"
  sensitive   = true
}

output "cluster_security_group_id" {
  value       = aws_security_group.cluster.id
  description = "EKS cluster security group ID"
}

output "node_groups" {
  value = {
    for key, ng in aws_eks_node_group.main :
    key => {
      id         = ng.id
      arn        = ng.arn
      asg_name   = ng.resources[0].autoscaling_groups[0].name
    }
  }
  description = "Node groups information"
}

output "oidc_provider_arn" {
  value       = aws_iam_openid_connect_provider.cluster.arn
  description = "ARN of the OIDC Provider for IRSA"
}

output "oidc_provider_url" {
  value       = aws_eks_cluster.main.identity[0].oidc[0].issuer
  description = "URL of the OIDC Provider"
}
