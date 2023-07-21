import configparser
import os
import re
import sys

import meraki
from meraki import exceptions
import requests


# Module information.
__author__ = 'Anthony Farina'
__copyright__ = 'Copyright (C) 2023 Anthony Farina'
__credits__ = ['Anthony Farina']
__maintainer__ = 'Anthony Farina'
__email__ = 'farinaanthony96@gmail.com'
__license__ = 'MIT'
__version__ = '2.0.0'
__status__ = 'Released'


# Configuration file access variables.
CONFIG = configparser.ConfigParser()
CONFIG_PATH = '../configs/VituBot-config.ini'
SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))
CONFIG.read(SCRIPT_PATH + '/' + CONFIG_PATH)

# Meraki API credentials.
MERAKI_API_KEY = CONFIG['Meraki Info']['api-key']
MERAKI_ORG_ID = CONFIG['Meraki Info']['org-id']
MERAKI_NET_ID = CONFIG['Meraki Info']['net-id']

# Slack configurations.
SLACK_POST_CHANNEL = f'#{CONFIG["Slack Info"]["channel"]}'
SLACK_AUTH_TOKEN = CONFIG['Slack Info']['oauth-token']

# Other global constants.
MAC_REGEX = re.compile('([0-9a-f]{2}:){5}[0-9a-f]{2}')


def run_vitubot_wifi_command(mac_addr: str) -> None:
    """
    Given a MAC address, find the status of the associated client on the
    configured Meraki network. Then send the status of that client to the
    configured Slack channel. The status includes the Meraki device the client
    is connected to.

    :param mac_addr: The MAC address of the client device.
    """

    # Clean the MAC address string provided.
    clean_mac = mac_addr.lower().replace('-', ':')

    # Check if the MAC address string is an invalid MAC address.
    if not MAC_REGEX.match(clean_mac):
        send_slack_message(f':exclamation: | {clean_mac} is not a valid MAC '
                           f'address')
        return

    # Set up the connection to the Meraki dashboard.
    meraki_dash = meraki.DashboardAPI(MERAKI_API_KEY, output_log=False)

    # Try to find the client with the given MAC address in Meraki.
    try:
        meraki_client_response = meraki_dash.networks.getNetworkClient(
            networkId=MERAKI_NET_ID,
            clientId=clean_mac
        )
    # Something went wrong. Send an error message to Slack.
    except meraki.exceptions.APIError:
        slack_message = f':exclamation: | A Meraki API error occurred while ' \
                        f'finding device with MAC address {clean_mac} in Meraki'
        send_slack_message(slack_message)
        return

    # Extract the Meraki device's MAC address.
    meraki_device_mac = meraki_client_response['recentDeviceMac']

    # Get the Meraki device's information.
    try:
        meraki_devices_response = meraki_dash.networks.getNetworkDevices(
            networkId=MERAKI_NET_ID
        )
    # Something went wrong. Send an error message to Slack.
    except meraki.exceptions.APIError:
        slack_message = f':yellow_circle: | Device with MAC address ' \
                        f'{mac_addr} is ' \
                        f'{meraki_client_response["status"].upper()} in ' \
                        f'Meraki, but I could not find the site the device ' \
                        f'is connected to'
        send_slack_message(slack_message)
        return

    # Find the Meraki device's name from the Meraki devices response.
    meraki_device_name = None
    for meraki_device in meraki_devices_response:
        # Check if this is the Meraki device the client device is connected to.
        if meraki_device['mac'] == meraki_device_mac:
            meraki_device_name = meraki_device['name']
            break

    # Check if we could not find the associated Meraki device from the
    # Meraki devices response.
    if not meraki_device_name:
        slack_message = f':yellow_circle: | Device with MAC address ' \
                        f'{mac_addr} is ' \
                        f'{meraki_client_response["status"].upper()} ' \
                        f'in Meraki, but I could not find the site the ' \
                        f'device is connected to'
        send_slack_message(slack_message)
        return

    # Assemble the Slack message to send based off the Meraki client's status.
    if meraki_client_response['status'] == 'Online':
        slack_message = f':large_green_circle: | Device with MAC address ' \
                f'{clean_mac} is ONLINE in Meraki at site ' \
                f'{meraki_device_name}'
    elif meraki_client_response['status'] == 'Offline':
        slack_message = f':red_circle: | Device with MAC address {clean_mac} ' \
                f'is OFFLINE in Meraki at site {meraki_device_name}'
    else:
        slack_message = f':grey_question: | Device with MAC address ' \
                        f'{clean_mac} is UNKNOWN in Meraki at site ' \
                        f'{meraki_device_name}'

    # Return the Meraki client's status to Slack.
    send_slack_message(slack_message)


def send_slack_message(message: str) -> None:
    """
    Send the provided message to the configured Slack channel.

    :param message: The message to send to Slack.
    """

    requests.post(
        url='https://slack.com/api/chat.postMessage',
        headers=
        {
            'Authorization': 'Bearer ' + SLACK_AUTH_TOKEN,
            'Content-Type': 'application/json; charset=utf-8'
        },
        json=
        {
            'channel': SLACK_POST_CHANNEL,
            'text': message,
            'as_user': False,
            'username': 'vitubot',
            'icon_url': 'https://img.icons8.com/plasticine/2x/bot.png'
        }
    )


# Main method for the script. Input is 1 argument: a valid MAC address string.
if __name__ == '__main__':
    # Check if an input argument was not given to the script.
    if len(sys.argv) != 2:
        invalid_input_message = ':exclamation: | Invalid number of arguments ' \
                                'given'
        send_slack_message(invalid_input_message)
    # Run the script.
    else:
        run_vitubot_wifi_command(sys.argv[1])
