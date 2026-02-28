terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }

  backend "local" {
    path = "../.tfstate/terraform.tfstate"
  }
}

provider "aws" {
  region = var.aws_region
}

locals {
  name_prefix      = "${var.environment}-"
  gear_table       = "${local.name_prefix}${var.gear_table_name}"
  notify_topic     = "${local.name_prefix}${var.sns_topic_name}"
  monitor_policy   = "${local.name_prefix}chain-wax-monitor-access"
  lambda_role_name = "${local.name_prefix}chain-wax-monitor-lambda-role"
  lambda_name      = "${local.name_prefix}chain-wax-monitor"
  lambda_rule_name = "${local.name_prefix}chain-wax-monitor-schedule"

  default_tags = {
    Environment = var.environment
  }

  merged_tags = merge(local.default_tags, var.tags)
}

resource "aws_dynamodb_table" "gear_stats" {
  name         = local.gear_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "gear_id"

  attribute {
    name = "gear_id"
    type = "S"
  }

  tags = local.merged_tags
}

resource "aws_sns_topic" "rewax_notifications" {
  name = local.notify_topic
  tags = local.merged_tags
}

resource "aws_sns_topic_subscription" "rewax_email" {
  topic_arn = aws_sns_topic.rewax_notifications.arn
  protocol  = "email"
  endpoint  = var.subscriber_email
}

data "archive_file" "lambda_zip" {
  type        = "zip"
  output_path = "../.lambda/${local.lambda_name}.zip"

  source {
    content  = file("../script/chain-wax-monitor.py")
    filename = "chain_wax_monitor_impl.py"
  }

  source {
    filename = "lambda_function.py"
    content  = <<-PY
import runpy


def lambda_handler(event, context):
    runpy.run_module("chain_wax_monitor_impl", run_name="__main__")
    return {"statusCode": 200, "body": "chain-wax monitor executed"}
PY
  }
}

data "aws_iam_policy_document" "assume_lambda" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "chain_wax_monitor_lambda" {
  name               = local.lambda_role_name
  assume_role_policy = data.aws_iam_policy_document.assume_lambda.json
  tags               = local.merged_tags
}

data "aws_iam_policy_document" "chain_wax_monitor" {
  statement {
    sid    = "GearStatsTableAccess"
    effect = "Allow"

    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem"
    ]

    resources = [aws_dynamodb_table.gear_stats.arn]
  }

  statement {
    sid    = "RewaxTopicPublish"
    effect = "Allow"

    actions = [
      "sns:Publish"
    ]

    resources = [aws_sns_topic.rewax_notifications.arn]
  }
}

resource "aws_iam_policy" "chain_wax_monitor" {
  name   = local.monitor_policy
  policy = data.aws_iam_policy_document.chain_wax_monitor.json
  tags   = local.merged_tags
}

resource "aws_iam_role_policy_attachment" "chain_wax_monitor_custom" {
  role       = aws_iam_role.chain_wax_monitor_lambda.name
  policy_arn = aws_iam_policy.chain_wax_monitor.arn
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.chain_wax_monitor_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "chain_wax_monitor" {
  function_name    = local.lambda_name
  role             = aws_iam_role.chain_wax_monitor_lambda.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = var.lambda_runtime
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  timeout          = var.lambda_timeout_seconds
  memory_size      = var.lambda_memory_mb

  environment {
    variables = {
      GEAR_TABLE       = aws_dynamodb_table.gear_stats.name
      NOTIFY_TOPIC_ARN = aws_sns_topic.rewax_notifications.arn
      WAX_WEAR         = tostring(var.wax_wear)
      WAX_RESET        = var.wax_reset_flag
      LOG_LEVEL        = var.log_level
      STRAVA_TOKEN     = var.strava_token
    }
  }

  tags = local.merged_tags
}

resource "aws_cloudwatch_event_rule" "chain_wax_monitor" {
  name                = local.lambda_rule_name
  description         = "Schedule for the chain wax monitor lambda"
  schedule_expression = var.lambda_schedule_expression
  is_enabled          = var.lambda_schedule_enabled

  tags = local.merged_tags
}

resource "aws_cloudwatch_event_target" "chain_wax_monitor" {
  rule      = aws_cloudwatch_event_rule.chain_wax_monitor.name
  target_id = "chain-wax-monitor-lambda"
  arn       = aws_lambda_function.chain_wax_monitor.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.chain_wax_monitor.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.chain_wax_monitor.arn
}
