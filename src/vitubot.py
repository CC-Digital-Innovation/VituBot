from enum import Enum
import os
import secrets

import commands.help_command as help_command
import commands.status_command as status_command
import commands.wifi_command as wifi_command
import slack

from dotenv import load_dotenv
from fastapi import Depends
from fastapi import FastAPI, HTTPException, status
from fastapi.security import APIKeyHeader
from loguru import logger


# ====================== Environment / Global Variables =======================
load_dotenv(override=True)

# Initialize the app's constant global variables.
VITUBOT_API_KEY = os.getenv('VITUBOT_API_KEY')
VITUBOT_API_KEY_HEADER = APIKeyHeader(name='API-Key')
VITUBOT_APP = FastAPI()
VITUBOT_SUCCESSFUL_RESPONSE = {
    'status_code': 200,
    'details': 'Command successful'
}


# =================================== Enums ===================================
class VituBotCommand(Enum):
    """
    Represents valid VituBot commands.
    """
    
    HELP = 'help'
    STATUS = 'status'
    WIFI = 'wifi'


# ================================= Functions =================================
def authorize(provided_api_key: str = Depends(VITUBOT_API_KEY_HEADER)):
    """
    Authorizes the provided API key. Raises an HTTP Exception if it does not 
    match this bot's API key.

    Args:
        provided_api_key (str): The API key to authorize.

    Raises:
        HTTPException: Raised when the provided API key does not match this
            bot's API key.
    """
    
    # Check if the provided API key is correct.
    if not secrets.compare_digest(provided_api_key, VITUBOT_API_KEY):
        # Unauthorized access. API key was incorrect.
        logger.error('Invalid API key received')
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid API key'
        )


def is_valid_payload(payload: dict) -> bool:
    """
    Validates the provided payload by checking if it is non-null, contains
    expected keys, and has a valid token.

    Args:
        payload (dict): The payload to validate.

    Returns:
        bool: True if the payload is non-null, contains the "type" and "token"
            keys, and the type / token are valid. Otherwise, returns false.
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
    
    # Check if the token is valid.
    if not slack.is_valid_event_callback_token(payload.get('token')):
        logger.error(f'{error_message_intro} Invalid event token')
        return False
    
    return True
        

# ================================= Endpoints =================================
@VITUBOT_APP.post('/vitubot/slack/event', dependencies=[Depends(authorize)])
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
    
    # Validate the payload received.
    if not is_valid_payload(payload):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid payload received'
        )
        
    # Check for a URL verification payload with a challenge string.
    if payload['type'] == slack.EventType.URL_VERIFICATION.value:
        logger.info('Slack challenge received. Sending back the challenge...')
        
        slack_outer_payload = slack.URLVerificationPayload(**payload)
        return {
            "challenge": slack_outer_payload.challenge
        }
    
    # Check for unknown / unsupported Slack event type.
    if payload['type'] != slack.EventType.APP_MENTION.value:
        logger.error('An unsupported Slack event type was received')
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Unsupported event type received'
        )
    
    # Respond to the Slack channel to acknowledge that we are processing their request.
    logger.info('Sending acknowledgement message to Slack...')
    slack.send_ack()
    
    # Extract the command from the Slack payload.
    vitubot_command = slack.EventCallback(**payload)
    command_args = vitubot_command.event.text.split(' ')
    
    logger.info(f'Received command: {command_args}')
    
    # Check if the bot was tagged with no command.
    if len(command_args) == 1:
        logger.info('Executing "help" command')
        
        help_command.execute()
        return VITUBOT_SUCCESSFUL_RESPONSE
    
    # Send the command to the proper function. Otherwise, send the help command.
    match command_args[1].lower():
        case VituBotCommand.WIFI.value:
            logger.info('Executing "wifi" command')
            wifi_command.execute(command_args)
        case VituBotCommand.STATUS.value:
            logger.info('Executing "status" command')
            status_command.execute(command_args)
        case VituBotCommand.HELP.value:
            logger.info('Executing "help" command')
            help_command.execute()
        case _:
            logger.info('An unknown command was provided. Executing "help" command')
            help_command.execute()
            
    return VITUBOT_SUCCESSFUL_RESPONSE


if __name__ == '__main__':
    vitubot(
        {
            "type": "app_mention",
            "token": "string",
            "team_id": "string",
            "api_app_id": "string",
            "event": {
                "type": "app_mention",
                "event_ts": "string",
                "user": "string",
                "ts": "string",
                "text": "@vitubot status example",
                "channel": "string"
            },
            "event_context": "string",
            "event_id": "string",
            "event_time": 0,
            "authorizations": [
                {}
            ],
            "is_ext_shared_channel": True,
            "context_team_id": "string",
            "context_enterprise_id": "string"
        }          
    )
