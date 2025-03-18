import commands.status as StatusFunctions
import services.slack as slack_service

from loguru import logger
import requests


VALID_ARGUMENT_COUNT = 3


def get_clover_ping_sensors(site_id: str) -> list[StatusFunctions.PRTGSensor]:
    """
    Gets the status of all the Clover ping sensors at a site from PRTG and
    returns the information as a list of PRTG sensor objects.

    Args:
        site_id (str): The site ID that the Clover's ping sensors are
            associated with.

    Raises:
        ValueError: The site ID was not found in PRTG or there are no ping 
            sensors at the site.

    Returns:
        list[PRTGSensor]: All Clover ping sensors at the site.
    """
    
    # Get all the Clover's statuses via their ping sensor's status at this site.
    clover_ping_sensors_response = requests.get(
        url=StatusFunctions.PRTG_TABLE_URL,
        params={
            'content': 'sensors',
            'columns': 'name,device,group,probe,status,parentid',
            'filter_probe': f'@sub({site_id})',
            'filter_group': f'@sub({StatusFunctions.GroupType.CLOVER_DEVICES.value})',
            'filter_name': StatusFunctions.PRTG_PING_NAME,
            'sortby': 'device',
            'output': 'json',
            'count': StatusFunctions.PRTG_API_RESPONSE_LIMIT,
            'apitoken': StatusFunctions.PRTG_API_KEY
        }
    )
    clover_ping_sensors_json = clover_ping_sensors_response.json()
    raw_clover_ping_sensors = clover_ping_sensors_json['sensors']
    
    # Check if there were no sensors returned.
    if len(raw_clover_ping_sensors) == 0:
        raise ValueError(f'No Clover ping sensors were found at site {site_id}')

    # Convert the raw response to a list of PRTGSensor objects.
    clover_ping_sensors = list[StatusFunctions.PRTGSensor]()
    for raw_clover_ping_sensor in raw_clover_ping_sensors:
        clover_ping_sensors.append(
            StatusFunctions.PRTGSensor(
                raw_clover_ping_sensor['device'],
                raw_clover_ping_sensor['group'],
                StatusFunctions.PRTG_STATUS_MAP[raw_clover_ping_sensor['status_raw']],
                raw_clover_ping_sensor['status_raw']
            )
        )
    
    # Return the Clover's ping sensors for the site.
    return clover_ping_sensors


def format_output(clover_ping_sensors: list[StatusFunctions.PRTGSensor]) -> dict:
    slack_message_json = {"blocks": []}
    
    if len(clover_ping_sensors) == 0:
        slack_message_json["blocks"].append(
            {
			    "type": "section",
			    "text": {
				    "type": "mrkdwn",
				    "text": f"{StatusFunctions.StatusEmoji.UP.value} All Clovers at this site are online!"
			    }
		    }
        )
        return slack_message_json
    
    for clover_ping_sensor in clover_ping_sensors:
        slack_message_json["blocks"].append(
            {
			    "type": "section",
			    "text": {
				    "type": "mrkdwn",
				    "text": f"{clover_ping_sensor.status} | {clover_ping_sensor.device_name}"
			    }
		    }
        )
        
    return slack_message_json


def is_valid_argument(arguments: list[str]) -> bool:
    """
    Validates the arguments to this command. This should be a list of each
    discrete string that the user used to tag and engage with the bot with
    the intentions of running a command.

    Args:
        arguments (list[str]): A list of arguments for this command. This will
            typically look like: ["@vitubot", "clovers", "{site ID}"]

    Returns:
        bool: True if the arguments are non-null, have the proper number of
            arguments, and the site ID provided is a 3-digit string. False
            otherwise.
    """
    
    # Check if the arguments are None.
    if arguments is None:
        error_message = 'Invalid arguments provided'
        logger.error(error_message)
        slack_service.send_error(error_message)
        return False
    
    # Check if there are an incorrect number of arguments.
    if len(arguments) > VALID_ARGUMENT_COUNT:
        error_message = f'Too many arguments - expecting {VALID_ARGUMENT_COUNT} but got {len(arguments)}'
        logger.error(error_message)
        slack_service.send_error(error_message)
        return False
    elif len(arguments) < VALID_ARGUMENT_COUNT:
        error_message = F'Too few arguments - expecting {VALID_ARGUMENT_COUNT}, but got {len(arguments)}'
        logger.error(error_message)
        slack_service.send_error(error_message)
        return False
    
    # Verify the format of the site's ID.
    site_id = arguments[2].strip()
    if not StatusFunctions.SITE_ID_REGEX.match(site_id):
        error_message = 'Invalid site ID - Must be a valid 3-digit ID'
        logger.error(error_message)
        slack_service.send_error(error_message)
        return False
    
    return True


def execute(arguments: list[str]) -> None:
    """
    Executes the clovers command. It will output all non-online Clover statuses
    at a specified site.

    Args:
        arguments (list[str]): The arguments to the command. This will
            typically look like: ["@vitubot", "clovers", "{site ID}"]
    """
    
    # Validate the arguments.
    if not is_valid_argument(arguments):
        return

    # Extract the site's ID from the arguments.
    site_id = arguments[2].strip()

    # Gather all the Clover's ping sensors. Send an error message to Slack if
    # something goes wrong.
    try:
        # Send the request to the PRTG API.
        clover_ping_sensors = get_clover_ping_sensors(site_id)
    except requests.RequestException as error:
        error_message = f'An unexpected request error occurred: {error}'
        logger.error(error_message)
        slack_service.send_error(error_message)
        return
    except requests.ConnectionError as error:
        error_message = f'A connection could not be established to PRTG: {error}'
        logger.error(error_message)
        slack_service.send_error(error_message)
        return
    except requests.HTTPError as error:
        error_message = f'An HTTP error occurred: {error}'
        logger.error(error_message)
        slack_service.send_error(error_message)
        return
    except requests.Timeout as error:
        error_message = f'The request to PRTG took too long: {error}'
        logger.error(error_message)
        slack_service.send_error(error_message)
        return
    except ValueError as error:
        logger.error(error)
        slack_service.send_error(error)
        return
    except Exception as error:
        error_message = f'An unknown error occurred: {error}'
        logger.error(error_message)
        slack_service.send_error(error_message)
        return
    
    # Filter out all online Clover pings.
    non_online_clovers = list(filter(lambda clover: clover.status_int != 3, clover_ping_sensors))
    
    # Format the Clover's ping statuses as a payload for the Slack API.
    clover_ping_statuses_payload = format_output(non_online_clovers)

    # Send the site's status to Slack.
    slack_service.send_message(clover_ping_statuses_payload)
