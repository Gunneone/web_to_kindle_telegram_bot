"""
Server-side copy: what goes into mails and the test book. Everything on screen lives in the client.
"""

from html import escape

LANGUAGES = ('en', 'de')
DEFAULT_LANGUAGE = 'en'

TEXTS = {
    'en': {
        'test_book_title': "Your Kindle setup works!",
        'test_book_body': (
            "<h1>It works! 🎉</h1>"
            "<p>This test book was sent by Eselsohr. From now on, every article you send to your Kindle "
            "from the site will show up here.</p>"
            "<p>Tip: paste a link on the site, or send it to the Telegram bot.</p>"),
        'code_subject': "{code} is your Eselsohr sign-in code",
        'code_text': ("Your sign-in code: {code}\n\n"
                      "Or open this link: {link}\n\n"
                      "Both work for {minutes} minutes. If you didn't ask for this, ignore this mail."),
        'code_html': ("<p>Your sign-in code:</p><p style=\"font-size:28px;letter-spacing:4px\"><b>{code}</b></p>"
                      "<p>Or <a href=\"{link}\">sign in with one click</a>.</p>"
                      "<p>Both work for {minutes} minutes. If you didn't ask for this, ignore this mail.</p>"),
    },
    'de': {
        'test_book_title': "Deine Kindle-Einrichtung funktioniert!",
        'test_book_body': (
            "<h1>Es funktioniert! 🎉</h1>"
            "<p>Dieses Testbuch hat Eselsohr geschickt. Ab jetzt landet hier jeder Artikel, den du auf der "
            "Seite an dein Kindle schickst.</p>"
            "<p>Tipp: Füge einen Link auf der Seite ein oder schick ihn an den Telegram-Bot.</p>"),
        'code_subject': "{code} ist dein Eselsohr-Anmeldecode",
        'code_text': ("Dein Anmeldecode: {code}\n\n"
                      "Oder öffne diesen Link: {link}\n\n"
                      "Beides gilt {minutes} Minuten. Falls du das nicht angefordert hast, ignoriere diese Mail."),
        'code_html': ("<p>Dein Anmeldecode:</p><p style=\"font-size:28px;letter-spacing:4px\"><b>{code}</b></p>"
                      "<p>Oder <a href=\"{link}\">mit einem Klick anmelden</a>.</p>"
                      "<p>Beides gilt {minutes} Minuten. Falls du das nicht angefordert hast, "
                      "ignoriere diese Mail.</p>"),
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    template = TEXTS.get(lang, TEXTS[DEFAULT_LANGUAGE]).get(key) or TEXTS[DEFAULT_LANGUAGE][key]
    if kwargs and key.endswith('_html'):
        kwargs = {name: escape(str(value)) for name, value in kwargs.items()}
    return template.format(**kwargs) if kwargs else template


def pick_language(*candidates: str | None) -> str:
    """The first candidate that is a supported language ('de-AT' counts as 'de'), else English."""
    for candidate in candidates:
        code = (candidate or '').lower().split(',')[0].split(';')[0].split('-')[0].strip()
        if code in LANGUAGES:
            return code
    return DEFAULT_LANGUAGE
