output "gear_table_name" {
  description = "Set this as GEAR_TABLE when running the script."
  value       = aws_dynamodb_table.gear_stats.name
}

output "notify_topic_arn" {
  description = "Set this as NOTIFY_TOPIC_ARN when running the script."
  value       = aws_sns_topic.rewax_notifications.arn
}

output "execution_policy_arn" {
  description = "IAM policy ARN with least-privilege access to this stack's table and topic."
  value       = aws_iam_policy.chain_wax_monitor.arn
}

output "lambda_function_name" {
  description = "Name of the deployed chain-wax monitor Lambda function."
  value       = aws_lambda_function.chain_wax_monitor.function_name
}

output "lambda_role_arn" {
  description = "IAM role ARN assumed by the Lambda function."
  value       = aws_iam_role.chain_wax_monitor_lambda.arn
}
