from dataclasses import dataclass
from enum import Enum
import json
import os
import re

from dotenv import load_dotenv
from loguru import logger
import meraki
from meraki.exceptions import APIError as MerakiAPIError

import slack


# ====================== Environment / Global Variables =======================
load_dotenv(override=True)

# Initialize Meraki constant global variables.
MERAKI_API_KEY = os.getenv('MERAKI_API_KEY')
MERAKI_ORGANIZATION_ID = os.getenv('MERAKI_ORGANIZATION_ID')
MERAKI_NETWORK_ID = os.getenv('MERAKI_NETWORK_ID')
MERAKI_DASHBOARD = meraki.DashboardAPI(MERAKI_API_KEY, output_log=False, print_console=False, suppress_logging=True)

# Other global constants.
MAC_ADDRESS_REGEX = re.compile('([0-9a-f]{2}:){5}[0-9a-f]{2}')
VALID_ARGUMENT_COUNT = 3


# =================================== Enums ===================================
class ClientStatus(Enum):
    ONLINE = ':large_green_circle: Online'
    OFFLINE = ':red_circle: Offline'
    UNKNOWN = ':grey_question: Unknown'


# ================================== Classes ==================================
@dataclass
class MerakiClient:
    mac_address: str
    name: str
    status: ClientStatus
    site_mac_address: str


# ================================= Functions =================================
def validate(arguments: list[str]) -> bool:
    # Check if the arguments are None.
    if arguments is None:
        error_message = 'Invalid arguments provided'
        logger.error(error_message)
        slack.send_error(error_message)
        return False
    
    # Check if there are an incorrect number of arguments.
    if len(arguments) > VALID_ARGUMENT_COUNT:
        error_message = 'Too many arguments'
        logger.error(error_message)
        slack.send_error(error_message)
        return False
    elif len(arguments) < VALID_ARGUMENT_COUNT:
        error_message = 'Too few arguments'
        logger.error(error_message)
        slack.send_error(error_message)
        return False
    
    # Verify the format of the MAC address is valid.
    mac_address = arguments[2].strip().lower()
    if not MAC_ADDRESS_REGEX.match(mac_address):
        error_message = 'Invalid MAC address - Must be a valid 12-digit MAC address with semi-colons (:)'
        logger.error(error_message)
        slack.send_error(error_message)
        return False
    
    return True


def get_meraki_client(mac_address: str) -> MerakiClient:
    # Try to find the client with the given MAC address in Meraki.
    meraki_client_response = MERAKI_DASHBOARD.networks.getNetworkClient(
        networkId=MERAKI_NETWORK_ID,
        clientId=mac_address
    )

    # Extract the client's MAC address, name, and status.
    client_mac_address = meraki_client_response['mac']
    client_name = client_mac_address if meraki_client_response['description'] is None else meraki_client_response['description']
    client_raw_status = meraki_client_response['status']
    site_mac_address = meraki_client_response['recentDeviceMac']
    
    # Convert the raw client status to a hard-typed status.
    if client_raw_status == 'Online':
        client_status = ClientStatus.ONLINE
    elif client_raw_status == 'Offline':
        client_status = ClientStatus.OFFLINE
    else:
        client_status = ClientStatus.UNKNOWN
    
    # Create the client object and return it.
    return MerakiClient(
        client_mac_address,
        client_name,
        client_status,
        site_mac_address
    )


def get_meraki_client_site(client: MerakiClient) -> str:
    site_name = ''
    
    # Get all network devices in Meraki.
    try:
        meraki_devices_response = MERAKI_DASHBOARD.networks.getNetworkDevices(
            networkId=MERAKI_NETWORK_ID
        )
    # Something went wrong. Send an error message to Slack.
    except MerakiAPIError:
        slack_message = f':yellow_circle: | Device with MAC address ' \
                        f'{client.mac_address} is ' \
                        f'{client.status.value} in ' \
                        f'Meraki, but I could not find the site the device ' \
                        f'is connected to'
        print(slack_message)
        return site_name

    # Find the device that the client is connected to and extract its name (the site's name).
    for meraki_device in meraki_devices_response:
        # Check if this is the site the client device is connected to.
        if meraki_device['mac'] == client.site_mac_address:
            site_name = meraki_device['name']
            break
    
    return site_name


def format_output(meraki_client: MerakiClient, site_name: str) -> dict[list]:
    slack_message_json = {"blocks": []}
    
    # Add the header to the message.
    slack_message_json['blocks'].append(
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Clover Device Status",
                "emoji": True
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
                    "text": f"*Name:*\n{meraki_client.name}"
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
                    "text": f"*MAC Address:*\n{meraki_client.mac_address}"
                }
            ]
        }
    )
    
    return slack_message_json


def execute(arguments: list[str]) -> None:
    """
    Given a MAC address, find the status of the associated client on the
    configured Meraki network. Then send the status of that client to the
    configured Slack channel. The status includes the Meraki device the client
    is connected to.

    Args:
        mac_address (str): The MAC address of the client device.
    """

    # Validate the arguments.
    if not validate(arguments):
        return
    
    # Extract the MAC address from the arguments.
    client_mac_address = arguments[2].strip().lower()

    # Get the Meraki client's information.
    try:
        meraki_client = get_meraki_client(client_mac_address)
    except MerakiAPIError as error:
        print(f'An API error occurred while getting client with MAC address {client_mac_address}')
        return

    # Get the site's name that the client is connected to.
    site_name = get_meraki_client_site(meraki_client)
    
    # Format the payload for Slack.
    slack_payload = format_output(meraki_client, site_name)

    print(json.dumps(slack_payload, indent=2))

    # Return the Meraki client's status to Slack.
    slack.send_message(slack_payload)
