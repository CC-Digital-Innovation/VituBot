from dataclasses import dataclass
from enum import Enum
import os
import re

import slack

import asyncio
from dotenv import load_dotenv
from loguru import logger
import requests


# ====================== Environment / Global Variables =======================
load_dotenv(override=True)

# Initialize PRTG constant global variables.
PRTG_INSTANCE_NAME = os.getenv('PRTG_INSTANCE_NAME')
PRTG_TABLE_URL = f'https://{PRTG_INSTANCE_NAME}/api/table.xml'
PRTG_API_KEY = os.getenv('PRTG_API_KEY')
PRTG_PI_LTE_DONGLE_GROUP = 'PI - LTE'
PRTG_PROBE_HEALTH_NAME = 'Probe Health'
PRTG_PING_NAME = 'Ping'
PRTG_PRIMARY_INTERFACE_NAME = 'Primary Interface'
PRTG_API_RESPONSE_LIMIT = '50000'
PRTG_STATUS_MAP = {
    0: ':black_square: None',
    1: ':grey_question: Unknown',
    2: ':arrows_counterclockwise: Scanning',
    3: ':large_green_circle: Up',
    4: ':large_yellow_circle: Warning',
    5: ':red_circle: Down',
    6: ':black_square: No Probe',
    7: ':double_vertical_bar: Paused by User',
    8: ':double_vertical_bar: Paused by Dependency',
    9: ':double_vertical_bar: Paused by Schedule',
    10: ':large_orange_circle: Unusual',
    11: ':no_entry_sign: Not Licensed',
    12: ':double_vertical_bar: :clock3: Paused Temporarily',
    13: ':o: Down Acknowledged',
    14: ':large_green_circle: :red_circle: Down Partial'
}

# Initialize other constant global variables.
SITE_ID_REGEX = re.compile('[0-9]{3}')
VALID_ARGUMENT_COUNT = 3


# =================================== Enums ===================================
class GroupType(Enum):
    """
    Represents the types of groups in PRTG we are reporting the status for.
    """
    
    NETWORK_DEVICES = 'Network Devices'
    CLOVER_DEVICES = 'Clover Devices'
    
    
class StatusEmoji(Enum):
    """
    Represents the emoji strings that are associated with each status type.
    """
    
    UP = ':large_green_circle:'
    WARNING = ':large_yellow_circle:'
    DOWN = ':red_circle:'
    PAUSED = ':double_vertical_bar:'
    UNKNOWN = ':grey_question:'


class OverallStatus(Enum):
    """
    Represents the different overall statuses with associated emoji strings.
    """
    
    HEALTHY = f'{StatusEmoji.UP.value} Healthy'
    DEGRADED = f'{StatusEmoji.WARNING.value} Degraded'
    CRITICAL = f'{StatusEmoji.DOWN.value} CRITICAL'
    PAUSED = f'{StatusEmoji.PAUSED.value} Paused'
    UNKNOWN = f'{StatusEmoji.UNKNOWN.value} Unknown'


# ================================== Classes ==================================
@dataclass
class PRTGSensor:
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


