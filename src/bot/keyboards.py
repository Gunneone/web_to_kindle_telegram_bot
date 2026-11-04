"""
Inline keyboards. Callback data is '<area>:<action>[:<arg>]' and always ≤ 64 bytes.
"""

from telegram import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import KeyboardButtonStyle

from core import db
from core.kindle import AMAZON_STORES, POCKETBOOK, device_of

from .texts import LANGUAGE_NAMES, LANGUAGES, for_device, t

PRIMARY = KeyboardButtonStyle.PRIMARY
SUCCESS = KeyboardButtonStyle.SUCCESS
DANGER = KeyboardButtonStyle.DANGER

HISTORY_PAGE_SIZE = 5

# Callback data
SETUP_START = 'setup:start'      # ask for the Kindle address
SETUP_EPUB = 'setup:epub'        # chat delivery only, no Kindle
SETUP_ADDED = 'setup:added'      # sender approved at Amazon -> step 3
SETUP_TEST = 'setup:test'        # send the test book
SETUP_YES = 'setup:yes'          # the test book arrived
SETUP_NO = 'setup:no'            # it didn't -> troubleshooting
SETUP_SKIP = 'setup:skip'
SHOW_SETTINGS = 'set:show'
SHOW_HELP = 'help:show'
SET_LINKS = 'set:links'
SET_TEST = 'set:test'
SET_DELETE = 'set:delete'
SET_DELETE_YES = 'set:delete_yes'
SET_STORE = 'set:store'          # pick the Amazon store (then 'set:store:<store>')

# The store picker from setup step 2 / troubleshooting: 'setup:store:<where>[:<store>|:back]'
STORE_STEP2 = 's'
STORE_TROUBLESHOOT = 't'


def setup_store(where: str, choice: str | None = None) -> str:
    return f'setup:store:{where}' + (f':{choice}' if choice else '')


def set_mode(mode: str) -> str:
    return f'set:mode:{mode}'


def set_lang(lang: str) -> str:
    return f'set:lang:{lang}'


def article_action(action: str, article_id: int) -> str:
    """
    action: 'kindle' (send to Kindle), 'file' (EPUB to the chat), 'again' (deliver as usual, new message),
    'retry' (deliver as usual, reusing the message the button is on)
    """
    return f'art:{action}:{article_id}'


def history_page(offset: int) -> str:
    return f'hist:{offset}'


def button(text: str, data: str | None = None, *, url: str | None = None, copy: str | None = None,
           style: str | None = None) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data, url=url,
                                copy_text=CopyTextButton(copy) if copy else None, style=style)


def markup(*rows) -> InlineKeyboardMarkup:
    """Rows of buttons; None rows and None buttons are left out."""
    rows = [[b for b in row if b] for row in rows if row]
    return InlineKeyboardMarkup([row for row in rows if row])


def start_new(lang):
    return markup([button(t(lang, 'btn_setup_kindle'), SETUP_START, style=PRIMARY)],
                  [button(t(lang, 'btn_epub_only'), SETUP_EPUB)])


def start_ready(lang):
    return markup([button(t(lang, 'btn_settings'), SHOW_SETTINGS), button(t(lang, 'btn_help'), SHOW_HELP)])


def store_of(amazon_url: str) -> str:
    """'https://www.amazon.de/hz/...' -> 'amazon.de'"""
    return amazon_url.split('/')[2].removeprefix('www.')


def amazon_buttons(lang, amazon_url: str, where: str):
    """Open the settings at the guessed store, or pick another one (an English Telegram says nothing
    about which country someone's Amazon account is in)."""
    return [[button(t(lang, 'btn_open_amazon', store=store_of(amazon_url)), url=amazon_url)],
            [button(t(lang, 'btn_other_store'), setup_store(where))]]


def store_picker(lang, current: str, choice_prefix: str, back: str):
    """All stores, three per row, the current one ticked; `choice_prefix` + ':' + store picks one."""
    buttons = [button(f"✓ {store}" if store == current else store, f'{choice_prefix}:{store}')
               for store in AMAZON_STORES]
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    return markup(*rows, [button(t(lang, 'btn_back'), back)])


def setup_sender(lang, sender: str, amazon_url: str | None, *, done_button: bool = True):
    """Step 2. Without `amazon_url` (a PocketBook, which has no sender list to fill in) there is
    nothing to copy or open: the user only acknowledges that PocketBook will ask them to confirm."""
    if amazon_url is None:
        return markup([button(t(lang, 'btn_change_email'), SETUP_START),
                       button(t(lang, 'btn_got_it'), SETUP_ADDED, style=PRIMARY) if done_button else None])
    return markup(
        [button(t(lang, 'btn_copy_sender'), copy=sender)] if sender else None,
        *amazon_buttons(lang, amazon_url, STORE_STEP2),
        [button(t(lang, 'btn_change_email'), SETUP_START),
         button(t(lang, 'btn_sender_added'), SETUP_ADDED, style=PRIMARY) if done_button else None],
    )


