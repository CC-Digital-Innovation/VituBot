from dataclasses import dataclass
from enum import Enum

import asyncio
from dotenv import load_dotenv
import os
import requests

import services.constants as constants


# ====================== Environment / Global Variables =======================
load_dotenv(override=True)

# Initialize PRTG constant global variables.
INSTANCE_NAME = os.getenv('PRTG_INSTANCE_NAME')
TABLE_URL = f'https://{INSTANCE_NAME}/api/table.xml'
API_KEY = os.getenv('PRTG_API_KEY')
PI_LTE_DONGLE_GROUP = 'PI - LTE'
PROBE_HEALTH_NAME = 'Probe Health'
PING_NAME = 'Ping'
PRIMARY_INTERFACE_NAME = 'Primary Interface'
API_RESPONSE_LIMIT = '50000'
STATUS_MAP = {
    0: f'{constants.SlackEmojiCodes.BLACK_SQUARE.value} None',
    1: f'{constants.SlackEmojiCodes.GRAY_QUESTION_MARK.value} Unknown',
    2: f'{constants.SlackEmojiCodes.REPEAT_BUTTON.value} Scanning',
    3: f'{constants.SlackEmojiCodes.GREEN_CIRCLE.value} Up',
    4: f'{constants.SlackEmojiCodes.YELLOW_CIRCLE.value} Warning',
    5: f'{constants.SlackEmojiCodes.RED_CIRCLE.value} Down',
    6: f'{constants.SlackEmojiCodes.BLACK_SQUARE.value} No Probe',
    7: f'{constants.SlackEmojiCodes.PAUSE_BUTTON.value} Paused by User',
    8: f'{constants.SlackEmojiCodes.PAUSE_BUTTON.value} Paused by Dependency',
    9: f'{constants.SlackEmojiCodes.PAUSE_BUTTON.value} Paused by Schedule',
    10: f'{constants.SlackEmojiCodes.ORANGE_CIRCLE.value} Unusual',
    11: f'{constants.SlackEmojiCodes.NO_SYMBOL.value} Not Licensed',
    12: f'{constants.SlackEmojiCodes.PAUSE_BUTTON.value} {constants.SlackEmojiCodes.THREE_O_CLOCK.value} Paused Temporarily',
    13: f'{constants.SlackEmojiCodes.HOLLOW_RED_CIRCLE.value} Down Acknowledged',
    14: f'{constants.SlackEmojiCodes.GREEN_CIRCLE.value} {constants.SlackEmojiCodes.RED_CIRCLE.value} Down Partial'
}


# =================================== Enums ===================================
class GroupType(Enum):
    """
    Represents the types of groups associated with a probe in PRTG.
    """
    
    NETWORK_DEVICES = 'Network Devices'
    CLOVER_DEVICES = 'Clover Devices'


# ================================== Classes ==================================
@dataclass
class Sensor:
    """
    Represents a sensor in PRTG.
    
    Args:
        device_name (str): The name of the device this sensor is associated
            with.
        device_group (str): The name of the group this sensor's device is in.
        status (str): The string representation of the sensor's status.
        status_int (int): The integer representation of the sensor's status.
    """
    
    device_name: str
    device_group: str
    status: str
    status_int: int
    

# ================================= Functions =================================
def get_probe_health(site_id: str) -> Sensor:
    """
    Gets the status of the probe health sensor with the associated site ID from
    PRTG and returns the information as a PRTG sensor object.

    Args:
        site_id (str): The 3-digit site ID that the probe is associated with.

    Raises:
        ValueError: The site ID was not found in PRTG.

    Returns:
        Sensor: The probe health sensor for the site.
    """
    
    # Get the status of this site's probe health sensor.
    probe_health_sensor_response = requests.get(
        url=TABLE_URL,
        params={
            'content': 'sensors',
            'columns': 'name,device,group,probe,status',
            'filter_probe': f'@sub({site_id})',
            'filter_name': PROBE_HEALTH_NAME,
            'sortby': 'device',
            'output': 'json',
            'count': '2',
            'apitoken': API_KEY
        }
    )
    probe_health_sensor_json = probe_health_sensor_response.json()
    
    # Check if we could not find the site's probe health sensor.
    if len(probe_health_sensor_json['sensors']) == 0:
        raise ValueError(f'Probe does not exist with site ID: {site_id}')

    # Make the sensor object and return it.
    raw_probe_health_sensor = probe_health_sensor_json['sensors'][0]
    site_probe_health_status_int = raw_probe_health_sensor['status_raw']
    
    return Sensor(
        raw_probe_health_sensor['device'], 
        raw_probe_health_sensor['group'], 
        STATUS_MAP[site_probe_health_status_int], 
        site_probe_health_status_int
    )