class ProbeDevice:
    """
    Represents a probe device and its properties and associated sensors.

    Members:
        probe_health_sensor (PRTGSensor): The sensor that checks on the probe's
            health.
        primary_interface_sensor (PRTGSensor): The sensor that checks whether
            the probe is getting an active internet connection through ethernet
            or not.
        primary_interface_description (str): Describes the failover status of
            the probe.
        is_lte_only (bool): True if this is an LTE-only site. False otherwise.
            An LTE-only site will ALWAYS be connected to the internet via a
            cellular dongle attached to a Raspberry Pi at the site.
        overall_status (OverallStatus): The overall status of the site with
            included status emoji.
    """
    
    probe_health_sensor: PRTGSensor
    primary_interface_sensor: PRTGSensor
    primary_interface_description: str
    is_lte_only: bool
    overall_status: OverallStatus
    
    def __init__(self, probe_health_sensor: PRTGSensor, primary_interface_sensor: PRTGSensor):
        """
        Initializes a probe device with its properties and sensors.

        Args:
            probe_health_sensor (PRTGSensor): The sensor that checks on the
                probe's health.
            primary_interface_sensor (PRTGSensor): The sensor that checks
                whether the probe is getting an active internet connection
                through ethernet versus through an LTE connection.
        """
        
        # Set fields based off the parameters.
        self.probe_health_sensor = probe_health_sensor
        self.primary_interface_sensor = primary_interface_sensor
        self.is_lte_only = True if 'LTE Only' in self.probe_health_sensor.device_group else False
        
        # Determine the overall status.
        # Check if the probe is up.
        if self.probe_health_sensor.status_int == 3:
            self.overall_status = OverallStatus.HEALTHY
        # Check if the probe health is in a warning / niche status.
        elif self.probe_health_sensor.status_int in [2, 4, 6, 10, 11, 14]:
            self.overall_status = OverallStatus.DEGRADED
        # Check if the probe is paused.
        elif self.probe_health_sensor.status_int in [7, 8, 9, 12]:  
            self.overall_status = OverallStatus.PAUSED
        # The probe is in some sort of down state.
        else:
            self.overall_status = OverallStatus.CRITICAL
        
        # Determine the site's failover status.
        # Check if the probe is up.
        if self.probe_health_sensor.status_int == 3:
            # Check if the probe is connected to the internet via an ISP
            # ethernet connection.
            if self.primary_interface_sensor.status_int == 3:
                self.primary_interface_description = 'Site is on ISP connection'
            else:
                # Check if this site is an LTE only site.
                if self.is_lte_only:
                    self.primary_interface_description = 'Site is on LTE connection'
                # If site is not an LTE only site and is on an LTE connection,
                # it must have failed over.
                else:
                    self.primary_interface_description = 'Site has failed over to LTE connection'
                    self.overall_status = OverallStatus.DEGRADED
        # Probe must be down.
        else:
            self.primary_interface_description = 'Site is down'
    
    def generate_slack_message_section_json(self) -> dict:
        """
        Generate the JSON-formatted dictionary that is compatible with Slack's
        message conventions of this object's properties and overall status.

        Returns:
            dict: The JSON-formatted Slack message payload of this object's
                properties and overall status.
        """
        
        slack_message_json = {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Overall Status:*\n{self.overall_status.value}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Probe Health:*\n{self.probe_health_sensor.status}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Primary Interface:*\n{self.primary_interface_sensor.status}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Failover Status:*\n{self.primary_interface_description}"
                }
            ]
        }
        
        return slack_message_json


