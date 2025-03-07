# VituBot

## Summary
Used to output site / Clover statuses and analytics to Slack.

_Note: If you have any questions or comments you can always use GitHub
discussions, or email me at farinaanthony96@gmail.com._

#### Why
This bot will help enable our engineers as well as Vitu engineers with a quick
overview of the overall status of a site. This is much faster than logging into
PRTG or Meraki to grab these statistics. It also allows engineers to have
access to this information without needing a PRTG / Meraki account.

## Requirements
- Python 3.13+
- fastapi
- meraki
- loguru
- pydantic
- python-dotenv
- requests

## Usage
- Edit the example environment file with relevant Meraki, PRTG, and Slack 
  configuration information.

- Simply run the FastAPI script using Python:
  `fastapi run vitubot.py`

- Commands for the bot and how to use them can be found in this
  [Tettra page](https://app.tettra.co/teams/quokka-one/pages/vitubot).

## Compatibility
Should be able to run on any machine with a Python interpreter. This script
was only tested on a Windows machine running Python 3.13.1.

## Disclaimer
The code provided in this project is an open source example and should not
be treated as an officially supported product. Use at your own risk. If you
encounter any problems, please log an
[issue](https://github.com/CC-Digital-Innovation/VituBot/issues).

## Contributing
1. Fork it!
2. Create your feature branch: `git checkout -b my-new-feature`
3. Commit your changes: `git commit -am 'Add some feature'`
4. Push to the branch: `git push origin my-new-feature`
5. Submit a pull request ツ

## History
-  version 3.0.0 - 2025/03/03
    - Added support for Slack's block-building output
    - Improved visibility of statuses
    - More robust site status for the probe and network devices
    - Removed Hubot dependency
    - Improved logging
    - Updated license


-  version 2.0.0 - 2023/07/21
    - Remove dependency on hard-coded site names
    - Updated LICENSE file


-  version 1.0.1 - 2022/07/19
    - Add support for uppercase / dash notated MAC addresses
    - Add ability to pass MAC address into script's arguments
    - Added site name to ONLINE and OFFLINE Slack responses
    - Tweaked some Slack responses


-  version 1.0.0 - 2022/07/01
    - MVP initial release

## Credits
Anthony Farina <<farinaanthony96@gmail.com>>