def get_primary_interface(site_id: str) -> Sensor:
    """
    Gets the status of the primary interface sensor from PRTG and returns the
    information as a PRTG sensor object.

    Args:
        site_id (str): The 3-digit site ID that the probe is associated with.

    Raises:
        ValueError: The site ID was not found in PRTG.

    Returns:
        Sensor: The primary interface sensor for the site.
    """
    
    # Get the "Primary Interface" sensor for this site to see if it has failed over.
    primary_interface_response = requests.get(
        url=TABLE_URL,
        params={
            'content': 'sensors',
            'columns': 'name,status,probe,group,device',
            'filter_probe': f'@sub({site_id})',
            'filter_name': PRIMARY_INTERFACE_NAME,
            'output': 'json',
            'count': '2',
            'apitoken': API_KEY
        }
    )
    primary_interface_json = primary_interface_response.json()
    
    # Check if we could not find the site's primary interface sensor.
    if len(primary_interface_json['sensors']) == 0:
        raise ValueError(f'Primary interface sensor not found at site {site_id}')
    
    # Make the sensor object and return it.
    raw_primary_interface_sensor = primary_interface_json['sensors'][0]
    site_primary_interface_status_int = raw_primary_interface_sensor['status_raw']
    
    return Sensor(
        raw_primary_interface_sensor['device'],
        raw_primary_interface_sensor['group'],
        STATUS_MAP[site_primary_interface_status_int],
        site_primary_interface_status_int
    )


def get_pi_lte_dongle(site_id: str) -> Sensor:
    """
    Gets the status of the LTE dongle plugged into the Raspberry Pi from PRTG
    and returns the information as a PRTG sensor object.

    Args:
        site_id (str): The 3-digit site ID that the probe is associated with.

    Raises:
        ValueError: The site ID was not found in PRTG.

    Returns:
        Sensor: The pi LTE dongle sensor for the site.
    """
    
    # Get the status of this site's pi LTE dongle from PRTG.
    site_pi_lte_dongle_response = requests.get(
        url=TABLE_URL,
        params={
            'content': 'sensors',
            'columns': 'name,device,group,status',
            'filter_group': PI_LTE_DONGLE_GROUP,
            'filter_device': f'@sub({site_id})',
            'filter_name': PING_NAME,
            'output': 'json',
            'count': '2',
            'apitoken': API_KEY
        }
    )
    pi_lte_dongle_json = site_pi_lte_dongle_response.json()
    
    # Check if we could not find the site's pi LTE dongle.
    if len(pi_lte_dongle_json['sensors']) == 0:
        raise ValueError(f'Pi LTE dongle sensor not found at site {site_id}')

    # Make the sensor object and return it.
    raw_pi_lte_dongle_sensor = pi_lte_dongle_json['sensors'][0]
    pi_lte_dongle_status_int = raw_pi_lte_dongle_sensor['status_raw']
    
    return Sensor(
        raw_pi_lte_dongle_sensor['device'], 
        raw_pi_lte_dongle_sensor['group'], 
        STATUS_MAP[pi_lte_dongle_status_int], 
        pi_lte_dongle_status_int
    )
    