class NetworkDevicesGroup:
    """
    Represents the network devices group for a site. Includes the ping sensors
    for each network device in the group along with the name, overall status,
    and a count of each type of status.

    Members:
        name (str): The name of the network devices group.
        overall_status (OverallStatus): The overall status of the site.
        pi_lte_dongle (PRTGSensor): The ping sensor for the LTE dongle that is
            connected to the site's Raspberry Pi.
        meraki_device (PRTGSensor): The ping sensor for the Meraki wireless
            access point. Connects the Clovers to the internet.
        router (PRTGSensor): The ping sensor for the Cradlepoint router.
            Supplies internet to all the network devices (NOT the Clovers).
        pdu (PRTGSensor): The ping sensor for the PDU that powers all the
            networking equipment.
        vitupay_com (PRTGSensor): The ping sensor for the connection to
            api.ca.vitupay.com.
        pi_device (PRTGSensor): The ping sensor for the Raspberry Pi.
        clover_com (PRTGSensor): The ping sensor for the connection to
            d.clover.com.
        up_devices (int): The number of network devices that are online.
        warning_devices (int): The number of network devices that are in some
            sort of warning / niche state.
        paused_devices (int): The number of network devices that are paused.
        down_devices (int): The number of network devices that are down.
    """
    
    name: str
    overall_status: OverallStatus
    pi_lte_dongle: PRTGSensor = None
    meraki_device: PRTGSensor = None
    router: PRTGSensor = None
    pdu: PRTGSensor = None
    vitupay_com: PRTGSensor = None
    pi_device: PRTGSensor = None
    clover_com: PRTGSensor = None
    up_devices: int = 0
    warning_devices: int = 0
    paused_devices: int = 0
    down_devices: int = 0

    def __init__(self, all_probe_ping_sensors: list[PRTGSensor], site_pi_lte_dongle_sensor: PRTGSensor):
        """
        Initializes a network devices group object. Stores information
        regarding the status of all the network devices for this site.

        Args:
            all_probe_ping_sensors (list[PRTGSensor]): List of ping PRTGSensors
                associated with all devices with the probe.
            site_pi_lte_dongle_sensor (PRTGSensor): The ping PRTGSensor of the 
                site's LTE dongle plugged into the Raspberry Pi.
        """
        
        # Add the Pi LTE dongle to this group and check if it is online.
        self.pi_lte_dongle = site_pi_lte_dongle_sensor
        if self.pi_lte_dongle is not None and self.pi_lte_dongle.status_int == 3:
            self.up_devices += 1
        
        # Go through all the ping sensors at this site.
        for ping_sensor in all_probe_ping_sensors:
            # Check if this is a network-related ping sensor for this site.
            if GroupType.NETWORK_DEVICES.value in ping_sensor.device_group:
                self.name = ping_sensor.device_group
                device_name_lower = ping_sensor.device_name.lower()
                
                # Add this network ping sensor to its corresponding device for this group.
                if 'meraki' in device_name_lower:
                    self.meraki_device = ping_sensor
                elif 'router' in device_name_lower:
                    self.router = ping_sensor
                elif 'pdu' in device_name_lower:
                    self.pdu = ping_sensor
                elif 'vitupay' in device_name_lower:
                    self.vitupay_com = ping_sensor
                elif 'pi' in device_name_lower:
                    self.pi_device = ping_sensor
                elif 'd.clover.com' in device_name_lower:
                    self.clover_com = ping_sensor
                else:
                    logger.warning(f"An unusual network device's ping sensor was detected at site {self.name}")
                    logger.warning(f'Name: {device_name_lower} | Object: {ping_sensor}')
                    continue
                
                # Check the status of this network device.
                # Check if this device is up.
                if ping_sensor.status_int == 3:
                    self.up_devices += 1
                # Check if this device is in a warning or niche state.
                elif ping_sensor.status_int in [2, 4, 6, 10, 11, 14]:
                    self.warning_devices += 1
                # Check if this device is paused.
                elif ping_sensor.status_int in [7, 8, 9, 12]:
                    self.paused_devices += 1
                # This device must be down.
                else:
                    self.down_devices += 1
        
        # Determine the overall status of this group.
        # Check if all devices are up.
        if self.up_devices == 7:
            self.overall_status = OverallStatus.HEALTHY
        # Check if 1 or more devices are in some sort of non-online state.
        elif self.up_devices == 6 or self.warning_devices > (self.up_devices + self.paused_devices + self.down_devices):
            self.overall_status = OverallStatus.DEGRADED
        # Check if most devices are paused.
        elif self.paused_devices > (self.up_devices + self.warning_devices + self.down_devices):
            self.overall_status = OverallStatus.PAUSED
        # Check if 2 or more devices are in some sort of non-online state.
        elif self.up_devices <= 5:
            self.overall_status = OverallStatus.CRITICAL
        # Something strange is happening...
        else:
            self.overall_status = OverallStatus.UNKNOWN
         
    def generate_slack_message_section_json(self) -> dict:
        """
        Generate the JSON-formatted dictionary that is compatible with Slack's
        message conventions of this object's properties and overall status.

        Returns:
            dict: The JSON-formatted Slack message payload of this object's
                properties and overall status.
        """
        
        slack_message_json = {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Overall Status:*\n{self.overall_status.value}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Meraki:*\n{PRTG_STATUS_MAP[0] if self.meraki_device is None else self.meraki_device.status}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Router:*\n{PRTG_STATUS_MAP[0] if self.router is None else self.router.status}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*PDU:*\n{PRTG_STATUS_MAP[0] if self.pdu is None else self.pdu.status}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*vitupay . com:*\n{PRTG_STATUS_MAP[0] if self.vitupay_com is None else self.vitupay_com.status}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*d . clover . com:*\n{PRTG_STATUS_MAP[0] if self.clover_com is None else self.clover_com.status}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Pi:*\n{PRTG_STATUS_MAP[0] if self.pi_device is None else self.pi_device.status}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Pi LTE Dongle:*\n{PRTG_STATUS_MAP[0] if self.pi_lte_dongle is None else self.pi_lte_dongle.status}"
                }
            ]
        }
        
        return slack_message_json
    

