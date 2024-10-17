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

def get_gear_stats(gear_id,gear_table,dynamodb_client):
    return

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


def update_gear_stats(gear_id,gear_table,distance,newest_activity_id,dynamodb_client):
    try:
        logging.info(f'Updating stats for {gear_id}')
        gear_update_response = dynamodb_client.update_item(
            TableName = gear_table,
            Key={'gear_id': gear_id},
            AttributeUpdates={
                'distance': distance,
                'newest_activity_id': newest_activity_id
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
        
            # Get activities
            auth_code = "7c93768a1701b42e80b870d944b3c47d4a604e38"
            token="32fac19add3740c79c04fa5c09d1fb138d27a3ad" #< retrieved based>
            headers = {'Authorization': "Bearer {}".format(token)}
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
        distance,last_activity_id = get_gear_stats(gear_id,gear_table,dynamodb_client)
        logging.debug(f"Starting distance: {distance}")
        logging.debug(f"Last acitvity ID: {last_activity_id}")

        # find last upload_id, trim older activities
        new_activities = []
        found_last_activity = False
        for activity in activities_per_gear[gear_id]:
            # Found the previous last upload, new distance is on the next activity
            if activity.upload_id == last_activity_id:
                logging.info("Found the last processed activity.")
                found_last_activity = True
                continue
            # Skip to next activity if we haven't found the previous last activity yet
            if not found_last_activity:
                logging.debug(f"Skipping activitiy ID: {activity.upload_id}")
                continue

            # Assume that all remaining activities are new

            # Reset the distance counter if the activity name includes the configured flag, indicating a freshly waxed chain 
            if wax_reset_flag in activity.name:
                logging.info(f"Found reset flag '{wax_reset_flag}' in '{activity.name}', resetting distance for {gear_id}")
                distance=0

            distance += int(activity.distance)
            newest_activity_id = activity.upload_id
            logging.debug(f"Distance: {distance} - Newest Activity: {newest_activity_id}")

        logging.info(f'Updating stats for {gear_id}')
        gear_update_response = update_gear_stats(gear_id,gear_table,distance,newest_activity_id,dynamodb_client)

        # Convert current distance from meters to miles
        distance_miles = distance * 0.0006213712

        miles_left = wax_wear_default - distance_miles
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
    


