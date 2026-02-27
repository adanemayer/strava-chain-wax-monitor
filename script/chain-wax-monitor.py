import argparse
import boto3
import logging
import os
import requests
import json
import time

logging.basicConfig(
    format="{asctime} - {levelname} - {message}",
    style="{",
    datefmt="%Y-%m-%d %H:%M",
    level=os.environ.get('LOG_LEVEL', 'INFO')
)


def get_gear_stats(gear_id, gear_table, dynamodb_client):
    try:
        response = dynamodb_client.get_item(
            TableName=gear_table,
            Key={'gear_id': {'S': gear_id}}
        )
    except Exception as e:
        logging.error(e)
        return 0.0, None, 0.0

    item = response.get('Item', {})
    distance_miles = float(item.get('distance_miles', {}).get('N', '0'))
    newest_activity_id = item.get('newest_activity_id', {}).get('N')
    reset_gear_miles = float(item.get('reset_gear_miles', {}).get('N', '0'))
    return distance_miles, newest_activity_id, reset_gear_miles


def get_gear_distance_miles(gear_id, headers, base_url):
    response = requests.get(
        f'https://{base_url}/gear/{gear_id}',
        headers=headers
    )
    response.raise_for_status()
    gear = response.json()
    return float(gear.get('distance', 0)) * 0.0006213712


def send_rewax_notice(gear_id, distance_miles, miles_left, sns_client):
    topic_arn = os.environ.get('NOTIFY_TOPIC_ARN')
    try:
        sns_response = sns_client.publish(
            TopicArn=topic_arn,
            Message=f'Bike {gear_id} > Current miles: {distance_miles} / Miles left: {miles_left}',
            Subject=f'Time to wax {gear_id}',
        )
        logging.debug(sns_response)
    except Exception as e:
        logging.error(e)


def split_activities(activities_raw):
    # drop "type":"VirtualRide" activities and related gearid
    activities_grouped = {}

    for activity in activities_raw:
        logging.info("Parsing '%s'", activity["name"])
        if activity["type"] == "VirtualRide":
            logging.debug("Skipping a Virtual Ride")
            continue

        activity_summary = {
            "name": activity["name"],
            "upload_id": activity["upload_id"],
            "distance": activity["distance"]
        }
        if activity["gear_id"] in activities_grouped.keys():
            logging.debug("Appending activity to list for gear ID %s", activity["gear_id"])
            activities_grouped[activity["gear_id"]].append(activity_summary)
        else:
            logging.debug("Starting a new list of activities for gear ID %s", activity["gear_id"])
            activities_grouped.setdefault(activity["gear_id"], [activity_summary])

    return activities_grouped


def update_gear_stats(gear_id, gear_table, distance_miles, newest_activity_id, reset_gear_miles, dynamodb_client):
    try:
        logging.info(f'Updating stats for {gear_id}')
        gear_update_response = dynamodb_client.put_item(
            TableName=gear_table,
            Item={
                'gear_id': {'S': gear_id},
                'distance_miles': {'N': f'{distance_miles}'},
                'newest_activity_id': {'N': f'{newest_activity_id}'} if newest_activity_id is not None else {'N': '0'},
                'reset_gear_miles': {'N': f'{reset_gear_miles}'}
            }
        )
        logging.debug(gear_update_response)
        return gear_update_response
    except Exception as e:
        logging.error(e)


def load_credentials(credentials_arg, secrets_client):
    if credentials_arg.endswith('.json'):
        logging.info("Using credentials file %s", credentials_arg)
        with open(credentials_arg, 'r', encoding='utf-8') as credentials_file:
            return json.load(credentials_file), None

    logging.info("Retrieving credentials from Secrets Manager Secret '%s'", credentials_arg)
    secret = secrets_client.get_secret_value(SecretId=credentials_arg)
    secret_string = secret.get('SecretString', '{}')
    return json.loads(secret_string), credentials_arg


def refresh_strava_token(credentials):
    response = requests.post(
        'https://www.strava.com/oauth/token',
        data={
            'client_id': credentials['client_id'],
            'client_secret': credentials['client_secret'],
            'grant_type': 'refresh_token',
            'refresh_token': credentials['refresh_token']
        }
    )
    response.raise_for_status()
    token_payload = response.json()
    credentials.update(token_payload)
    return credentials


