import asyncio
from enum import Enum

import requests
from loguru import logger

import services.constants as constants
import services.prtg as prtg_service
import services.slack as slack_service


# ====================== Environment / Global Variables =======================
VALID_ARGUMENT_COUNT = 3


# =================================== Enums ===================================
class OverallStatus(Enum):
    """
    Represents the different overall statuses with associated emoji strings.
    """
    
    HEALTHY = f'{constants.SlackEmojiCodes.GREEN_CIRCLE.value} Healthy'
    DEGRADED = f'{constants.SlackEmojiCodes.YELLOW_CIRCLE.value} Degraded'
    CRITICAL = f'{constants.SlackEmojiCodes.RED_CIRCLE.value} CRITICAL'
    PAUSED = f'{constants.SlackEmojiCodes.PAUSE_BUTTON.value} Paused'
    UNKNOWN = f'{constants.SlackEmojiCodes.GRAY_QUESTION_MARK.value} Unknown'


# ================================== Classes ==================================
class ProbeDeviceStatus:
    """
    Represents a probe device's status and its properties / associated sensors.

    Members:
        probe_health_sensor (prtg_service.Sensor): The sensor that checks on the probe's
            health.
        primary_interface_sensor (prtg_service.Sensor): The sensor that checks whether
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
    
    probe_health_sensor: prtg_service.Sensor
    primary_interface_sensor: prtg_service.Sensor
    primary_interface_description: str
    is_lte_only: bool
    overall_status: OverallStatus
    
    def __init__(self, probe_health_sensor: prtg_service.Sensor, primary_interface_sensor: prtg_service.Sensor):
        """
        Initializes a probe device with its properties and sensors.

        Args:
            probe_health_sensor (prtg_service.Sensor): The sensor that checks on the
                probe's health.
            primary_interface_sensor (prtg_service.Sensor): The sensor that checks
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


class NetworkGroupStatus:
    """
    Represents the network group status for a site. Includes the ping sensors
    for each network device in the group along with the name, overall status,
    and a count of each type of status.

    Members:
        name (str): The name of the network devices group.
        overall_status (OverallStatus): The overall status of the site.
        pi_lte_dongle (prtg_service.Sensor): The ping sensor for the LTE dongle that is
            connected to the site's Raspberry Pi.
        meraki_device (prtg_service.Sensor): The ping sensor for the Meraki wireless
            access point. Connects the Clovers to the internet.
        router (prtg_service.Sensor): The ping sensor for the Cradlepoint router.
            Supplies internet to all the network devices (NOT the Clovers).
        pdu (prtg_service.Sensor): The ping sensor for the PDU that powers all the
            networking equipment.
        vitupay_com (prtg_service.Sensor): The ping sensor for the connection to
            api.ca.vitupay.com.
        pi_device (prtg_service.Sensor): The ping sensor for the Raspberry Pi.
        clover_com (prtg_service.Sensor): The ping sensor for the connection to
            d.clover.com.
        up_devices (int): The number of network devices that are online.
        warning_devices (int): The number of network devices that are in some
            sort of warning / niche state.
        paused_devices (int): The number of network devices that are paused.
        down_devices (int): The number of network devices that are down.
    """
    
    name: str
    overall_status: OverallStatus
    pi_lte_dongle: prtg_service.Sensor = None
    meraki_device: prtg_service.Sensor = None
    router: prtg_service.Sensor = None
    pdu: prtg_service.Sensor = None
    vitupay_com: prtg_service.Sensor = None
    pi_device: prtg_service.Sensor = None
    clover_com: prtg_service.Sensor = None
    up_devices: int = 0
    warning_devices: int = 0
    paused_devices: int = 0
    down_devices: int = 0

    def __init__(self, all_probe_ping_sensors: list[prtg_service.Sensor], site_pi_lte_dongle_sensor: prtg_service.Sensor):
        """
        Initializes a network devices group object. Stores information
        regarding the status of all the network devices for this site.

        Args:
            all_probe_ping_sensors (list[prtg_service.Sensor]): List of ping prtg_service.Sensors
                associated with all devices with the probe.
            site_pi_lte_dongle_sensor (prtg_service.Sensor): The ping prtg_service.Sensor of the 
                site's LTE dongle plugged into the Raspberry Pi.
        """
        
        # Add the Pi LTE dongle to this group and check if it is online.
        self.pi_lte_dongle = site_pi_lte_dongle_sensor
        if self.pi_lte_dongle is not None and self.pi_lte_dongle.status_int == 3:
            self.up_devices += 1
        
        # Go through all the ping sensors at this site.
        for ping_sensor in all_probe_ping_sensors:
            # Check if this is a network-related ping sensor for this site.
            if prtg_service.GroupType.NETWORK_DEVICES.value in ping_sensor.device_group:
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
                    "text": f"*Meraki:*\n{prtg_service.STATUS_MAP[0] if self.meraki_device is None else self.meraki_device.status}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Router:*\n{prtg_service.STATUS_MAP[0] if self.router is None else self.router.status}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*PDU:*\n{prtg_service.STATUS_MAP[0] if self.pdu is None else self.pdu.status}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*vitupay . com:*\n{prtg_service.STATUS_MAP[0] if self.vitupay_com is None else self.vitupay_com.status}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*d . clover . com:*\n{prtg_service.STATUS_MAP[0] if self.clover_com is None else self.clover_com.status}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Pi:*\n{prtg_service.STATUS_MAP[0] if self.pi_device is None else self.pi_device.status}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Pi LTE Dongle:*\n{prtg_service.STATUS_MAP[0] if self.pi_lte_dongle is None else self.pi_lte_dongle.status}"
                }
            ]
        }
        
        return slack_message_json
    

