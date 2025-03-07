import slack


# ====================== Environment / Global Variables =======================
HELP_PAYLOAD = {
    "blocks": [
		{
			"type": "section",
			"text": {
				"type": "plain_text",
				"text": ":information_source: VituBot supports the following commands:\n\n@vitubot wifi (Clover MAC address)\n     - Return the status of a Clover\n@vitubot status (site ID)\n     - Return the status of an entire site\n@vitubot help\n     - Display this message with usage information",
				"emoji": True
			}
		}
	]
}


# ================================= Functions =================================
def execute() -> None:
    """
    Sends the pre-formatted help message to Slack.
    """
    
    slack.send_message(HELP_PAYLOAD)
