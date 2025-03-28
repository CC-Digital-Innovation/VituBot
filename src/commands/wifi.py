from loguru import logger
from meraki.exceptions import APIError as MerakiAPIError

import services.constants as constants
import services.meraki as meraki_service
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
            typically look like: ["@vitubot", "wifi", "{Clover MAC address}"]

    Returns:
        bool: True if the arguments are non-null, have the proper number of
            arguments, and a valid Clover MAC address. False otherwise.
    """
    
    # Check if the arguments are None.
    if arguments is None:
        error_message = 'Invalid arguments provided - please try again'
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
        error_message = f'Too few arguments - expecting {VALID_ARGUMENT_COUNT}, but got {len(arguments)}'
        logger.error(error_message)
        slack_service.send_error(error_message)
        return False
    
    # Verify the format of the MAC address is valid.
    mac_address = arguments[2].strip().lower()
    if not constants.MAC_ADDRESS_REGEX.match(mac_address):
        error_message = 'Invalid MAC address - Must be a valid 12-digit MAC address with semi-colons (:)'
        logger.error(error_message)
        slack_service.send_error(error_message)
        return False
    
    return True


def format_output(meraki_client: meraki_service.Client, site_name: str) -> dict[list]:
    """
    Formats the output of the Slack message. Makes the output look
    sophisticated and pretty to convey the overall status effectively.

    Args:
        meraki_client (MerakiClient): The client to output the status for.
        site_name (str): The name of the site the client is connected to.

    Returns:
        dict[list]: The JSON-formatted dictionary object for the Slack API.
    """
    
    slack_message_json = {"blocks": []}
    
    # Add the header to the message.
    slack_message_json['blocks'].append(
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Clover Device Status",
                "emoji": False
            }
        }
    )
    
    # Add the client status to the message.
    slack_message_json['blocks'].append(
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Name:*\n`{meraki_client.name}`"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Status:*\n{meraki_client.status.value}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Site:*\n{'?' if site_name is None or site_name == '' else site_name}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*MAC Address:*\n`{meraki_client.mac_address}`"
                }
            ]
        }
    )
    
    return slack_message_json


def execute(arguments: list[str]) -> None:
    """
    Executes the status command. It will output the status of a client in
    Meraki, which will typically be a Clover device. The output includes the
    client's status and the site it is connected to.

    Args:
        arguments (list[str]): The arguments to the command. This will
            typically look like: ["@vitubot", "wifi", "{Clover MAC address}"]
    """

    # Validate the arguments.
    if not is_valid_argument(arguments):
        return
    
    # Extract the MAC address from the arguments.
    client_mac_address = arguments[2].strip().lower()

    # Get the client's status and its site name.
    try:
        # Get the Meraki client's information.
        meraki_client = meraki_service.get_client(client_mac_address)
        
        # Get the site's name that the client is connected to.
        site_name = meraki_service.get_client_site(meraki_client)
    except MerakiAPIError as error:
        if error.status == 404:
            error_message = f"Could not find Clover with MAC address `{client_mac_address}`"
            logger.error(error_message.replace('`', ''))
            slack_service.send_error(error_message)
        else:
            error_message = f"An API error occurred while getting the client's status with MAC address `{client_mac_address}`"
            logger.error(error_message.replace('`', ''))
            logger.error(f'API error: {error}')
            slack_service.send_error(error_message)
        return
    
    # Format the payload for Slack.
    slack_payload = format_output(meraki_client, site_name)

    # Return the Meraki client's status to Slack.
    slack_service.send_message(slack_payload)