class CloverDevicesGroup:
    """
    Represents the Clover devices group for a site. Includes the ping sensors
    for each Clover device in the group along with the name, overall status,
    and a count of each type of status.

    Members:
        name (str): The name of the Clover devices group.
        overall_status (OverallStatus): The overall status of the Clovers.
        up_clovers (int): The number of Clover devices that are online.
        warning_clovers (int): The number of Clover devices that are in some
            sort of warning / niche state.
        paused_clovers (int): The number of Clover devices that are paused.
        down_clovers (int): The number of Clover devices that are down.
        total_clovers (int): The total number of Clovers at this site.
    """
    
    name: str
    overall_status: OverallStatus
    up_clovers: int = 0
    warning_clovers: int = 0
    paused_clovers: int = 0
    down_clovers: int = 0
    total_clovers: int = 0
    
    def __init__(self, all_probe_ping_sensors: list[PRTGSensor]):
        """
        Initializes a Clover devices group object. Stores information
        regarding the overall status of the Clover devices for this site.

        Args:
            all_probe_ping_sensors (list[PRTGSensor]): List of ping PRTGSensors
                associated with each Clover with the probe.
        """
        
        # Go through all the ping sensors at this site.
        for ping_sensor in all_probe_ping_sensors:
            # Check if this is a Clover ping sensor for this site.
            if GroupType.CLOVER_DEVICES.value in ping_sensor.device_group:
                self.name = ping_sensor.device_group
                
                # Check the status of this Clover device.
                # Check if this Clover is up.
                if ping_sensor.status_int == 3:
                    self.up_clovers += 1
                # Check if this Clover is in a warning / some sort of niche state.
                elif ping_sensor.status_int in [2, 4, 6, 10, 11, 14]:
                    self.warning_clovers += 1
                # Check if this Clover is paused.
                elif ping_sensor.status_int in [7, 8, 9, 12]:
                    self.paused_clovers += 1
                # This Clover must be down.
                else:
                    self.down_clovers += 1
                
                self.total_clovers += 1
        
        # Determine the overall status of the Clover devices group.
        percent_of_online_clovers = (self.up_clovers / self.total_clovers) * 100
        
        # Check if at least 90% of the Clovers are up.
        if percent_of_online_clovers >= 90:
            self.overall_status = OverallStatus.HEALTHY
        # Check if at least 80% of the Clovers are up or most of the Clovers 
        # are in some sort of warning / niche state.
        elif percent_of_online_clovers >= 80 or self.warning_clovers > (self.up_clovers + self.down_clovers + self.paused_clovers):
            self.overall_status = OverallStatus.DEGRADED
        # Check if most of the Clovers are paused.
        elif self.paused_clovers > (self.up_clovers + self.down_clovers + self.warning_clovers):
            self.overall_status = OverallStatus.PAUSED
        # Check if less than 80% of the Clovers are up.
        elif percent_of_online_clovers < 80:
            self.overall_status = OverallStatus.CRITICAL
        # Something strange is going on...
        else:
            self.overall_status = OverallStatus.UNKNOWN
    
    def generate_slack_message_section_json(self) -> dict:
        """
        Generate the JSON-formatted dictionary that is compatible with Slack's
        message conventions of this object's properties and overall status.

        Returns:
            dict: The JSON-formatted Slack message payload of this object's
                properties and overall status.
        """
        
        slack_message_json = {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Overall Status:*\n{self.overall_status.value}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Clovers Online:*\n{self.up_clovers} / {self.total_clovers}"
                }
            ]
        }
        
        return slack_message_json