class CloverGroupStatus:
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
    
    def __init__(self, all_probe_ping_sensors: list[prtg_service.Sensor]):
        """
        Initializes a Clover devices group object. Stores information
        regarding the overall status of the Clover devices for this site.

        Args:
            all_probe_ping_sensors (list[prtg_service.Sensor]): List of ping prtg_service.Sensors
                associated with each Clover with the probe.
        """
        
        # Go through all the ping sensors at this site.
        for ping_sensor in all_probe_ping_sensors:
            # Check if this is a Clover ping sensor for this site.
            if prtg_service.GroupType.CLOVER_DEVICES.value in ping_sensor.device_group:
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
        
        # Check if there are Clovers at this site (typical of express sites).
        if self.total_clovers == 0:
            self.name = ""
            self.overall_status = OverallStatus.UNKNOWN
        else:
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


def normalize_overall_site_status(probe_device: ProbeDeviceStatus, network_devices: NetworkGroupStatus, clover_devices: CloverGroupStatus) -> None:
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


def format_output(probe_device: ProbeDeviceStatus, network_devices_group: NetworkGroupStatus, clover_devices_group: CloverGroupStatus) -> dict[list]:
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
                    "emoji": False
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
                    "emoji": False
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
                    "emoji": False
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
                    "emoji": False
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
    if not clover_devices_group or clover_devices_group.total_clovers == 0:
        slack_message_json["blocks"].append(
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "No Clover devices found for this probe",
                    "emoji": False
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
                    "emoji": False
                }
            }
        )
        slack_message_json["blocks"].append(clover_devices_group.generate_slack_message_section_json())
    
    return slack_message_json


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
        # Send the requests to the PRTG API asynchronously.
        site_ping_sensors, \
        site_probe_health_sensor, \
        site_primary_interface_sensor, \
        site_pi_lte_dongle_sensor = await asyncio.gather(
            prtg_service.get_all_pings_async(site_id),
            prtg_service.get_probe_health_async(site_id),
            prtg_service.get_primary_interface_async(site_id),
            prtg_service.get_pi_lte_dongle_async(site_id)
        )
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
    
    # Organize the sensors to determine overall status for each group.
    site_probe_device = ProbeDeviceStatus(site_probe_health_sensor, site_primary_interface_sensor)
    site_network_devices_group = NetworkGroupStatus(site_ping_sensors, site_pi_lte_dongle_sensor)
    site_clover_devices_group = CloverGroupStatus(site_ping_sensors)
    
    # Adjust the overall status of the site based on the collective statuses.
    normalize_overall_site_status(site_probe_device, site_network_devices_group, site_clover_devices_group)
    
    # Format the site's status as a payload for the Slack API.
    site_status_payload = format_output(site_probe_device, site_network_devices_group, site_clover_devices_group)

    # Send the site's status to Slack.
    slack_service.send_message(site_status_payload)