def setup_test(lang):
    return markup([button(t(lang, 'btn_send_test'), SETUP_TEST, style=SUCCESS)],
                  [button(t(lang, 'btn_skip'), SETUP_SKIP)])


def test_result(lang):
    return markup([button(t(lang, 'btn_arrived'), SETUP_YES, style=SUCCESS),
                   button(t(lang, 'btn_not_arrived'), SETUP_NO)])


def test_retry(lang):
    return markup([button(t(lang, 'btn_try_again'), SETUP_TEST, style=PRIMARY)])


def troubleshoot(lang, sender: str, amazon_url: str | None):
    return markup(
        [button(t(lang, 'btn_try_again'), SETUP_TEST, style=PRIMARY)],
        [button(t(lang, 'btn_copy_sender'), copy=sender)] if sender else None,
        *(amazon_buttons(lang, amazon_url, STORE_TROUBLESHOOT) if amazon_url else []),
        [button(t(lang, 'btn_change_email'), SETUP_START)],
    )


def settings(lang, user: db.User, store: str | None = None):
    """`store`: the Amazon store links go to (a button changes it); none for a PocketBook."""
    mode = user.delivery_mode if user.kindle_email else db.TELEGRAM
    mode = mode or db.KINDLE
    other_lang = next(code for code in LANGUAGES if code != lang)

    def mode_button(value):
        label = t(lang, f'mode_{value}')
        return button(f"✓ {label}" if value == mode else label, set_mode(value))

    links = t(lang, 'on' if user.image_links else 'off')
    return markup(
        [button(t(lang, 'btn_change_email' if user.kindle_email else 'btn_set_email'), SETUP_START,
                style=None if user.kindle_email else PRIMARY)],
        [mode_button(db.KINDLE), mode_button(db.TELEGRAM), mode_button(db.BOTH)],
        [button(t(lang, 'btn_links', state=links), SET_LINKS),
         button(LANGUAGE_NAMES[other_lang], set_lang(other_lang))],
        [button(t(lang, 'btn_send_test'), SET_TEST)] if user.kindle_email else None,
        [button(t(lang, 'btn_amazon_store', store=store), SET_STORE)]
        if store and device_of(user.kindle_email) != POCKETBOOK else None,
        [button(t(lang, 'btn_delete_data'), SET_DELETE, style=DANGER)],
    )


def delete_confirm(lang):
    return markup([button(t(lang, 'btn_delete_yes'), SET_DELETE_YES, style=DANGER)],
                  [button(t(lang, 'btn_cancel'), SHOW_SETTINGS)])


def privacy(lang):
    return markup([button(t(lang, 'btn_delete_data'), SET_DELETE, style=DANGER)])


def result_card(lang, article_id: int, url: str, delivered_to: set[str], user: db.User, is_preview: bool):
    """Buttons under a delivered book: the original, plus whatever delivery didn't happen yet."""
    actions = []
    if db.TELEGRAM not in delivered_to:
        actions.append(button(t(lang, 'btn_epub_here'), article_action('file', article_id)))
    if user.kindle_email:
        label = 'btn_resend' if db.KINDLE in delivered_to else for_device('btn_send_to_kindle', user.kindle_email)
        actions.append(button(t(lang, label), article_action('kindle', article_id)))
    elif not user.chose_chat_only:
        actions.append(button(t(lang, 'btn_setup_kindle'), SETUP_START, style=PRIMARY))
    original = t(lang, 'btn_full_post' if is_preview else 'btn_original')
    return markup([button(original, url=url)], actions)


def error_card(lang, article_id: int, url: str):
    return markup([button(t(lang, 'btn_retry'), article_action('retry', article_id), style=PRIMARY),
                   button(t(lang, 'btn_open_link'), url=url)])


def duplicate(lang, article_id: int):
    return markup([button(t(lang, 'btn_send_again'), article_action('retry', article_id)),
                   button(t(lang, 'btn_epub_here'), article_action('file', article_id))])


def send_to_kindle(lang, article_id: int, address: str | None = None):
    label = t(lang, for_device('btn_send_to_kindle', address))
    return markup([button(label, article_action('kindle', article_id), style=PRIMARY)])


def history(articles: list[db.Article], offset: int, total: int):
    numbers = [button(str(offset + i + 1), article_action('again', a.id)) for i, a in enumerate(articles)]
    nav = []
    if offset > 0:
        nav.append(button('◀️', history_page(max(0, offset - HISTORY_PAGE_SIZE))))
    if offset + HISTORY_PAGE_SIZE < total:
        nav.append(button('▶️', history_page(offset + HISTORY_PAGE_SIZE)))
    return markup(numbers, nav)


def guest_setup(lang, bot_username: str):
    return markup([button(t(lang, 'btn_guest_setup'), url=f'https://t.me/{bot_username}?start=setup')])