# ================================= Functions =================================
def get_probe_health_sensor(site_id: str) -> PRTGSensor:
    """
    Gets the status of the probe health sensor from PRTG and returns the 
    information as a PRTG sensor object.

    Args:
        site_id (str): The 3-digit site ID that the probe is associated with.

    Raises:
        ValueError: The site ID was not found in PRTG.

    Returns:
        PRTGSensor: The probe health sensor for the site.
    """
    
    # Get the status of this site's probe health sensor.
    site_probe_health_sensor_response = requests.get(
        url=PRTG_TABLE_URL,
        params={
            'content': 'sensors',
            'columns': 'name,device,group,probe,status',
            'filter_probe': f'@sub({site_id})',
            'filter_name': PRTG_PROBE_HEALTH_NAME,
            'sortby': 'device',
            'output': 'json',
            'count': '2',
            'apitoken': PRTG_API_KEY
        }
    )
    site_probe_health_sensor_json = site_probe_health_sensor_response.json()
    
    # Check if we could not find the site's probe health sensor.
    if len(site_probe_health_sensor_json['sensors']) == 0:
        raise ValueError(f'Probe does not exist with site ID: {site_id}')

    # Make the sensor object and return it.
    site_probe_health_sensor = site_probe_health_sensor_json['sensors'][0]
    site_probe_health_status_int = site_probe_health_sensor['status_raw']
    
    return PRTGSensor(
        site_probe_health_sensor['device'], 
        site_probe_health_sensor['group'], 
        PRTG_STATUS_MAP[site_probe_health_status_int], 
        site_probe_health_status_int
    )


async def get_probe_health_sensor_async(site_id: str) -> PRTGSensor:
    return await asyncio.to_thread(get_probe_health_sensor, site_id)


def get_site_ping_sensors(site_id: str) -> list[PRTGSensor]:
    """
    Gets the status of all the ping sensors at a site from PRTG and returns the 
    information as a list of PRTG sensor objects.

    Args:
        site_id (str): The site ID that the ping sensors are associated with.

    Raises:
        ValueError: The site ID was not found in PRTG.

    Returns:
        list[PRTGSensor]: All ping sensors at the site.
    """
    
    # Get all the device's statuses via their ping sensor's status at this site.
    site_ping_sensors_response = requests.get(
        url=PRTG_TABLE_URL,
        params={
            'content': 'sensors',
            'columns': 'name,device,group,probe,status,parentid',
            'filter_probe': f'@sub({site_id})',
            'filter_name': PRTG_PING_NAME,
            'sortby': 'device',
            'output': 'json',
            'count': PRTG_API_RESPONSE_LIMIT,
            'apitoken': PRTG_API_KEY
        }
    )
    site_ping_sensors_json = site_ping_sensors_response.json()
    site_ping_sensors = site_ping_sensors_json['sensors']
    
    # Check if there were no sensors returned.
    if len(site_ping_sensors) == 0:
        raise ValueError(f'No ping sensors were found at site {site_id}')

    # Convert the raw response to a list of PRTGSensor objects.
    site_devices = list[PRTGSensor]()
    for site_ping_sensor in site_ping_sensors:
        site_devices.append(
            PRTGSensor(
                site_ping_sensor['device'],
                site_ping_sensor['group'],
                PRTG_STATUS_MAP[site_ping_sensor['status_raw']],
                site_ping_sensor['status_raw']
            )
        )
    
    # Return the site's ping sensors.
    return site_devices


async def get_site_ping_sensors_async(site_id: str) -> list[PRTGSensor]:
    return await asyncio.to_thread(get_site_ping_sensors, site_id)