def get_strava_headers(credentials_arg, secrets_client):
    credentials, secret_id = load_credentials(credentials_arg, secrets_client)

    required_keys = ['access_token']
    for key in required_keys:
        if key not in credentials:
            raise ValueError(f"Missing required credential field '{key}'")

    # If token is close to expiring and refresh metadata is available, refresh.
    expires_at = credentials.get('expires_at')
    can_refresh = all(
        key in credentials
        for key in ['client_id', 'client_secret', 'refresh_token']
    )
    if expires_at and can_refresh and int(expires_at) <= int(time.time()) + 120:
        logging.info('Refreshing expired/expiring Strava access token')
        credentials = refresh_strava_token(credentials)

        if secret_id:
            secrets_client.update_secret(
                SecretId=secret_id,
                SecretString=json.dumps(credentials)
            )

    return {'Authorization': f"Bearer {credentials['access_token']}"}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Check chain waxing schedule')
    parser.add_argument('--activity-file', type=str, required=False, dest='activity_file')
    parser.add_argument('--activity-days', type=int, default=7, required=False, dest='activity_days')
    parser.add_argument('--credentials', type=str, default='strava/credentials', required=False, dest='credentials')
    args = parser.parse_args()

    gear_table = os.environ.get('GEAR_TABLE', 'strava-gear-stats')
    wax_reset_flag = os.environ.get('WAX_RESET', '[wax]')
    wax_wear_default = os.environ.get('WAX_WEAR', 400)

    dynamodb_client = boto3.client('dynamodb')
    sns_client = boto3.client('sns')
    secrets_client = boto3.client('secretsmanager')

    base_url = "www.strava.com/api/v3"
    headers = None

    if args.activity_file:
        logging.info("Using activity file %s", args.activity_file)
        with open(args.activity_file, encoding='utf-8') as f:
            activities_raw = json.load(f)
    else:
        logging.info("Retrieving activities from past %s days", args.activity_days)
        headers = get_strava_headers(args.credentials, secrets_client)

        response = requests.get(
            f'https://{base_url}/athlete/activities',
            headers=headers
        )
        response.raise_for_status()
        activities_raw = json.loads(response.content)

    logging.info("Splitting activities up by gear_id")
    activities_per_gear = split_activities(activities_raw)

    for gear_id in activities_per_gear:
        logging.info("Processing acitvities for gear ID %s", gear_id)
        logging.info("Retrieving last distance and activity_id")
        distance_miles, last_activity_id, reset_gear_miles = get_gear_stats(gear_id, gear_table, dynamodb_client)
        logging.debug(f"Starting distance: {distance_miles}")
        logging.debug(f"Last acitvity ID: {last_activity_id}")

        new_activities = []
        newest_activity_id = int(last_activity_id) if last_activity_id else None
        for idx, activity in enumerate(activities_per_gear[gear_id]):
            if idx == 0:
                newest_activity_id = activity["upload_id"]
            if last_activity_id and str(activity["upload_id"]) == str(last_activity_id):
                logging.info("Found the last processed activity.")
                break
            new_activities.append(activity)

        if headers:
            current_gear_miles = get_gear_distance_miles(gear_id, headers, base_url)
        else:
            added_miles = sum(a["distance"] for a in new_activities) * 0.0006213712
            current_gear_miles = distance_miles + added_miles + reset_gear_miles
        logging.debug(f"Current gear miles for {gear_id}: {current_gear_miles}")

        miles_since_reset = current_gear_miles - reset_gear_miles
        for activity in reversed(new_activities):
            if wax_reset_flag in activity["name"]:
                logging.info(f"Found reset flag '{wax_reset_flag}' in '{activity['name']}', resetting distance for {gear_id}")
                distance_after_reset = sum(
                    a["distance"]
                    for a in new_activities
                    if a["upload_id"] >= activity["upload_id"]
                ) * 0.0006213712
                reset_gear_miles = max(current_gear_miles - distance_after_reset, 0)
                miles_since_reset = distance_after_reset

        distance_miles = miles_since_reset
        update_gear_stats(
            gear_id,
            gear_table,
            distance_miles,
            newest_activity_id,
            reset_gear_miles,
            dynamodb_client
        )

        miles_left = float(wax_wear_default) - distance_miles
        logging.debug(f'Miles left for {gear_id}: {miles_left}')
        if miles_left < 50:
            logging.info(f"{gear_id} has {miles_left} miles left on current chain wax coat.")
            send_rewax_notice(gear_id, distance_miles, miles_left, sns_client)
        else:
            logging.debug(f"{gear_id} has {miles_left} miles left on current chain wax coat.")
