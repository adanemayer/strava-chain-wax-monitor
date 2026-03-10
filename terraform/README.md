# Terraform for strava-chain-wax-monitor

This Terraform config creates the AWS resources required by `script/chain-wax-monitor.py`:

- DynamoDB table for gear stats (`GEAR_TABLE`)
- SNS topic for notifications (`NOTIFY_TOPIC_ARN`)
- SNS email subscription (uses a placeholder email until updated)
- Secrets Manager secret for Strava credentials (`STRAVA_CREDENTIALS`)
- IAM policy for runtime access scoped to the created table/topic
- Lambda function that runs the script on a schedule

## Naming

All resource names are prefixed with `var.environment`.

For example, with `environment = "dev"`:

- DynamoDB table: `dev-strava-gear-stats`
- SNS topic: `dev-chain-wax-monitor-notifications`
- Strava secret: `dev-strava-credentials`
- IAM policy: `dev-chain-wax-monitor-access`
- Lambda function: `dev-chain-wax-monitor`

## Lambda packaging

Terraform builds a zip locally using the checked-in script and uploads it to Lambda.
The runtime code uses only the Python standard library plus `boto3`, so no extra dependency packaging step is required.

- source file: `../script/chain-wax-monitor.py`
- generated archive: `../.lambda/<environment>-chain-wax-monitor.zip`

## State location

Terraform state is configured to use the local backend at:

- `../.tfstate/terraform.tfstate`

This keeps the state file in the repository root under a dedicated dot-directory.

## Usage

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# export AWS_PROFILE=<your-local-profile>
# update environment, subscriber_email, strava_access_token, and optional refresh values
terraform init
terraform plan
terraform apply
```

After apply:

- Lambda uses `GEAR_TABLE` and `NOTIFY_TOPIC_ARN` automatically.
- Lambda reads Strava credentials from Secrets Manager via `STRAVA_CREDENTIALS`.
- If `strava_client_id`, `strava_client_secret`, `strava_refresh_token`, and `strava_token_expires_at` are set, the Lambda refreshes expiring Strava tokens and writes the updated value back to the same secret.
- Attach `execution_policy_arn` only if you run the script outside Lambda.
- Confirm SNS email subscription from your inbox before notifications are delivered.