def get_site_pi_lte_dongle_sensor(site_id: str) -> PRTGSensor:
    """
    Gets the status of the LTE dongle plugged into the Raspberry Pi from PRTG
    and returns the information as a PRTG sensor object.

    Args:
        site_id (str): The 3-digit site ID that the probe is associated with.

    Raises:
        ValueError: The site ID was not found in PRTG.

    Returns:
        PRTGSensor: The pi LTE dongle sensor for the site.
    """
    
    # Get the status of this site's pi LTE dongle from PRTG.
    site_pi_lte_dongle_response = requests.get(
        url=PRTG_TABLE_URL,
        params={
            'content': 'sensors',
            'columns': 'name,device,group,status',
            'filter_group': PRTG_PI_LTE_DONGLE_GROUP,
            'filter_device': f'@sub({site_id})',
            'filter_name': PRTG_PING_NAME,
            'output': 'json',
            'count': '2',
            'apitoken': PRTG_API_KEY
        }
    )
    site_pi_lte_dongle_json = site_pi_lte_dongle_response.json()
    
    # Check if we could not find the site's pi LTE dongle.
    if len(site_pi_lte_dongle_json['sensors']) == 0:
        raise ValueError(f'Pi LTE dongle sensor not found at site {site_id}')

    # Make the sensor object and return it.
    site_pi_lte_dongle_sensor = site_pi_lte_dongle_json['sensors'][0]
    site_pi_lte_dongle_status_int = site_pi_lte_dongle_sensor['status_raw']
    
    return PRTGSensor(
        site_pi_lte_dongle_sensor['device'], 
        site_pi_lte_dongle_sensor['group'], 
        PRTG_STATUS_MAP[site_pi_lte_dongle_status_int], 
        site_pi_lte_dongle_status_int
    )


async def get_site_pi_lte_dongle_sensor_async(site_id: str) -> PRTGSensor:
    return await asyncio.to_thread(get_site_pi_lte_dongle_sensor, site_id)


def get_site_primary_interface_sensor(site_id: str) -> PRTGSensor:
    """
    Gets the status of the primary interface sensor from PRTG and returns the
    information as a PRTG sensor object.

    Args:
        site_id (str): The 3-digit site ID that the probe is associated with.

    Raises:
        ValueError: The site ID was not found in PRTG.

    Returns:
        PRTGSensor: The primary interface sensor for the site.
    """
    
    # Get the "Primary Interface" sensor for this site to see if it has failed over.
    site_primary_interface_response = requests.get(
        url=PRTG_TABLE_URL,
        params={
            'content': 'sensors',
            'columns': 'name,status,probe,group,device',
            'filter_probe': f'@sub({site_id})',
            'filter_name': PRTG_PRIMARY_INTERFACE_NAME,
            'output': 'json',
            'count': '2',
            'apitoken': PRTG_API_KEY
        }
    )
    site_primary_interface_json = site_primary_interface_response.json()
    
    # Check if we could not find the site's primary interface sensor.
    if len(site_primary_interface_json['sensors']) == 0:
        raise ValueError(f'Primary interface sensor not found at site {site_id}')
    
    # Make the sensor object and return it.
    site_primary_interface_sensor = site_primary_interface_json['sensors'][0]
    site_primary_interface_status_int = site_primary_interface_sensor['status_raw']
    
    return PRTGSensor(
        site_primary_interface_sensor['device'],
        site_primary_interface_sensor['group'],
        PRTG_STATUS_MAP[site_primary_interface_status_int],
        site_primary_interface_status_int
    )
    

async def get_site_primary_interface_sensor_async(site_id: str) -> PRTGSensor:
    return await asyncio.to_thread(get_site_primary_interface_sensor, site_id)


