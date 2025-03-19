from loguru import logger
import requests

import services.constants as constants
import services.prtg as prtg_service
import services.slack as slack_service


# ====================== Environment / Global Variables =======================
VALID_ARGUMENT_COUNT = 3


# ================================= Functions =================================
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
    if not constants.THREE_DIGITS_REGEX.match(site_id):
        error_message = 'Invalid site ID - Must be a valid 3-digit ID'
        logger.error(error_message)
        slack_service.send_error(error_message)
        return False
    
    return True


def format_output(clover_ping_sensors: list[prtg_service.Sensor]) -> dict:
    slack_message_json = {
        "blocks": 
            [
                {
                    "type": "header",
                    "text": {
				        "type": "plain_text",
				        "text": "All Non-Online Clovers",
				        "emoji": True
			        }
                }
            ]
    }
    
    if len(clover_ping_sensors) == 0:
        slack_message_json["blocks"].append(
            {
			    "type": "section",
			    "text": {
				    "type": "mrkdwn",
				    "text": f"{constants.SlackEmojiCodes.GREEN_CIRCLE.value} All Clovers at this site are online!"
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
        clover_ping_sensors = prtg_service.get_all_clover_pings(site_id)
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
