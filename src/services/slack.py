from enum import Enum
import json
import os

from dotenv import load_dotenv
from loguru import logger
from pydantic import BaseModel
import requests

import services.constants as constants


# ====================== Environment / Global Variables =======================
load_dotenv(override=True)

# Initialize Slack constant global variables.
SLACK_OAUTH_TOKEN = os.getenv('SLACK_OAUTH_TOKEN')
SLACK_POST_CHANNEL_ID = os.getenv('SLACK_POST_CHANNEL_ID')
SLACK_BASE_API_URL = 'https://slack.com/api'


class EventType(Enum):
    """
    Represents the supported Slack event types.
    """
    
    APP_MENTION = 'app_mention'
    EVENT_CALLBACK = 'event_callback'
    URL_VERIFICATION = 'url_verification'


# ================================== Classes ==================================
class URLVerificationPayload(BaseModel):
    """
    Represents a URL verification payload received from Slack.

    Args:
        token (str): A token of some sort. No use / purpose at the moment.
        challenge (str): The challenge string. This will need to be sent
            back to the Slack API to acknowledge that we are a legitimate
            endpoint.
        type (str): The Slack event type. This will always be 
            "url_verification".
    """
    
    token: str
    challenge: str
    type: str


class Event(BaseModel):
    """
    Represents a Slack event.

    Args:
        user (str): The user ID that triggered the event.
        type (str): The type of Slack event.
        ts (str): The Unix timestamp when this event occurred in seconds with
            a floating point decimal that includes microseconds.
        client_msg_id (str): The ID of the message from Slack.
        text (str): The text that the user typed to trigger the event.
        team (str): The team ID.
        blocks (list[dict]): A list of blocks that describe what the message
            looked like in Slack.
        channel (str): The channel ID where the event occurred.
        event_ts (str): The Unix timestamp when this event occurred in
            microseconds.
    """
    
    user: str
    type: str
    ts: str
    client_msg_id: str
    text: str
    team: str
    blocks: list[dict]
    channel: str
    event_ts: str


class EventCallback(BaseModel):
    """
    Represents the event callback payload received from Slack when a configured
    event occurs for this bot.

    Args:
        token (str): The token used to validate this event callback. If this is
            invalid, discard this callback.
        team_id (str): The ID of the workspace / team where this event callback
            came from.
        api_app_id (str): The app ID associated with this event callback.
        event (Event): The Slack event.
        type (str): The type of callback. Typically this is "event_callback".
        event_id (str): The ID of this event instance that is unique across
            Slack globally.
        event_time (int): The Unix timestamp in seconds when this event
            occurred.
        authorizations (list[dict] | None): An installation of this app.
        is_ext_shared_channel (bool): True if the event occurred in an external
            channel, false otherwise.
        event_context (str): An identifier for this specific event instance.
    """
    
    token: str
    team_id: str
    api_app_id: str
    event: Event
    type: str
    event_id: str
    event_time: int
    authorizations: list[dict] | None
    is_ext_shared_channel: bool
    event_context: str
    

# ================================= Functions =================================
def send_message(json_payload: dict) -> None:
    """
    Send the provided JSON-formatted dictionary to the configured Slack
    channel. Guidelines for how to properly format a message for Slack
    can be found here: https://api.slack.com/reference/surfaces/formatting

    Args:
        json_payload (dict): A formatted JSON object that represents a message
            to send to Slack.
    """
    
    # Add the channel into the payload.
    json_payload['channel'] = SLACK_POST_CHANNEL_ID
    
    # Send the payload to Slack.
    send_message_response = requests.post(
        url=f'{SLACK_BASE_API_URL}/chat.postMessage',
        headers={
            'Authorization': f'Bearer {SLACK_OAUTH_TOKEN}',
            'Content-Type': 'application/json'
        },
        data=f'{json.dumps(json_payload)}'
    )
    
    # Log if the message was sent successfully or not.
    if send_message_response.ok:
        logger.info('Slack message successfully sent!')
    else:
        logger.error('Slack message failed to send')


def send_error(reason: str) -> None:
    """
    Sends a pre-formatted JSON dictionary with the included error reason to
    Slack.

    Args:
        reason (str): The reason for error.
    """
    
    # Send an error message to Slack.
    send_message(
        {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{constants.SlackEmojiCodes.RED_EXCLAMATION_MARK.value} Error processing your request:\n\n{reason}"
                    }
		        }
            ]
        }
    )


def send_ack() -> None:
    """
    Sends a pre-formatted JSON dictionary to Slack. This is an acknowledgement
    message so the user in Slack knows the bot is working on their request.
    """
    
    # Send an acknowledgement message to Slack.
    send_message(
        {
            "blocks": [
		        {
			        "type": "section",
			        "text": {
				        "type": "mrkdwn",
				        "text": f"{constants.SlackEmojiCodes.REPEAT_BUTTON.value} Processing your request..."
			        }
		        }
	        ]
        }
    )
    