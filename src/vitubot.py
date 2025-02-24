from enum import Enum
import os
import secrets

import commands.help_command as help_command
import commands.status_command as status_command
import commands.wifi_command as wifi_command
import slack

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
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
    HELP = 'help'
    STATUS = 'status'
    WIFI = 'wifi'


# ================================= Functions =================================
def authorize(provided_api_key: str = Depends(VITUBOT_API_KEY_HEADER)):
    # Check if the provided API key is correct.
    if not secrets.compare_digest(provided_api_key, VITUBOT_API_KEY):
        # Unauthorized access. API key was incorrect.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid API key'
        )


def validate(payload: dict) -> bool:
    # Check if the payload is None.
    if payload is None or len(payload) == 0:
        print('Invalid arguments provided')
        return False
    
    # Check if there is no "type" field.
    if not payload.get('type'):
        print('Type field is missing')
        return False
    
    return True
        

# ================================= Endpoints =================================
# @VITUBOT_APP.post('/vitubot/slack/event', dependencies=[Depends(authorize)])
def vitubot(payload: dict):
    # Validate the payload received.
    if not validate(payload):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid payload received'
        )
        
    # Check for a URL verification payload.
    if payload['type'] == slack.EventType.URL_VERIFICATION.value:
        slack_outer_payload = slack.URLVerificationPayload(**payload)
        
        return {
            "challenge": slack_outer_payload.challenge
        }
    
    # Check for unknown / unsupported payload type.
    if payload['type'] != slack.EventType.APP_MENTION.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid payload type received'
        )
    
    # Respond to the Slack channel to acknowledge that we are processing their request.
    slack.send_ack()
    
    # Extract the command from the Slack payload.
    vitubot_command = slack.OuterPayload(**payload)
    command_args = vitubot_command.event.text.split(' ')
    
    # Check if the bot was tagged with no command.
    if len(command_args) == 1:
        help_command.execute()
        return VITUBOT_SUCCESSFUL_RESPONSE
    
    # Send the command to the proper function. Otherwise, send the help command.
    match command_args[1].lower():
        case VituBotCommand.WIFI.value:
            wifi_command.execute(command_args)
        case VituBotCommand.STATUS.value:
            status_command.execute(command_args)
        case VituBotCommand.HELP.value:
            help_command.execute()
        case _:
            help_command.execute()
            
    return VITUBOT_SUCCESSFUL_RESPONSE


if __name__ == '__main__':
    # 537 - Alturas | 553 - Tulelake (LTE Only) | 633 - Reedley | 610 - Inglewood (Paused)
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
                "text": "@vitubot status nonsense",
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


"""
Request URL to verify with Slack API:
{
    "token":"Dj2CRRrzLPVVzqfIZNg38uOn",
    "challenge":"WNWkFnIpcufTz7TY4OfxDfadYY5v8BY8ZbaoHvCqNhnKhNgqtOex",
    "type":"url_verification"
}
"""

"""
example payload from slack:
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
    "text": "@vitubot wifi d4:95:24:73:f7:ab",
    "channel": "string"
  },
  "event_context": "string",
  "event_id": "string",
  "event_time": 0,
  "authorizations": [
    {}
  ],
  "is_ext_shared_channel": true,
  "context_team_id": "string",
  "context_enterprise_id": "string"
}    
"""