def normalize_overall_site_status(probe_device: ProbeDevice, network_devices: NetworkDevicesGroup, clover_devices: CloverDevicesGroup) -> None:
    """
    Using the status of the provided probe device, network device group, and
    Clover device group, find the true overall status of a site. The aim is
    to set the overall status of the probe to a degraded or critical status
    depending on the context of the other components of the site.

    Args:
        probe_device (ProbeDevice): The probe device to set the status for.
        network_devices (NetworkDevicesGroup): The network devices group.
        clover_devices (CloverDevicesGroup): The Clover devices group.
    """
    
    # Normalize the overall status of the site based off the overall statuses
    # of the network and Clover devices.
    if probe_device.overall_status is OverallStatus.HEALTHY:
        # When the probe is healthy, but ANYTHING else is critical, the site is critical.
        if network_devices.overall_status is OverallStatus.CRITICAL or clover_devices.overall_status is OverallStatus.CRITICAL:
            probe_device.overall_status = OverallStatus.CRITICAL
        # When the probe is healthy, but ANYTHING else is degraded, the site is degraded.
        elif network_devices.overall_status is OverallStatus.DEGRADED or clover_devices.overall_status is OverallStatus.DEGRADED:
            probe_device.overall_status = OverallStatus.DEGRADED
        # When the probe is healthy and BOTH the network devices group AND the Clover devices group are paused, the site is paused.
        elif network_devices.overall_status is OverallStatus.PAUSED and clover_devices.overall_status is OverallStatus.PAUSED:
            probe_device.overall_status = OverallStatus.PAUSED
    elif probe_device.overall_status is OverallStatus.DEGRADED:
        # When the probe is degraded and BOTH the network devices group AND the Clover devices group are paused, the site is paused.
        if network_devices.overall_status is OverallStatus.PAUSED and clover_devices.overall_status is OverallStatus.PAUSED:
            probe_device.overall_status = OverallStatus.PAUSED
        # When the probe is degraded, but ANYTHING else is degraded OR critical, the site is critical.
        elif network_devices.overall_status is OverallStatus.CRITICAL or network_devices.overall_status is OverallStatus.DEGRADED or \
             clover_devices.overall_status is OverallStatus.CRITICAL or clover_devices.overall_status is OverallStatus.DEGRADED:
                probe_device.overall_status = OverallStatus.CRITICAL


def format_output(probe_device: ProbeDevice, network_devices_group: NetworkDevicesGroup, clover_devices_group: CloverDevicesGroup) -> dict[list]:
    """
    Formats the output of the Slack message. Makes the output look
    sophisticated and pretty to convey the overall status effectively.

    Args:
        probe_device (ProbeDevice): The probe device.
        network_devices_group (NetworkDevicesGroup): The network devices group.
        clover_devices_group (CloverDevicesGroup): The Clover devices group.

    Returns:
        dict[list]: The JSON-formatted dictionary object for the Slack API.
    """
    
    # Create the returning JSON-formatted dictionary object.
    slack_message_json = {"blocks": []}
    
    # Check for the existence of the probe device.
    if not probe_device:
        slack_message_json["blocks"].append(
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Error: No Probe found. Please check the site ID is correct.",
                    "emoji": True
                }
            }
        )
        return slack_message_json
    else:
        slack_message_json["blocks"].append(
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{probe_device.probe_health_sensor.device_group} Site Status",
                    "emoji": True
                }
            }
        )
        slack_message_json["blocks"].append(probe_device.generate_slack_message_section_json())
    
    slack_message_json["blocks"].append(
        {
            "type": "divider"
        }
    )
    
    # Check for the existence of the network devices group.
    if not network_devices_group:
        slack_message_json["blocks"].append(
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "No network devices found for this probe",
                    "emoji": True
                }
            }
        )
    else:
        slack_message_json["blocks"].append(
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{network_devices_group.name} Status",
                    "emoji": True
                }
            }
        )
        slack_message_json["blocks"].append(network_devices_group.generate_slack_message_section_json())
    
    slack_message_json["blocks"].append(
        {
            "type": "divider"
        }
    )
    
    # Check for the existence of the Clover devices group.
    if not clover_devices_group:
        slack_message_json["blocks"].append(
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "No Clover devices found for this probe",
                    "emoji": True
                }
            }
        )
    else:
        slack_message_json["blocks"].append(
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{clover_devices_group.name} Status",
                    "emoji": True
                }
            }
        )
        slack_message_json["blocks"].append(clover_devices_group.generate_slack_message_section_json())
    
    return slack_message_json


