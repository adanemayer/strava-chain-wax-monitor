variable "environment" {
  description = "Environment prefix prepended to all created AWS resource names (for example: dev, staging, prod)."
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region where resources will be created."
  type        = string
  default     = "us-east-1"
}

variable "gear_table_name" {
  description = "Base DynamoDB table name used by the monitoring script (GEAR_TABLE env var)."
  type        = string
  default     = "strava-gear-stats"
}

variable "sns_topic_name" {
  description = "Base SNS topic name used by the monitoring script (NOTIFY_TOPIC_ARN env var)."
  type        = string
  default     = "chain-wax-monitor-notifications"
}

variable "subscriber_email" {
  description = "Placeholder email address to subscribe to SNS notifications."
  type        = string
  default     = "you@example.com"
}

variable "strava_token" {
  description = "Strava API token used by the monitor script."
  type        = string
  default     = ""
  sensitive   = true
}

variable "wax_wear" {
  description = "Mileage threshold before rewax notification."
  type        = number
  default     = 400
}

variable "wax_reset_flag" {
  description = "Activity name flag that resets chain wax distance tracking."
  type        = string
  default     = "[wax]"
}

variable "log_level" {
  description = "Log level for lambda execution."
  type        = string
  default     = "INFO"
}

variable "lambda_runtime" {
  description = "Lambda runtime for the monitor function."
  type        = string
  default     = "python3.12"
}

variable "lambda_memory_mb" {
  description = "Memory size for the monitor lambda."
  type        = number
  default     = 256
}

variable "lambda_timeout_seconds" {
  description = "Timeout in seconds for the monitor lambda."
  type        = number
  default     = 60
}

variable "lambda_schedule_expression" {
  description = "EventBridge schedule expression used to invoke lambda."
  type        = string
  default     = "rate(1 day)"
}

variable "lambda_schedule_enabled" {
  description = "Whether the EventBridge schedule is enabled."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Optional tags applied to created resources."
  type        = map(string)
  default = {
    Application = "strava-chain-wax-monitor"
    ManagedBy   = "terraform"
  }
}
