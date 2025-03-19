from enum import Enum
import os
import secrets

import commands.clovers as clovers_command
import commands.help as help_command
import commands.status as status_command
import commands.wifi as wifi_command
import services.slack as constants

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, status
from loguru import logger


# ====================== Environment / Global Variables =======================
load_dotenv(override=True)

# Initialize the app's constant global variables.
app = FastAPI()

VITUBOT_SLACK_APP_TOKEN = os.getenv('SLACK_APP_TOKEN')
VITUBOT_END_STRING = \
    '===================================== END ======================================'


# =================================== Enums ===================================
class VituBotCommand(Enum):
    """
    Represents valid VituBot commands.
    """
    
    CLOVERS = 'clovers'
    HELP = 'help'
    STATUS = 'status'
    WIFI = 'wifi'


# ================================= Functions =================================
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


async def execute_vitubot_task(payload: dict) -> None:
    """
    Executes a VituBot command based off the provided payload. Sends an
    acknowledgement message to Slack so the user knows we have received their
    request. It will then determine the command received from the payload and
    send the arguments to the corresponding command. If an unknown command is
    received or the bot was simply tagged with no command we will return the
    output of the "help" command.

    Args:
        payload (dict): The Slack payload to extract a command from.
    """
    
    # Respond to the Slack channel to acknowledge that we are processing their request.
    logger.info('Sending acknowledgement message to Slack...')
    constants.send_ack()
    
    # Extract the command from the Slack payload.
    vitubot_command = constants.EventCallback(**payload)
    command_args = vitubot_command.event.text.split()
    
    logger.info(f'Received command: {command_args}')
    
    # Check if the bot was tagged with no command.
    if len(command_args) == 1:
        logger.info(f'Bot was tagged with no command. Executing "{VituBotCommand.HELP.value}" command')
        help_command.execute()
        logger.info(VITUBOT_END_STRING)
        return
    
    # Send the command to the proper function. Otherwise, send the help command.
    command = command_args[1].lower()
    match command:
        case VituBotCommand.CLOVERS.value:
            logger.info(f'Executing "{VituBotCommand.CLOVERS.value}" command')
            clovers_command.execute(command_args)
        case VituBotCommand.HELP.value:
            logger.info(f'Executing "{VituBotCommand.HELP.value}" command')
            help_command.execute()
        case VituBotCommand.STATUS.value:
            logger.info(f'Executing "{VituBotCommand.STATUS.value}" command')
            await status_command.execute(command_args)
        case VituBotCommand.WIFI.value:
            logger.info(f'Executing "{VituBotCommand.WIFI.value}" command')
            wifi_command.execute(command_args)
        case _:
            logger.warning(f'An unknown command was provided: "{command}". Executing "{VituBotCommand.HELP.value}" command')
            help_command.execute()
    
    logger.info(VITUBOT_END_STRING)


# ================================= Endpoints =================================
@app.post('/slack/event', status_code=status.HTTP_200_OK)
async def vitubot(payload: dict, background_tasks: BackgroundTasks):
    """
    The main endpoint for the VituBot. This function will authorize and
    validate the payload before sending the payload to the execute function.
    It will also send back a challenge token if prompted by the Slack API. This
    function is designed to send back a response to the Slack API ASAP as per
    the 3-second requirement. This endpoint is triggered whenever this bot is
    tagged in Slack.

    Args:
        payload (dict): The Slack payload to extract a command from.

    Raises:
        HTTPException (400): An invalid payload was received or an unsupported
            event type was received.
        HTTPException (401): An invalid token was received.

    Returns:
        dict: The HTTP response to send back to Slack. If a URL verification    
            event is received, the challenge string from the payload will be
            returned.
    """
    logger.info('============================== VituBot Triggered ===============================')
    
    # Validate the payload received.
    if not is_valid_payload(payload):
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
    if payload['type'] == constants.EventType.URL_VERIFICATION.value:
        logger.info('Slack challenge received. Sending back the challenge...')
        slack_outer_payload = constants.URLVerificationPayload(**payload)
        logger.info(VITUBOT_END_STRING)
        return {
            "challenge": slack_outer_payload.challenge
        }
    
    # Check for unknown / unsupported Slack event type.
    if payload['type'] != constants.EventType.EVENT_CALLBACK.value:
        logger.error('An unsupported Slack event type was received')
        logger.info(VITUBOT_END_STRING)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Unsupported event type received'
        )
    
    background_tasks.add_task(execute_vitubot_task, payload)