def is_valid_argument(arguments: list[str]) -> bool:
    """
    Validates the arguments to this command. This should be a list of each
    discrete string that the user used to tag and engage with the bot with
    the intentions of running a command.

    Args:
        arguments (list[str]): A list of arguments for this command. This will
            typically look like: ["@vitubot", "status", "{site ID}"]

    Returns:
        bool: True if the arguments are non-null, have the proper number of
            arguments, and the site ID provided is a 3-digit string. False
            otherwise.
    """
    
    # Check if the arguments are None.
    if arguments is None:
        error_message = 'Invalid arguments provided'
        logger.error(error_message)
        slack.send_error(error_message)
        return False
    
    # Check if there are an incorrect number of arguments.
    if len(arguments) > VALID_ARGUMENT_COUNT:
        error_message = f'Too many arguments - expecting {VALID_ARGUMENT_COUNT} but got {len(arguments)}'
        logger.error(error_message)
        slack.send_error(error_message)
        return False
    elif len(arguments) < VALID_ARGUMENT_COUNT:
        error_message = F'Too few arguments - expecting {VALID_ARGUMENT_COUNT}, but got {len(arguments)}'
        logger.error(error_message)
        slack.send_error(error_message)
        return False
    
    # Verify the format of the site's ID.
    site_id = arguments[2].strip()
    if not SITE_ID_REGEX.match(site_id):
        error_message = 'Invalid site ID - Must be a valid 3-digit ID'
        logger.error(error_message)
        slack.send_error(error_message)
        return False
    
    return True


async def execute(arguments: list[str]) -> None:
    """
    Executes the status command. It will output the overall status of the site
    along with statuses of the probe device, each network device, the number of
    online Clover devices, and the failover status.

    Args:
        arguments (list[str]): The arguments to the command. This will
            typically look like: ["@vitubot", "status", "{site ID}"]
    """
    
    # Validate the arguments.
    if not is_valid_argument(arguments):
        return

    # Extract the site's ID from the arguments.
    site_id = arguments[2].strip()

    # Gather all the sensors. Send an error message to Slack if something goes
    # wrong.
    try:
        site_probe_health_sensor, \
        site_ping_sensors, \
        site_pi_lte_dongle_sensor, \
        site_primary_interface_sensor = await asyncio.gather(
            get_probe_health_sensor_async(site_id),
            get_site_ping_sensors_async(site_id),
            get_site_pi_lte_dongle_sensor_async(site_id),
            get_site_primary_interface_sensor_async(site_id)
        )
        
        # Get the probe device's health sensor. This will also tell us if the
        # probe exists with the provided site ID.
        # site_probe_health_sensor = await get_probe_health_sensor(site_id)
        
        # Get all ping sensors for the devices at the site. This includes
        # network devices and Clover devices.
        # site_ping_sensors = await get_site_ping_sensors(site_id)
        
        # Get the sensor for the LTE dongle plugged into the site's Raspberry Pi.
        # site_pi_lte_dongle_sensor = await get_site_pi_lte_dongle_sensor(site_id)
        
        # Get the sensor for the site's ISP connection.
        # site_primary_interface_sensor = await get_site_primary_interface_sensor(site_id)
    except requests.RequestException as error:
        error_message = f'An unexpected request error occurred: {error}'
        logger.error(error_message)
        slack.send_error(error_message)
        return
    except requests.ConnectionError as error:
        error_message = f'A connection could not be established to PRTG: {error}'
        logger.error(error_message)
        slack.send_error(error_message)
        return
    except requests.HTTPError as error:
        error_message = f'An HTTP error occurred: {error}'
        logger.error(error_message)
        slack.send_error(error_message)
        return
    except requests.Timeout as error:
        error_message = f'The request to PRTG took too long: {error}'
        logger.error(error_message)
        slack.send_error(error_message)
        return
    except ValueError as error:
        logger.error(error)
        slack.send_error(error)
        return
    except Exception as error:
        error_message = f'An unknown error occurred: {error}'
        logger.error(error_message)
        slack.send_error(error_message)
        return
    
    # Organize the sensors to determine overall status for each group.
    site_probe_device = ProbeDevice(site_probe_health_sensor, site_primary_interface_sensor)
    site_network_devices_group = NetworkDevicesGroup(site_ping_sensors, site_pi_lte_dongle_sensor)
    site_clover_devices_group = CloverDevicesGroup(site_ping_sensors)
    
    # Adjust the overall status of the site based on the collective statuses.
    normalize_overall_site_status(site_probe_device, site_network_devices_group, site_clover_devices_group)
    
    # Format the site's status as a payload for the Slack API.
    site_status_payload = format_output(site_probe_device, site_network_devices_group, site_clover_devices_group)

    # Send the site's status to Slack.
    slack.send_message(site_status_payload)
