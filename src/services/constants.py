from enum import Enum
import re


# ====================== Environment / Global Variables =======================
MAC_ADDRESS_REGEX = re.compile('([0-9a-f]{2}:){5}[0-9a-f]{2}')
THREE_DIGITS_REGEX = re.compile('[0-9]{3}')


# =================================== Enums ===================================
class SlackEmojiCodes(Enum):
    BLACK_SQUARE = ':black_square:'
    GRAY_QUESTION_MARK = ':grey_question:'
    GREEN_CIRCLE = ':large_green_circle:'
    HOLLOW_RED_CIRCLE = ':o:'
    NO_SYMBOL = ':no_entry_sign:'
    ORANGE_CIRCLE = ':large_orange_circle:'
    PAUSE_BUTTON = ':double_vertical_bar:'
    RED_CIRCLE = ':red_circle:'
    RED_EXCLAMATION_MARK = ':exclamation:'
    REPEAT_BUTTON = ':repeat:'
    THREE_O_CLOCK = ':clock3:'
    YELLOW_CIRCLE = ':large_yellow_circle:'
