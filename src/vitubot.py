from enum import Enum
import os
import secrets

import commands.help_command as help_command
import commands.status_command as status_command
import commands.wifi_command as wifi_command
import slack

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from loguru import logger


# ====================== Environment / Global Variables =======================
load_dotenv(override=True)

# Initialize the app's constant global variables.
VITUBOT_SLACK_APP_TOKEN = os.getenv('SLACK_APP_TOKEN')
VITUBOT_APP = FastAPI()
VITUBOT_SUCCESSFUL_RESPONSE = {
    'status_code': 200,
    'details': 'Command successful'
}
VITUBOT_END_STRING = \
    '===================================== END ======================================'


# =================================== Enums ===================================
class VituBotCommand(Enum):
    """
    Represents valid VituBot commands.
    """
    
    HELP = 'help'
    STATUS = 'status'
    WIFI = 'wifi'


# ================================= Functions =================================
def is_authorized(provided_api_key: str) -> bool:
    """
    Authorizes the provided API key.

    Args:
        provided_api_key (str): The API key to authorize.

    Raises:
        HTTPException: Raised when the provided API key does not match this
            bot's Slack app key.
    
    Returns:
        bool: True if the provided API key is valid, false otherwise.
    """
    
    # Check if the provided API key is correct.
    return secrets.compare_digest(provided_api_key, VITUBOT_SLACK_APP_TOKEN)
        

def is_valid_payload(payload: dict) -> bool:
    """
    Validates the provided payload by checking if it is non-null and contains
    the expected keys.

    Args:
        payload (dict): The payload to validate.

    Returns:
        bool: True if the payload is non-null and contains the "type" and
            "token" keys. Otherwise, returns false.
    """
    error_message_intro = 'Error while validating received payload:'
    
    # Check if the payload is None.
    if payload is None or len(payload) == 0:
        logger.error(f'{error_message_intro} invalid arguments provided')
        return False
    
    # Check if there is no "type" field.
    if not payload.get('type'):
        logger.error(f'{error_message_intro} "type" field is missing')
        return False
    
    # Check if the "token" field exists.
    if not payload.get('token'):
        logger.error(f'{error_message_intro} "token" field is missing')
        return False
    
    return True
        

# ================================= Endpoints =================================
@VITUBOT_APP.post('/vitubot/slack/event')
def vitubot(payload: dict):
    """
    Executes a VituBot command based off the provided payload. The payload will 
    be authorized and validated before we examine the payload for a bot 
    command. This payload comes from Slack and is triggered whenever this bot 
    is tagged.

    Args:
        payload (dict): The Slack payload to extract a command from.

    Raises:
        HTTPException: An invalid payload was received.
        HTTPException: An unsupported event type was received.

    Returns:
        dict: The HTTP response to send back to Slack. If a URL verification    
            event is received, the challenge string will be returned.
    """
    logger.info('============================== VituBot Triggered ===============================')
    
    # Validate the payload received.
    if not is_valid_payload(payload):
        slack.send_error('Invalid payload received')
        logger.info(VITUBOT_END_STRING)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid payload received'
        )
        
    # Authorize the payload.
    if not is_authorized(payload.get('token')):
        logger.error('Unauthorized payload received')
        logger.info(VITUBOT_END_STRING)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid token'
        )
        
    # Check for a URL verification payload with a challenge string.
    if payload['type'] == slack.EventType.URL_VERIFICATION.value:
        logger.info('Slack challenge received. Sending back the challenge...')
        slack_outer_payload = slack.URLVerificationPayload(**payload)
        logger.info(VITUBOT_END_STRING)
        return {
            "challenge": slack_outer_payload.challenge
        }
    
    # Check for unknown / unsupported Slack event type.
    if payload['type'] != slack.EventType.APP_MENTION.value:
        logger.error('An unsupported Slack event type was received')
        logger.info(VITUBOT_END_STRING)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Unsupported event type received'
        )
    
    # Respond to the Slack channel to acknowledge that we are processing their request.
    logger.info('Sending acknowledgement message to Slack...')
    slack.send_ack()
    
    # Extract the command from the Slack payload.
    vitubot_command = slack.EventCallback(**payload)
    command_args = vitubot_command.event.text.split()
    
    logger.info(f'Received command: {command_args}')
    
    # Check if the bot was tagged with no command.
    if len(command_args) == 1:
        logger.info(f'Bot was tagged with no command. Executing "{VituBotCommand.HELP.value}" command')
        help_command.execute()
        logger.info(VITUBOT_END_STRING)
        return VITUBOT_SUCCESSFUL_RESPONSE
    
    # Send the command to the proper function. Otherwise, send the help command.
    command = command_args[1].lower()
    match command:
        case VituBotCommand.WIFI.value:
            logger.info(f'Executing "{VituBotCommand.WIFI.value}" command')
            wifi_command.execute(command_args)
        case VituBotCommand.STATUS.value:
            logger.info(f'Executing "{VituBotCommand.STATUS.value}" command')
            status_command.execute(command_args)
        case VituBotCommand.HELP.value:
            logger.info(f'Executing "{VituBotCommand.HELP.value}" command')
            help_command.execute()
        case _:
            logger.warning(f'An unknown command was provided: "{command}". Executing "{VituBotCommand.HELP.value}" command')
            help_command.execute()
    
    logger.info(VITUBOT_END_STRING)
    return VITUBOT_SUCCESSFUL_RESPONSE
