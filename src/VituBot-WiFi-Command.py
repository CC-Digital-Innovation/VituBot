import configparser
import os

import meraki
from meraki import exceptions
import requests


# Module information.
__author__ = 'Anthony Farina'
__copyright__ = 'Copyright (C) 2022 Anthony Farina'
__credits__ = ['Anthony Farina']
__maintainer__ = 'Anthony Farina'
__email__ = 'farinaanthony96@gmail.com'
__license__ = 'MIT'
__version__ = '1.0.0'
__status__ = 'Released'


# Configuration file access variables.
CONFIG = configparser.ConfigParser()
CONFIG_PATH = '../configs/VituBot-config.ini'
SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))
CONFIG.read(SCRIPT_PATH + CONFIG_PATH)

# Meraki API credentials.
MERAKI_API_KEY = CONFIG['Meraki Info']['api-key']
MERAKI_ORG_ID = CONFIG['Meraki Info']['org-id']
MERAKI_NET_ID = CONFIG['Meraki Info']['net-id']

# Slack configurations.
SLACK_POST_CHANNEL = str('#' + CONFIG['Slack Info']['channel'])
SLACK_TOKEN = CONFIG['Slack Info']['oauth-token']


# Given a MAC address, find the status of the client on the configured
# Meraki network. Then send the status to the configured Slack channel.
def meraki_get_client_status(mac_addr: str):
    # Set up the connection to Meraki.
    meraki_dash = meraki.DashboardAPI(MERAKI_API_KEY,
                                      output_log=False,
                                      print_console=False,
                                      suppress_logging=True)

    # Try to find the device with the given MAC address in Meraki.
    try:
        response = meraki_dash.networks.getNetworkClient(
            networkId=MERAKI_NET_ID,
            clientId=mac_addr
        )
    # Something went wrong. Send the response to Slack.
    except meraki.exceptions.APIError:
        resp = ':exclamation: | Error finding device with MAC address \"' + \
               mac_addr + '\" in Meraki'
        send_slack_response(resp)
        return

    # Check the device's status on Meraki.
    if response['status'] == 'Online':
        resp = ':large_green_circle: | Device with MAC address \"' + \
               mac_addr + '\" is ONLINE in Meraki'
    elif response['status'] == 'Offline':
        resp = ':red_circle: | Device with MAC address \"' + mac_addr + \
               '\" is OFFLINE in Meraki'
    else:
        resp = ':grey_question: | Device with MAC address \"' + mac_addr + \
               '\" is UNKNOWN in Meraki'

    # Return the result to Slack.
    send_slack_response(resp)


# Send the provided response to the configured Slack channel.
def send_slack_response(response: str):
    requests.post(url='https://slack.com/api/chat.postMessage',
                  headers={
                      'Authorization': 'Bearer ' + SLACK_TOKEN,
                      'Content-Type': 'application/json; '
                                      'charset=utf-8'
                  },
                  json={
                      'channel': SLACK_POST_CHANNEL,
                      'text': response,
                      'as_user': False,
                      'username': 'vitubot',
                      'icon_url':
                          'https://img.icons8.com/plasticine/2x/bot.png'
                  })
