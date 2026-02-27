import argparse
import boto3
import logging
import os
import requests
import json

logging.basicConfig(
    format="{asctime} - {levelname} - {message}",
    style="{",
    datefmt="%Y-%m-%d %H:%M",
    level=os.environ.get('LOG_LEVEL','INFO')
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

def send_rewax_notice(gear_id,distance_miles,miles_left,sns_client):
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

    # Replace \\" with '
    # Replace \' with space
    for activity in activities_raw:
        logging.info("Parsing '"+activity["name"]+"'")
        if activity["type"] == "VirtualRide":
            logging.debug("Skipping a Virtual Ride")
            continue

        activity_summary = {
            "name": activity["name"],
            "upload_id": activity["upload_id"],
            "distance": activity["distance"]
        }
        if activity["gear_id"] in activities_grouped.keys():
            logging.debug("Appending activity to list for gear ID "+activity["gear_id"])
            activities_grouped[activity["gear_id"]].append(activity_summary)
        else:
            logging.debug("Starting a new list of activities for gear ID "+activity["gear_id"])
            activities_grouped.setdefault(activity["gear_id"],[activity_summary])

    return(activities_grouped)
    # trim to upload_id, gear_id, distance


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




if __name__ == '__main__':
    # Runtime arguments
    parser = argparse.ArgumentParser(description='Check chain waxing schedule')
    parser.add_argument('--activity-file', type=str, required=False, dest='activity_file')
    parser.add_argument('--activity-days', type=int, default=7, required=False, dest='activity_days')
    parser.add_argument('--credentials', type=str, default='strava/credentials', required=False, dest='credentials')
    args = parser.parse_args()

    # Environment variables
    gear_table = os.environ.get('GEAR_TABLE','strava-gear-stats')
    wax_reset_flag = os.environ.get('WAX_RESET','[wax]')
    wax_wear_default = os.environ.get('WAX_WEAR',400)

    # AWS Clients
    dynamodb_client=boto3.client('dynamodb')
    sns_client=boto3.client('sns')

    base_url = "www.strava.com/api/v3"
    headers = None

    # Use supplied activities file
    if args.activity_file:
        logging.info("Using activity file %s", args.activity_file)

        with open(args.activity_file) as f:
            activities_raw = json.load(f)
        
    # Pull new activity summary from Strava
    else:
        logging.info("Retrieving activities from past %s days", args.activity_days)
        # Use credentials from a local file
        if "json" in args.credentials:
            logging.info("Using credentials file %s", args.credentials)
        # Pull credentials from a remote store (AWS)
        else:
            logging.info("Retrieving credentials from Secrets Manager Secret '%s'", args.credentials)

        # TODO: Replace with secret retrieval flow
        token = os.environ.get('STRAVA_TOKEN', "32fac19add3740c79c04fa5c09d1fb138d27a3ad")
        headers = {'Authorization': f"Bearer {token}"}
        response = requests.get(
            f'https://{base_url}/athlete/activities',
            headers=headers
        )

        activities_raw = json.loads(response.content)
    
    
    # inputs: distance threshold, activity lookback
    # dynamodb table: gearid, common name, current distance, last updated

    # split activities per gear id
    logging.info("Splitting activities up by gear_id")
    activities_per_gear = split_activities(activities_raw)
            # drop "type":"VirtualRide" activities and related gearid
            # trim to upload_id, gear_id, distance
    # for each gear_id
    for gear_id in activities_per_gear:
        logging.info("Processing acitvities for gear ID "+gear_id)
        # get existing distance, upload_id from dynamodb
        logging.info("Retrieving last distance and activity_id")
        distance_miles,last_activity_id,reset_gear_miles = get_gear_stats(gear_id,gear_table,dynamodb_client)
        logging.debug(f"Starting distance: {distance_miles}")
        logging.debug(f"Last acitvity ID: {last_activity_id}")

        # find last upload_id, trim older activities
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
                distance_after_reset = sum(a["distance"] for a in new_activities if a["upload_id"] >= activity["upload_id"]) * 0.0006213712
                reset_gear_miles = max(current_gear_miles - distance_after_reset, 0)
                miles_since_reset = distance_after_reset


        distance_miles = miles_since_reset
        logging.info(f'Updating stats for {gear_id}')
        gear_update_response = update_gear_stats(
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
            send_rewax_notice(gear_id,distance_miles,miles_left,sns_client)
        else:
            logging.debug(f"{gear_id} has {miles_left} miles left on current chain wax coat.")


        # add distance from each activity
        # if activity includes flag, start distance count
        # post distance count to dynamodb
        # if distance within 10% of threshold, send SNS message
    

