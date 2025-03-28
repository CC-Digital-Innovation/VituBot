import services.slack as slack_service


# ====================== Environment / Global Variables =======================
HELP_PAYLOAD = {
    "blocks": [
		{
			"type": "section",
			"text": {
				"type": "mrkdwn",
				"text": ":information_source: VituBot supports the following commands:\n\nvitubot clovers (site ID)\n     - Return all non-online Clovers at a site\nvitubot wifi (Clover MAC address)\n     - Return the status of a Clover\nvitubot status (site ID)\n     - Return the status of an entire site\nvitubot help\n     - Display this message with usage information"
			}
		}
	]
}


# ================================= Functions =================================
def execute() -> None:
    """
    Sends the pre-formatted help message to Slack.
    """
    
    slack_service.send_message(HELP_PAYLOAD)
