import argparse
import logging
import requests
import json

def split_activities(activities_raw):
    # drop "type":"VirtualRide" activities and related gearid
    activities_grouped = {}

    # Replace \\" with '
    # Replace \' with space
    for activity in activities_raw:
        print(activity["name"])
        if activity["type"] == "VirtualRide":
            continue
        if activity["gear_id"] in activities_grouped.keys():
            activities_grouped[activity["gear_id"]].append(activity)
        else:
            activities_grouped.setdefault(activity["gear_id"],[activity])

    print(activities_grouped)
    # trim to upload_id, gear_id, distance


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Check chain waxing schedule')
    parser.add_argument('--activity-file', type=str, required=False, dest='activity_file')
    parser.add_argument('--activity-days', type=int, default=7, required=False, dest='activity_days')
    parser.add_argument('--log-level', type=str, default='INFO', required=False, dest='log_level')
    parser.add_argument('--credentials', type=str, default='strava/credentials', required=False, dest='credentials')
    args = parser.parse_args()

    base_url = "www.strava.com/api/v3"

    numeric_level = getattr(logging, (args.log_level).upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % args.log_level)
    logging.basicConfig(level=numeric_level)

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
    
    
    # inputs: mileage threshold, activity lookback
    # dynamodb table: gearid, common name, current mileage, last updated

    # split activities per gear id
    split_activities(activities_raw)
            # drop "type":"VirtualRide" activities and related gearid
            # trim to upload_id, gear_id, distance
    # for each gear_id
        # get existing mileage, upload_id from dynamodb
        # find last upload_id, trim older activities
        # add mileage from each activity
        # if activity includes flag, start mileage count
        # post mileage count to dynamodb
        # if mileage within 10% of threshold, send SNS message
    