def get_all_pings(site_id: str) -> list[Sensor]:
    """
    Gets the status of all the ping sensors at a site from PRTG and returns the 
    information as a list of sensor objects.

    Args:
        site_id (str): The site ID that the ping sensors are associated with.

    Raises:
        ValueError: The site ID was not found in PRTG.

    Returns:
        list[Sensor]: All ping sensors at the site.
    """
    
    # Get all the device's statuses via their ping sensor's status at this site.
    all_ping_sensors_response = requests.get(
        url=TABLE_URL,
        params={
            'content': 'sensors',
            'columns': 'name,device,group,probe,status,parentid',
            'filter_probe': f'@sub({site_id})',
            'filter_name': PING_NAME,
            'sortby': 'device',
            'output': 'json',
            'count': API_RESPONSE_LIMIT,
            'apitoken': API_KEY
        }
    )
    all_ping_sensors_json = all_ping_sensors_response.json()
    raw_ping_sensors = all_ping_sensors_json['sensors']
    
    # Check if there were no sensors returned.
    if len(raw_ping_sensors) == 0:
        raise ValueError(f'No ping sensors were found at site {site_id}')

    # Convert the raw response to a list of sensor objects.
    all_ping_sensors = list[Sensor]()
    for raw_ping_sensor in raw_ping_sensors:
        all_ping_sensors.append(
            Sensor(
                raw_ping_sensor['device'],
                raw_ping_sensor['group'],
                STATUS_MAP[raw_ping_sensor['status_raw']],
                raw_ping_sensor['status_raw']
            )
        )
    
    # Return the site's ping sensors.
    return all_ping_sensors


def get_all_clover_pings(site_id: str) -> list[Sensor]:
    """
    Gets the status of all the Clover ping sensors at a site from PRTG and
    returns the information as a list of sensor objects.

    Args:
        site_id (str): The site ID that the Clovers are associated with.

    Raises:
        ValueError: The site ID was not found in PRTG.

    Returns:
        list[Sensor]: All Clover ping sensors at the site.
    """
    
    # Get all the Clover's statuses via their ping sensor's status at this site.
    all_clover_ping_sensors_response = requests.get(
        url=TABLE_URL,
        params={
            'content': 'sensors',
            'columns': 'name,device,group,probe,status,parentid',
            'filter_probe': f'@sub({site_id})',
            'filter_group': f'@sub({GroupType.CLOVER_DEVICES.value})',
            'filter_name': PING_NAME,
            'sortby': 'device',
            'output': 'json',
            'count': API_RESPONSE_LIMIT,
            'apitoken': API_KEY
        }
    )
    all_clover_ping_sensors_json = all_clover_ping_sensors_response.json()
    raw_clover_ping_sensors = all_clover_ping_sensors_json['sensors']
    
    # Check if there were no sensors returned.
    if len(raw_clover_ping_sensors) == 0:
        raise ValueError(f'No Clover ping sensors were found at site {site_id}')

    # Convert the raw response to a list of sensor objects.
    all_clover_ping_sensors = list[Sensor]()
    for raw_clover_ping_sensor in raw_clover_ping_sensors:
        all_clover_ping_sensors.append(
            Sensor(
                raw_clover_ping_sensor['device'],
                raw_clover_ping_sensor['group'],
                STATUS_MAP[raw_clover_ping_sensor['status_raw']],
                raw_clover_ping_sensor['status_raw']
            )
        )
    
    # Return the site's Clover ping sensors.
    return all_clover_ping_sensors


# ============================== Async Functions ==============================
async def get_probe_health_async(site_id: str) -> Sensor:
    """
    The asynchronous version of "get_probe_health()".
    """
    return await asyncio.to_thread(get_probe_health, site_id)


async def get_primary_interface_async(site_id: str) -> Sensor:
    """
    The asychronous version of "get_primary_interface()".
    """
    return await asyncio.to_thread(get_primary_interface, site_id)


async def get_pi_lte_dongle_async(site_id: str) -> Sensor:
    """
    The asychronous version of "get_pi_lte_dongle()".
    """
    return await asyncio.to_thread(get_pi_lte_dongle, site_id)


async def get_all_pings_async(site_id: str) -> list[Sensor]:
    """
    The asychronous version of "get_all_pings()".
    """
    return await asyncio.to_thread(get_all_pings, site_id)