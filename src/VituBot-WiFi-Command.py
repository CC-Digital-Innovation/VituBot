import configparser
import os
import re
import sys

import meraki
from meraki import exceptions
import requests


# Module information.
__author__ = 'Anthony Farina'
__copyright__ = 'Copyright (C) 2022 Anthony Farina'
__credits__ = ['Anthony Farina']
__maintainer__ = 'Anthony Farina'
__email__ = 'farinaanthony96@gmail.com'
__license__ = 'MIT'
__version__ = '1.0.0'
__status__ = 'Released'


# Configuration file access variables.
CONFIG = configparser.ConfigParser()
CONFIG_PATH = '../configs/VituBot-config.ini'
SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))
CONFIG.read(SCRIPT_PATH + '/' + CONFIG_PATH)

# Meraki API credentials.
MERAKI_API_KEY = CONFIG['Meraki Info']['api-key']
MERAKI_ORG_ID = CONFIG['Meraki Info']['org-id']
MERAKI_NET_ID = CONFIG['Meraki Info']['net-id']

# Slack configurations.
SLACK_POST_CHANNEL = str('#' + CONFIG['Slack Info']['channel'])
SLACK_TOKEN = CONFIG['Slack Info']['oauth-token']

# Other global constants.
MAC_REGEX = re.compile('([0-9a-f]{2}:){5}[0-9a-f]{2}')
MERAKI_DEVICES = \
    {
        '98:18:88:73:e6:48': 'Alturas537',
        '68:3a:1e:84:f0:a7': 'Anaheim698',
        '68:3a:1e:84:ee:f6': 'Arleta587',
        '68:3a:1e:84:f0:a4': 'Arvin661',
        '68:3a:1e:84:e1:f3': 'Auburn570',
        '68:3a:1e:84:e1:da': 'Bakersfield529',
        '68:3a:1e:84:e3:b6': 'BakersfieldSW679',
        '98:18:88:73:d8:6d': 'Banning641',
        '98:18:88:73:d8:ac': 'Barstow582',
        '68:3a:1e:84:ee:8d': 'BellGardens576',
        '68:3a:1e:84:ed:eb': 'Bellflower606',
        '98:18:88:73:db:17': 'Bishop585',
        '98:18:88:73:da:0e': 'Blythe528',
        '98:18:88:73:f3:ac': 'Brawley597',
        '98:18:88:73:b1:3c': 'Capitola550',
        '68:3a:1e:84:ed:e7': 'Carmichael625',
        '98:18:88:73:da:3a': 'Chico520',
        '68:3a:1e:1f:3c:6d': 'ChulaVista613',
        '98:18:88:73:d8:88': 'Clearlake830',
        '68:3a:1e:84:e6:01': 'Clovis580',
        '68:3a:1e:84:e5:10': 'Coalinga603',
        '68:3a:1e:84:dd:44': 'Colusa564',
        '98:18:88:73:b2:b3': 'Compton581',
        '98:18:88:73:f3:a7': 'Concord523',
        '68:3a:1e:84:75:28': 'CorteMadera534',
        '68:3a:1e:84:ed:4c': 'CostaMesa628',
        '98:18:88:73:dd:95': 'CrescentCity524',
        '68:3a:1e:84:a0:6a': 'CulverCity514',
        '98:18:88:73:d8:a7': 'DalyCity599',
        '68:3a:1e:84:ee:be': 'Davis598',
        '98:18:88:73:dd:cb': 'Delano615',
        '68:3a:1e:1f:4f:2d': 'ElCajon669',
        '98:18:88:73:ec:64': 'ElCentro527',
        '98:18:88:73:b5:da': 'ElCerrito556',
        '98:18:88:73:b2:2b': 'ElMonte685',
        '98:18:88:73:c0:a2': 'Eureka526',
        '98:18:88:73:ba:95': 'Fairfield621',
        '98:18:88:73:d9:d3': 'FallRiverMills643',
        '68:3a:1e:84:ef:b0': 'Folsom655',
        '68:3a:1e:84:e5:06': 'Fontana657',
        '68:3a:1e:84:e7:5e': 'FontanaCDTC699',
        '68:3a:1e:84:dd:65': 'FontanaDLPC688',
        '98:18:88:73:b7:a4': 'FortBragg590',
        '98:18:88:73:b1:64': 'Fremont644',
        '68:3a:1e:84:ee:19': 'Fresno505',
        '68:3a:1e:84:f0:8c': 'FresnoCDTC215',
        '68:3a:1e:1f:45:cb': 'FresnoNorth646',
        '68:3a:1e:84:d3:5b': 'Fullerton607',
        '98:18:88:73:d9:b7': 'Garberville627',
        '98:18:88:73:ba:8c': 'GardenaCDTC498',
        '98:18:88:73:d9:d1': 'Gilroy623',
        '68:3a:1e:84:e1:f8': 'Glendale510',
        '98:18:88:73:dd:db': 'Goleta670',
        '98:18:88:73:b7:72': 'GrassValley541',
        '98:18:88:73:f4:c9': 'Hanford565',
        '98:18:88:73:dd:c8': 'Hawthorne609',
        '68:3a:1e:84:e5:75': 'Hayward579',
        '98:18:88:73:e6:86': 'Hemet635',
        '68:3a:1e:84:dd:3d': 'Hollister546',
        '98:18:88:73:ba:52': 'HollywoodCole508',
        '68:3a:1e:84:f0:91': 'HollywoodWest652',
        '98:18:88:73:bf:be': 'Indio578',
        '98:18:88:74:00:b9': 'Inglewood610',
        '68:3a:1e:84:ef:1e': 'Jackson521',
        '68:3a:1e:84:ee:68': 'KingCity647',
        '98:18:88:73:ba:59': 'LagunaHills605',
        '98:18:88:73:d9:b8': 'LakeIsabella687',
        '98:18:88:73:dd:82': 'Lakeport530',
        '68:3a:1e:84:e6:e1': 'Lancaster595',
        '98:18:88:73:b8:a2': 'LincolnPark617',
        '68:3a:1e:84:ee:5c': 'Lodi622',
        '98:18:88:73:b6:81': 'Lompoc692',
        '98:18:88:73:bc:b3': 'LongBeach507',
        '68:3a:1e:84:ee:97': 'LosBanos650',
        '68:3a:1e:84:ed:d9': 'LosGatos640',
        '98:18:88:73:fd:13': 'Madera533',
        '68:3a:1e:84:e6:f6': 'Manteca658',
        '98:18:88:73:c0:64': 'Mariposa566',
        '68:3a:1e:84:ee:c7': 'MendotaTravelRun822',
        '68:3a:1e:84:e1:f4': 'Merced536',
        '98:18:88:73:c0:a3': 'Modesto557',
        '98:18:88:73:dd:ca': 'Montebello511',
        '68:3a:1e:84:de:4b': 'Mt.Shasta639',
        '98:18:88:73:fe:3f': 'Napa540',
        '98:18:88:73:d9:b9': 'Needles584',
        '68:3a:1e:84:e6:cc': 'Newhall662',
        '68:3a:1e:84:dd:05': 'Norco586',
        '68:3a:1e:84:f0:40': 'Novato686',
        '98:18:88:73:b1:31': 'OaklandClaremont504',
        '98:18:88:73:bc:b1': 'OaklandColiseum604',
        '68:3a:1e:84:ef:8a': 'Oceanside596 ',
        '98:18:88:73:d9:cd': 'Oroville522',
        '68:3a:1e:84:ef:04': 'Oxnard636',
        '98:18:88:74:04:1c': 'PacoimaDLPC693',
        '98:18:88:73:c0:72': 'PalmDesert683',
        '98:18:88:73:dd:7b': 'PalmSprings659',
        '68:3a:1e:84:ef:03': 'Pasadena509',
        '98:18:88:73:dd:d1': 'PasoRobles574',
        '68:3a:1e:84:f0:55': 'Petaluma634',
        '98:18:88:74:00:7b': 'Pittsburg592',
        '68:3a:1e:84:e1:ed': 'Placerville525',
        '98:18:88:73:bf:d2': 'Pleasanton631',
        '68:3a:1e:84:ee:5d': 'Pomona532',
        '98:18:88:73:db:1c': 'Porterville573',
        '68:3a:1e:84:a3:0c': 'Poway676',
        '98:18:88:73:d9:aa': 'Quincy544',
        '68:3a:1e:84:f0:c1': 'RanchoCucamonga612',
        '68:3a:1e:84:e1:eb': 'Ready 1 ( LosAngeles502)',
        '68:3a:1e:84:ed:c7': 'Ready 12',
        '68:3a:1e:1f:46:6c': 'Ready 16',
        '68:3a:1e:84:e5:24': 'Ready 17',
        '68:3a:1e:84:ef:a8': 'Ready 19',
        '68:3a:1e:84:ed:48': 'Ready 2 ( LosAngeles502)',
        '68:3a:1e:84:f0:aa': 'Ready 20',
        '68:3a:1e:84:a7:b2': 'Ready 21',
        '68:3a:1e:84:ed:b1': 'Ready 23',
        '68:3a:1e:84:a8:0d': 'Ready 24',
        '68:3a:1e:84:e1:fb': 'Ready 25',
        '98:18:88:73:b2:61': 'Ready 26',
        '68:3a:1e:84:ef:2b': 'Ready 3',
        '68:3a:1e:84:ed:cb': 'Ready 4',
        '68:3a:1e:84:e1:f7': 'Ready 5',
        '68:3a:1e:84:ed:4e': 'Ready 6',
        '68:3a:1e:84:ed:9b': 'RedBluff558',
        '98:18:88:73:b1:39': 'Redding551',
        '68:3a:1e:84:e1:4e': 'Redlands626',
        '98:18:88:73:b3:91': 'RedwoodCity548',
        '68:3a:1e:84:e3:6f': 'Reedley633',
        '98:18:88:73:db:63': 'Ridgecrest577',
        '68:3a:1e:84:ee:4d': 'Riverside545',
        '98:18:88:74:00:7f': 'RiversideEast656',
        '68:3a:1e:84:e3:aa': 'Rocklin673',
        '68:3a:1e:31:e3:8f': 'Roseville543',
        '68:3a:1e:84:6c:c0': 'Sacramento501',
        '68:3a:1e:1f:4a:94': 'SacramentoCapitol ',
        '98:18:88:73:dd:7c': 'Salinas539',
        '68:3a:1e:84:ef:78': 'SanAndreas568',
        '68:3a:1e:84:ee:0c': 'SanBernardino512',
        '98:18:88:73:e6:42': 'SanClemente648',
        '68:3a:1e:1f:4d:73': 'SanDiego519',
        '68:3a:1e:1f:3e:ce': 'SanDiegoNormal506',
        '98:18:88:73:b5:bd': 'SanFrancisco503',
        '68:3a:1e:84:a8:d6': 'SanJose516',
        '98:18:88:73:d8:93': 'SanJoseDLPC645',
        '98:18:88:73:d8:73': 'SanJoseDLPC645-2',
        '98:18:88:73:c0:65': 'SanLuisObispo547',
        '68:3a:1e:84:f0:b6': 'SanMarcos689',
        '98:18:88:73:fd:c3': 'SanMateo593',
        '98:18:88:73:bc:8a': 'SanPedro619',
        '98:18:88:74:00:84': 'SanYsidro677',
        '68:3a:1e:84:e1:fc': 'SantaAna542',
        '98:18:88:73:c0:61': 'SantaBarbara549',
        '68:3a:1e:84:a7:19': 'SantaClara632',
        '98:18:88:73:e5:83': 'SantaMaria563',
        '98:18:88:73:fd:05': 'SantaMonica616',
        '98:18:88:73:e6:82': 'SantaPaula630',
        '98:18:88:73:ec:7c': 'SantaRosa555',
        '68:3a:1e:84:e5:6d': 'SantaTeresa668',
        '98:18:88:73:db:65': 'Seaside567',
        '98:18:88:73:b1:47': 'Shafter660',
        '98:18:88:73:b2:32': 'SimiValley680',
        '68:3a:1e:84:ef:ca': 'Sonora569',
        '98:18:88:73:ba:a4': 'SouthLakeTahoe538',
        '68:3a:1e:84:ef:26': 'SouthSacramento602',
        '98:18:88:73:b8:5e': 'Stockton517',
        '68:3a:1e:84:e1:97': 'Stoneridge664',
        '98:18:88:73:db:77': 'Susanville531',
        '68:3a:1e:84:ef:c1': 'Taft575',
        '98:18:88:73:fd:0c': 'Temecula672',
        '68:3a:1e:84:e9:54': 'ThousandOaks663 ',
        '98:18:88:73:d8:a6': 'Torrance608',
        '98:18:88:73:e6:4c': 'Tracy642',
        '98:18:88:73:ba:63': 'Truckee513',
        '98:18:88:73:b3:37': 'Tulare594',
        '98:18:88:73:b7:49': 'Tulelake553',
        '68:3a:1e:84:da:01': 'Turlock649',
        '98:18:88:73:c0:ac': 'TwentyninePalms638',
        '98:18:88:73:bd:ee': 'Ukiah535',
        '98:18:88:73:d9:9f': 'Vacaville588',
        '98:18:88:73:ec:41': 'Vallejo554',
        '68:3a:1e:84:f0:05': 'VanNuys515',
        '98:18:88:73:b3:90': 'Ventura560',
        '68:3a:1e:1f:51:58': 'Victorville629',
        '68:3a:1e:84:6d:c8': 'Visalia559',
        '68:3a:1e:84:ee:c4': 'WSacramento697',
        '68:3a:1e:84:ed:8b': 'Watsonville583',
        '98:18:88:73:d9:ce': 'Weaverville572',
        '98:18:88:73:b2:4f': 'WestCovina618',
        '68:3a:1e:84:f0:a3': 'Westminster611',
        '68:3a:1e:84:a9:c9': 'Whittier591',
        '68:3a:1e:84:dc:fd': 'Willows571',
        '98:18:88:73:c0:7b': 'Winnetka637',
        '98:18:88:73:b6:88': 'WinnetkaIBC671',
        '68:3a:1e:84:a7:42': 'Woodland561',
        '98:18:88:73:d9:18': 'Yreka552',
        '68:3a:1e:84:a6:e8': 'YubaCity562',
    }


