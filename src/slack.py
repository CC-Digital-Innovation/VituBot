from enum import Enum
import json
import os

from dotenv import load_dotenv
from pydantic import BaseModel
import requests


# ====================== Environment / Global Variables =======================
load_dotenv(override=True)

# Initialize Slack constant global variables.
SLACK_OAUTH_TOKEN = os.getenv('SLACK_OAUTH_TOKEN')
SLACK_POST_CHANNEL = os.getenv('SLACK_POST_CHANNEL')
SLACK_BASE_API_URL = 'https://slack.com/api/'
SLACK_ACK_PAYLOAD = {
    "blocks": [
		{
			"type": "section",
			"text": {
				"type": "plain_text",
				"text": "Processing your request...",
				"emoji": True
			}
		}
	]
}


# =================================== Enums ===================================
class EventType(Enum):
    URL_VERIFICATION = 'url_verification'
    APP_MENTION = 'app_mention'


# ================================== Classes ==================================
class URLVerificationPayload(BaseModel):
    token: str
    challenge: str
    type: str


class Event(BaseModel):
    type: str
    event_ts: str
    user: str
    ts: str
    text: str
    channel: str


class OuterPayload(BaseModel):
    type: str
    token: str
    team_id: str
    api_app_id: str
    event: Event
    event_context: str
    event_id: str
    event_time: int
    authorizations: list[dict] | None
    is_ext_shared_channel: bool
    context_team_id: str
    context_enterprise_id: str | None
    

# ================================= Functions =================================
def send_message(json_payload: dict) -> None:
    # Add the channel into the payload.
    json_payload['channel'] = SLACK_POST_CHANNEL
    
    # Send the payload to Slack.
    send_message_response = requests.post(
        url=f'{SLACK_BASE_API_URL}chat.postMessage',
        headers={
            'Authorization': f'Bearer {SLACK_OAUTH_TOKEN}',
            'Content-Type': 'application/json'
        },
        data=f'{json.dumps(json_payload)}'
    )
    
    print(json.dumps(send_message_response.json(), indent=2))


def send_error(reason: str) -> None:
    # Send an error message to Slack.
    send_message(
        {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "plain_text",
                        "text": f":red_circle: Error processing your request:\n\n{reason}",
                        "emoji": True
                    }
		        }
            ]
        }
    )


def send_ack() -> None:
    # Send an acknowledgement message to Slack.
    send_message(SLACK_ACK_PAYLOAD)
    