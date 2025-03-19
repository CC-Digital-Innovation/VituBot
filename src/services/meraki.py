from dataclasses import dataclass
from enum import Enum
import os

from dotenv import load_dotenv
import meraki as MerakiSDK

import services.constants as constants


# ====================== Environment / Global Variables =======================
load_dotenv(override=True)

# Initialize Meraki constant global variables.
API_KEY = os.getenv('MERAKI_API_KEY')
ORGANIZATION_ID = os.getenv('MERAKI_ORGANIZATION_ID')
NETWORK_ID = os.getenv('MERAKI_NETWORK_ID')
DASHBOARD_CLIENT = MerakiSDK.DashboardAPI(
    API_KEY,
    output_log=False,
    print_console=False,
    suppress_logging=True
)


# =================================== Enums ===================================
class ClientStatus(Enum):
    """
    Represents the pretty / presentable string of the status of a client in
    Meraki.
    """
    
    ONLINE = f'{constants.SlackEmojiCodes.GREEN_CIRCLE.value} Online'
    OFFLINE = f'{constants.SlackEmojiCodes.RED_CIRCLE.value} Offline'
    UNKNOWN = f'{constants.SlackEmojiCodes.GRAY_QUESTION_MARK.value} Unknown'


# ================================== Classes ==================================
@dataclass
class Client:
    """
    Represents a client connected to a device in Meraki.
    
    Args:
        mac_address (str): The MAC address of the client.
        name (str): The name of the client as seen in the Meraki dashboard.
        status (ClientStatus): The presentable status of the client.
        site_mac_address (str): The MAC address of the device that the client
            is connected to.
    """
    
    mac_address: str
    name: str
    status: ClientStatus
    site_mac_address: str
    
    
# ================================= Functions =================================
def get_client(mac_address: str) -> Client:
    """
    Retrieves the client with the provided MAC address from Meraki.

    Args:
        mac_address (str): The MAC address of the desired client.

    Returns:
        Client: The associated client with name, status, and the MAC address
            of the device the client is connected to (its site).
    """
    
    # Try to find the client with the given MAC address in Meraki.
    client_response = DASHBOARD_CLIENT.networks.getNetworkClient(
        networkId=NETWORK_ID,
        clientId=mac_address
    )

    # Extract the client's MAC address, name, status, and the MAC address of
    # the device the client is connected to.
    mac_address = client_response['mac']
    name = mac_address if client_response['description'] is None else client_response['description']
    raw_status = client_response['status']
    site_mac_address = client_response['recentDeviceMac']
    
    # Convert the raw client status to a hard-typed status.
    if raw_status == 'Online':
        client_status = ClientStatus.ONLINE
    elif raw_status == 'Offline':
        client_status = ClientStatus.OFFLINE
    else:
        client_status = ClientStatus.UNKNOWN
    
    # Create the client object and return it.
    return Client(
        mac_address,
        name,
        client_status,
        site_mac_address
    )


def get_client_site(client: Client) -> str:
    """
    Retrieves the device that the provided client is connected to in Meraki.

    Args:
        client (Client): The client associated with the device we are trying to
            find in Meraki.

    Returns:
        str: The name of the device associated with the client (the name of
            the site). Returns the empty string '' if the device was not found
            in Meraki.
    """
    
    site_name = ''
    
    # Get all network devices in Meraki.
    all_devices_response = DASHBOARD_CLIENT.networks.getNetworkDevices(
        networkId=NETWORK_ID
    )

    # Find the device that the client is connected to and extract its name (the
    # site's name).
    for device in all_devices_response:
        # Check if this is the device the client is connected to.
        if device['mac'] == client.site_mac_address:
            site_name = device['name']
            break
    
    return site_name