# Given a MAC address, find the status of the client on the configured
# Meraki network. Then send the status to the configured Slack channel.
def meraki_get_client_status(mac_addr: str):
    # Clean the MAC address string.
    clean_mac = mac_addr.lower().replace('-', ':')

    # Check if the MAC address string is an invalid MAC address.
    if not MAC_REGEX.match(clean_mac):
        send_slack_response(':exclamation: | ' + clean_mac +
                            ' is not a MAC address')
        return

    # Set up the connection to Meraki.
    meraki_dash = meraki.DashboardAPI(MERAKI_API_KEY,
                                      output_log=False)

    # Try to find the device with the given MAC address in Meraki.
    try:
        response = meraki_dash.networks.getNetworkClient(
            networkId=MERAKI_NET_ID,
            clientId=clean_mac
        )
    # Something went wrong. Send the response to Slack.
    except meraki.exceptions.APIError:
        resp = ':exclamation: | An API error occurred while finding ' \
               'device with MAC address \"' + clean_mac + '\" in Meraki'
        send_slack_response(resp)
        return

    # Check the device's status on Meraki.
    if response['status'] == 'Online':
        resp = ':large_green_circle: | Device with MAC address \"' + \
               clean_mac + '\" is ONLINE in Meraki at site ' + \
               MERAKI_DEVICES[response['recentDeviceMac']]
    elif response['status'] == 'Offline':
        resp = ':red_circle: | Device with MAC address \"' + clean_mac + \
               '\" is OFFLINE in Meraki at site ' + \
               MERAKI_DEVICES[response['recentDeviceMac']]
    else:
        resp = ':grey_question: | Device with MAC address \"' + clean_mac + \
               '\" is UNKNOWN in Meraki'

    # Return the result to Slack.
    send_slack_response(resp)


# Send the provided response to the configured Slack channel.
def send_slack_response(response: str):
    requests.post(url='https://slack.com/api/chat.postMessage',
                  headers={
                      'Authorization': 'Bearer ' + SLACK_TOKEN,
                      'Content-Type': 'application/json; '
                                      'charset=utf-8'
                  },
                  json={
                      'channel': SLACK_POST_CHANNEL,
                      'text': response,
                      'as_user': False,
                      'username': 'vitubot',
                      'icon_url':
                          'https://img.icons8.com/plasticine/2x/bot.png'
                  })


# Main method for the script. Input is 1 argument: a valid MAC address string.
if __name__ == '__main__':
    # Check if an input argument was not given to the script.
    if len(sys.argv) != 2:
        invalid_args = ':exclamation: | Invalid number of arguments given'
        send_slack_response(invalid_args)
    # Run the script.
    else:
        meraki_get_client_status(sys.argv[1])
