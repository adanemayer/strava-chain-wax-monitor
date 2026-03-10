# strava-chain-wax-monitor
Monitor the chain wax schedule for your bike!

## Infrastructure

Terraform configuration for required AWS resources is available in [`terraform/`](terraform/).
The Terraform module supports an `environment` variable that prefixes all created resource names,
includes a Secrets Manager-backed Strava credential setup for the Lambda runtime,
and packages the script into a local zip before upload.
