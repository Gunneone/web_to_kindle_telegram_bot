"""
Every user-facing text, in English and German. Messages use Telegram HTML.

t() HTML-escapes its keyword arguments, so titles and addresses can be passed as they are;
wrap a value in Raw() when it is markup you built yourself.
"""

from html import escape

from core.kindle import POCKETBOOK, device_of

LANGUAGES = ('en', 'de')
DEFAULT_LANGUAGE = 'en'
LANGUAGE_NAMES = {'en': '🇬🇧 English', 'de': '🇩🇪 Deutsch'}


class Raw(str):
    """A value that t() inserts without escaping."""


TEXTS = {
    'en': {
        # Bot profile (setMyDescription ≤ 512, setMyShortDescription ≤ 120 characters)
        'bot_description': (
            "Send me a link to any article (Substack, Medium, news sites, blogs) and I'll turn it into a "
            "clean e-book and deliver it to your Kindle, or right here as an EPUB file."),
        'bot_short_description': "Articles from the web → e-books on your Kindle. Just send a link.",
        'cmd_start': "Start and set up",
        'cmd_settings': "Kindle address, delivery, language",
        'cmd_history': "Your recent books",
        'cmd_help': "How to use the bot",
        'cmd_privacy': "What's stored, delete your data",

        # /start
        'start_new': (
            "👋 Hi {name}! I turn web articles into e-books.\n\n"
            "Send me a link from Substack, Medium or almost any website and I'll deliver it to your "
            "<b>Kindle</b>, or straight into this chat as an <b>EPUB file</b>."),
        'start_ready': "📚 Ready! Send me any article link and I'll deliver it to {target}.",
        'target_kindle': "your Kindle",
        'target_telegram': "this chat",
        'target_both': "your Kindle and this chat",
        'btn_setup_kindle': "📚 Set up Kindle",
        'btn_epub_only': "📥 Just send me EPUB files",
        'btn_settings': "⚙️ Settings",
        'btn_help': "❓ Help",
        'epub_only_set': (
            "👍 Done. I'll send books right here as EPUB files. Send me a link to try it.\n\n"
            "You can switch to Kindle delivery any time in /settings."),

        # Setup step 1
        'setup_step1': (
            "<b>Step 1 of 3 · Your Kindle address</b>\n\n"
            "Send me your Kindle's email address. On your <a href=\"{url}\">Amazon devices page</a>, "
            "pick your Kindle and look for <i>Email</i>. It ends in <code>@kindle.com</code>.\n\n"
            "<i>Reading on a PocketBook? Send its Send-to-PocketBook address instead, ending in "
            "<code>@pbsync.com</code>.</i>"),
        'setup_step1_current': (
            "<b>Your Kindle address</b>\n\n"
            "Currently: <code>{email}</code>\n\nSend me a new address to change it, or /cancel."),
        'email_placeholder': "name_ab12@kindle.com",
        'email_invalid': (
            "That doesn't look like a Kindle address. It ends in <code>@kindle.com</code>, e.g. "
            "<code>name_ab12@kindle.com</code> (or <code>@pbsync.com</code> for a PocketBook). Try again or /cancel."),
        'email_not_kindle': (
            "<code>{email}</code> is a regular email address. Your Kindle has its own Send-to-Kindle "
            "address ending in <code>@kindle.com</code>: on your <a href=\"{url}\">Amazon devices page</a>, "
            "pick your Kindle and look for <i>Email</i>. On a PocketBook it ends in "
            "<code>@pbsync.com</code>. "
            "Try again or /cancel."),

        # Setup step 2
        'setup_step2': (
            "<b>Step 2 of 3 · Allow my address</b>\n\n"
            "✅ Saved: <code>{email}</code>\n\n"
            "Amazon only accepts books from senders you approved. Add this address to your "
            "<i>Approved Personal Document E-mail List</i>:\n\n"
            "<code>{sender}</code>\n\n"
            "On Amazon's <i>Preferences</i> page, scroll down to <i>Personal Document Settings</i>."),
        'btn_copy_sender': "📋 Copy address",
        'btn_open_amazon': "🔗 Open Amazon settings ({store})",
        'btn_other_store': "🌍 Other Amazon store",
        'btn_amazon_store': "🛒 Amazon store: {store}",
        'btn_back': "← Back",
        'btn_change_email': "✏️ Change address",
        'btn_sender_added': "✅ I've added it",

        # Setup step 3
        'setup_step3': (
            "<b>Step 3 of 3 · Test it</b>\n\n"
            "I'll send a tiny test book to <code>{email}</code>. It should show up on your Kindle within "
            "a few minutes."),
        'btn_send_test': "📨 Send test book",
        'btn_skip': "Skip",
        'test_sending': "📨 Sending the test book to <code>{email}</code>…",
        'test_sent': (
            "📨 Test book sent to <code>{email}</code>.\n\n"
            "Did it arrive on your Kindle? It can take a few minutes."),
        'test_failed': (
            "😕 I couldn't send the test book: my mail server didn't accept it. That's on my side. "
            "Please try again in a moment."),
        'test_no_email': "Set your Kindle address first.",
        'btn_arrived': "🎉 Yes, it's there",
        'btn_not_arrived': "😕 No",
        'btn_try_again': "🔁 Try again",
        'test_arrived': "✅ The test book arrived.",
        'setup_done': (
            "🎉 <b>All set!</b> Send me any article link and it goes straight to your Kindle.\n\n"
            "<b>Tip:</b> in your browser or reading app, tap <i>Share → Telegram</i> and pick this chat."),
        'setup_skipped': (
            "👍 Saved. Send me any article link and it goes to your Kindle. If nothing arrives, run the "
            "test from /settings."),
        'troubleshoot': (
            "No problem, it's usually one of these:\n"
            "<blockquote expandable>"
            "1. <code>{sender}</code> isn't on your approved sender list yet, or has a typo.\n"
            "2. The Kindle address <code>{email}</code> is wrong. Compare it with "
            "<i>Amazon → Devices → your Kindle → Email</i>.\n"
            "3. Amazon rejected the book. Look for an email from Amazon in the inbox of your Amazon "
            "account.\n"
            "4. Amazon is slow today. It can take up to 10 minutes."
            "</blockquote>"),
        'offer_pending': "Want “{title}” on your Kindle too?",
        'btn_send_to_kindle': "📚 Send it to Kindle",

        # Messages that aren't links
        'no_link': "Send me a link to an article and I'll turn it into a book. 📚",
        'cancelled': "Okay, cancelled.",
        'too_many_links': "I found {count} links. I'll send the first {max}.",

        # Delivery progress
        'status_queued': "🕐 Waiting for a free slot…",
        'status_fetching': "⏳ Fetching the article…",
        'status_building': "📖 Building the book…",
        'status_sending': "📧 Sending to your Kindle…",
        'status_uploading': "📥 Uploading the file…",

        # Result card
        'card_by': "by {author}",
        'card_read_time': "~{minutes} min read",
        'card_preview': "🔒 Paywalled: only the free preview is included.",
        'footer_kindle': "✅ Sent to your Kindle. It usually shows up within a few minutes.",
        'footer_both': "✅ Also sent to your Kindle.",
        'footer_telegram': "📥 Open it with any e-book app.",
        'btn_original': "🔗 Original",
        'btn_full_post': "🔒 Read full post",
        'btn_epub_here': "📥 EPUB here",
        'btn_resend': "🔁 Resend",
        'btn_retry': "🔁 Retry",
        'btn_open_link': "🔗 Open link",
        'btn_send_again': "🔁 Send again",
        'duplicate': "📚 You already got “{title}” on {date}.",
        'file_too_big': "⚠️ The EPUB is {size}, more than Telegram allows bots to send (50 MB).",
        'article_gone': "I can't find this book any more.",

        # Errors
        'err_fetch': "😕 I couldn't load this page.",
        'err_blocked': "🚫 This site blocks automated readers, so I couldn't get the article.",
        'err_extract': "🤷 I loaded the page but couldn't find any article text in it.",
        'err_email': (
            "📧 My mail server didn't accept the book. That's on my side, not yours. "
            "Please retry in a moment."),
        'err_unknown': "💥 Something went wrong on my side. The developer has been notified.",

        # Settings
        'settings': (
            "<b>⚙️ Settings</b>\n\n"
            "📧 Kindle: {email}\n"
            "📬 Delivery: {delivery}\n"
            "🖼 Image links: {links}\n"
            "<i>On: tap a picture on your Kindle to open the full-size version online.</i>\n"
            "🌐 Language: {language}"),
        'not_set': "<i>not set</i>",
        'delivery_kindle': "Kindle",
        'delivery_telegram': "this chat (EPUB file)",
        'delivery_both': "Kindle + this chat",
        'mode_kindle': "📚 Kindle",
        'mode_telegram': "📥 Chat",
        'mode_both': "📚+📥 Both",
        'on': "on",
        'off': "off",
        'btn_set_email': "📧 Set Kindle address",
        'btn_links': "🖼 Image links: {state}",
        'btn_delete_data': "🗑 Delete my data",
        'toast_saved': "Saved ✓",
        'toast_need_email': "Set your Kindle address first.",
        'delete_confirm': (
            "🗑 <b>Delete all your data?</b>\n\n"
            "This removes your Kindle address, your settings and your history from the bot. "
            "Books already on your Kindle stay there."),
        'btn_delete_yes': "Yes, delete everything",
        'btn_cancel': "Cancel",
        'deleted': "🗑 Done, everything is deleted. Send /start whenever you want to come back.",

        # History
        'history_title': "<b>📜 Your books</b> ({start}–{end} of {total})",
        'history_empty': "No books yet. Send me a link to get started!",
        'history_hint': "Tap a number to send that book again.",

        # Help & privacy
        'help': (
            "<b>❓ How to use me</b>\n\n"
            "<b>Send a link.</b> Paste it, or use <i>Share → Telegram</i> in your browser or app. "
            "Forwarded posts work too, including hyperlinked text and links in photo captions. Up to "
            "{max} links per message.\n\n"
            "<b>What works:</b> Substack, Medium and most news sites and blogs. For paywalled posts "
            "you get the free preview.\n\n"
            "<b>From any chat:</b> reply to a message that contains a link and mention @{bot}. "
            "I'll send the article to your Kindle and confirm here.\n\n"
            "<b>Nothing arrived?</b> Check that <code>{sender}</code> is on your Amazon approved "
            "sender list, then send a test book from /settings.\n\n"
            "/settings: Kindle address, delivery, image links, language\n"
            "/history: your recent books\n"
            "/privacy: what's stored, delete your data"),
        'privacy': (
            "<b>🔒 Privacy</b>\n\n"
            "<b>What I store:</b> your Telegram ID and name, your Kindle address, your settings, and "
            "the links and titles of articles you sent me (your /history).\n\n"
            "<b>Who sees it:</b> the bot's operator gets a notice with the title of each book and who "
            "requested it, and error reports for failed links.\n\n"
            "<b>Files:</b> generated EPUBs are kept on the server for a while so they can be resent, "
            "and deleted automatically when space runs low.\n\n"
            "You can delete everything at any time:"),

        # Guest mode
        'guest_title': "Send to Kindle",
        'guest_sending': "📚 Got it, {name}! I'll deliver the book and confirm in our private chat.",
        'guest_no_link': "📚 Reply to a message with a link and mention me, and I'll send the article to your Kindle.",
        'guest_not_setup': "📚 Set me up in a private chat first, then I can send articles to your Kindle.",
        'btn_guest_setup': "📚 Set up",

        # Test book
        'test_book_title': "Your Kindle setup works!",
        'test_book_body': (
            "<h1>It works! 🎉</h1>"
            "<p>This test book was sent by @{bot}. From now on, every article link you send me will show "
            "up here.</p>"
            "<p>Tip: in your browser or reading app, tap <i>Share → Telegram</i> and pick the bot's "
            "chat.</p>"),

        # PocketBook versions of Kindle texts, picked by for_device() for @pbsync.com addresses.
        # PocketBook has no sender list to fill in: the first book from a new sender makes PocketBook
        # email the owner, who confirms the sender there.
        'setup_step2_pocketbook': (
            "<b>Step 2 of 3 · Allow my address</b>\n\n"
            "✅ Saved: <code>{email}</code> (PocketBook)\n\n"
            "PocketBook only accepts books from trusted senders. When my first book arrives, PocketBook "
            "emails you (at your PocketBook account's address) and asks whether to trust\n\n"
            "<code>{sender}</code>\n\n"
            "Confirm it in that email and the book goes to your reader."),
        'btn_got_it': "✅ Got it",
        'setup_step3_pocketbook': (
            "<b>Step 3 of 3 · Test it</b>\n\n"
            "I'll send a tiny test book to <code>{email}</code>. Confirm my address in PocketBook's email. "
            "The book then lands in the <i>Send-to-PocketBook</i> folder the next time your reader is online."),
        'test_sent_pocketbook': (
            "📨 Test book sent to <code>{email}</code>.\n\n"
            "If PocketBook emailed you about a new sender, confirm it. Did the book arrive on your "
            "PocketBook? It shows up once the reader has synced over Wi-Fi."),
        'setup_done_pocketbook': (
            "🎉 <b>All set!</b> Send me any article link and it goes straight to your PocketBook.\n\n"
            "<b>Tip:</b> in your browser or reading app, tap <i>Share → Telegram</i> and pick this chat."),
        'setup_skipped_pocketbook': (
            "👍 Saved. Send me any article link and it goes to your PocketBook. If nothing arrives, run the "
            "test from /settings."),
        'troubleshoot_pocketbook': (
            "No problem, it's usually one of these:\n"
            "<blockquote expandable>"
            "1. You haven't confirmed <code>{sender}</code> yet. Look for an email from PocketBook in the "
            "inbox of your PocketBook account, and in spam.\n"
            "2. The address <code>{email}</code> is wrong. Compare it with <i>Settings → Accounts and "
            "synchronization → Send-to-PocketBook</i> on your reader.\n"
            "3. Your reader hasn't synced yet. Connect it to Wi-Fi and open the <i>Send-to-PocketBook</i> "
            "folder."
            "</blockquote>"),
        'target_kindle_pocketbook': "your PocketBook",
        'target_both_pocketbook': "your PocketBook and this chat",
        'status_sending_pocketbook': "📧 Sending to your PocketBook…",
        'footer_kindle_pocketbook': "✅ Sent to your PocketBook. It shows up the next time your reader syncs.",
        'footer_both_pocketbook': "✅ Also sent to your PocketBook.",
        'offer_pending_pocketbook': "Want “{title}” on your PocketBook too?",
        'btn_send_to_kindle_pocketbook': "📖 Send it to PocketBook",
        'test_book_title_pocketbook': "Your PocketBook setup works!",

        'months': "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec",
    },

    'de': {
        'bot_description': (
            "Schick mir einen Link zu einem Artikel (Substack, Medium, Nachrichtenseiten, Blogs) und ich "
            "mache daraus ein sauberes E-Book und schicke es an deinen Kindle oder als EPUB-Datei hierher."),
        'bot_short_description': "Artikel aus dem Web → E-Books auf deinem Kindle. Schick einfach einen Link.",
        'cmd_start': "Starten und einrichten",
        'cmd_settings': "Kindle-Adresse, Zustellung, Sprache",
        'cmd_history': "Deine letzten Bücher",
        'cmd_help': "So funktioniert der Bot",
        'cmd_privacy': "Gespeicherte Daten, Daten löschen",

        'start_new': (
            "👋 Hallo {name}! Ich mache aus Web-Artikeln E-Books.\n\n"
            "Schick mir einen Link von Substack, Medium oder fast jeder anderen Website und ich schicke "
            "ihn an deinen <b>Kindle</b> oder direkt hier in den Chat als <b>EPUB-Datei</b>."),
        'start_ready': "📚 Bereit! Schick mir einen Artikel-Link und ich liefere ihn an {target}.",
        'target_kindle': "deinen Kindle",
        'target_telegram': "diesen Chat",
        'target_both': "deinen Kindle und diesen Chat",
        'btn_setup_kindle': "📚 Kindle einrichten",
        'btn_epub_only': "📥 Nur EPUB-Dateien schicken",
        'btn_settings': "⚙️ Einstellungen",
        'btn_help': "❓ Hilfe",
        'epub_only_set': (
            "👍 Erledigt. Ich schicke Bücher als EPUB-Datei hierher. Schick mir einen Link zum "
            "Ausprobieren.\n\nIn /settings kannst du jederzeit auf Kindle-Zustellung umstellen."),

        'setup_step1': (
            "<b>Schritt 1 von 3 · Deine Kindle-Adresse</b>\n\n"
            "Schick mir die E-Mail-Adresse deines Kindle. Wähle auf deiner "
            "<a href=\"{url}\">Amazon-Geräteseite</a> deinen Kindle aus und schau unter <i>E-Mail</i>. "
            "Sie endet auf <code>@kindle.com</code>.\n\n"
            "<i>Du liest auf einem PocketBook? Dann schick mir stattdessen seine Send-to-PocketBook-Adresse, "
            "die auf <code>@pbsync.com</code> endet.</i>"),
        'setup_step1_current': (
            "<b>Deine Kindle-Adresse</b>\n\n"
            "Aktuell: <code>{email}</code>\n\nSchick mir eine neue Adresse, um sie zu ändern, oder /cancel."),
        'email_placeholder': "name_ab12@kindle.com",
        'email_invalid': (
            "Das sieht nicht nach einer Kindle-Adresse aus. Sie endet auf <code>@kindle.com</code>, z. B. "
            "<code>name_ab12@kindle.com</code> (oder <code>@pbsync.com</code> bei einem PocketBook). Versuch es noch "
            "einmal oder /cancel."),
        'email_not_kindle': (
            "<code>{email}</code> ist eine normale E-Mail-Adresse. Dein Kindle hat eine eigene "
            "„An Kindle senden“-Adresse, die auf <code>@kindle.com</code> endet: Wähle auf deiner "
            "<a href=\"{url}\">Amazon-Geräteseite</a> deinen Kindle aus und schau unter <i>E-Mail</i>. "
            "Bei einem PocketBook endet "
            "sie auf "
            "<code>@pbsync.com</code>. Versuch es noch einmal oder /cancel."),

        'setup_step2': (
            "<b>Schritt 2 von 3 · Meine Adresse freigeben</b>\n\n"
            "✅ Gespeichert: <code>{email}</code>\n\n"
            "Amazon nimmt nur Bücher von freigegebenen Absendern an. Füge diese Adresse zur "
            "<i>Liste genehmigter E-Mail-Adressen für persönliche Dokumente</i> hinzu:\n\n"
            "<code>{sender}</code>\n\n"
            "Scroll auf Amazons <i>Einstellungen</i>-Seite nach unten zu <i>Einstellungen für persönliche "
            "Dokumente</i>."),
        'btn_copy_sender': "📋 Adresse kopieren",
        'btn_open_amazon': "🔗 Amazon-Einstellungen öffnen ({store})",
        'btn_other_store': "🌍 Anderer Amazon-Shop",
        'btn_amazon_store': "🛒 Amazon-Shop: {store}",
        'btn_back': "← Zurück",
        'btn_change_email': "✏️ Adresse ändern",
        'btn_sender_added': "✅ Hab ich hinzugefügt",

        'setup_step3': (
            "<b>Schritt 3 von 3 · Testen</b>\n\n"
            "Ich schicke ein kleines Testbuch an <code>{email}</code>. Es sollte in ein paar Minuten auf "
            "deinem Kindle erscheinen."),
        'btn_send_test': "📨 Testbuch senden",
        'btn_skip': "Überspringen",
        'test_sending': "📨 Schicke das Testbuch an <code>{email}</code>…",
        'test_sent': (
            "📨 Testbuch an <code>{email}</code> geschickt.\n\n"
            "Ist es auf deinem Kindle angekommen? Das kann ein paar Minuten dauern."),
        'test_failed': (
            "😕 Ich konnte das Testbuch nicht senden: Mein Mailserver hat es nicht angenommen. Das liegt an "
            "mir. Bitte versuch es gleich noch einmal."),
        'test_no_email': "Hinterlege zuerst deine Kindle-Adresse.",
        'btn_arrived': "🎉 Ja, ist da",
        'btn_not_arrived': "😕 Nein",
        'btn_try_again': "🔁 Nochmal versuchen",
        'test_arrived': "✅ Das Testbuch ist angekommen.",
        'setup_done': (
            "🎉 <b>Alles bereit!</b> Schick mir einen Artikel-Link und er landet direkt auf deinem Kindle.\n\n"
            "<b>Tipp:</b> Tippe im Browser oder in deiner Lese-App auf <i>Teilen → Telegram</i> und wähle "
            "diesen Chat."),
        'setup_skipped': (
            "👍 Gespeichert. Schick mir einen Artikel-Link und er geht an deinen Kindle. Falls nichts "
            "ankommt, starte den Test in /settings."),
        'troubleshoot': (
            "Kein Problem, meistens ist es eins davon:\n"
            "<blockquote expandable>"
            "1. <code>{sender}</code> steht noch nicht auf deiner Liste freigegebener Absender oder hat "
            "einen Tippfehler.\n"
            "2. Die Kindle-Adresse <code>{email}</code> stimmt nicht. Vergleiche sie mit "
            "<i>Amazon → Geräte → dein Kindle → E-Mail</i>.\n"
            "3. Amazon hat das Buch abgelehnt. Schau im Posteingang deines Amazon-Kontos nach einer "
            "E-Mail von Amazon.\n"
            "4. Amazon ist heute langsam. Es kann bis zu 10 Minuten dauern."
            "</blockquote>"),
        'offer_pending': "Möchtest du „{title}“ auch auf deinem Kindle?",
        'btn_send_to_kindle': "📚 An Kindle senden",

        'no_link': "Schick mir einen Link zu einem Artikel und ich mache ein Buch daraus. 📚",
        'cancelled': "Okay, abgebrochen.",
        'too_many_links': "Ich habe {count} Links gefunden. Ich schicke die ersten {max}.",

        'status_queued': "🕐 Warte auf einen freien Platz…",
        'status_fetching': "⏳ Lade den Artikel…",
        'status_building': "📖 Baue das Buch…",
        'status_sending': "📧 Schicke es an deinen Kindle…",
        'status_uploading': "📥 Lade die Datei hoch…",

        'card_by': "von {author}",
        'card_read_time': "~{minutes} Min. Lesezeit",
        'card_preview': "🔒 Bezahlschranke: Nur die kostenlose Vorschau ist enthalten.",
        'footer_kindle': "✅ An deinen Kindle geschickt. Es erscheint meist innerhalb weniger Minuten.",
        'footer_both': "✅ Auch an deinen Kindle geschickt.",
        'footer_telegram': "📥 Öffne die Datei mit einer beliebigen E-Book-App.",
        'btn_original': "🔗 Original",
        'btn_full_post': "🔒 Ganzen Beitrag lesen",
        'btn_epub_here': "📥 EPUB hierher",
        'btn_resend': "🔁 Nochmal senden",
        'btn_retry': "🔁 Nochmal versuchen",
        'btn_open_link': "🔗 Link öffnen",
        'btn_send_again': "🔁 Nochmal senden",
        'duplicate': "📚 Du hast „{title}“ schon am {date} bekommen.",
        'file_too_big': "⚠️ Die EPUB-Datei ist {size} groß, mehr als Telegram Bots erlaubt (50 MB).",
        'article_gone': "Dieses Buch finde ich nicht mehr.",

        'err_fetch': "😕 Ich konnte diese Seite nicht laden.",
        'err_blocked': "🚫 Diese Website sperrt automatische Leser, deshalb kam ich nicht an den Artikel.",
        'err_extract': "🤷 Die Seite hat geladen, aber ich habe keinen Artikeltext darin gefunden.",
        'err_email': (
            "📧 Mein Mailserver hat das Buch nicht angenommen. Das liegt an mir, nicht an dir. "
            "Bitte versuch es gleich noch einmal."),
        'err_unknown': "💥 Bei mir ist etwas schiefgelaufen. Der Entwickler wurde benachrichtigt.",

        'settings': (
            "<b>⚙️ Einstellungen</b>\n\n"
            "📧 Kindle: {email}\n"
            "📬 Zustellung: {delivery}\n"
            "🖼 Bild-Links: {links}\n"
            "<i>An: Tippe auf dem Kindle auf ein Bild, um die große Version online zu öffnen.</i>\n"
            "🌐 Sprache: {language}"),
        'not_set': "<i>nicht gesetzt</i>",
        'delivery_kindle': "Kindle",
        'delivery_telegram': "dieser Chat (EPUB-Datei)",
        'delivery_both': "Kindle + dieser Chat",
        'mode_kindle': "📚 Kindle",
        'mode_telegram': "📥 Chat",
        'mode_both': "📚+📥 Beides",
        'on': "an",
        'off': "aus",
        'btn_set_email': "📧 Kindle-Adresse festlegen",
        'btn_links': "🖼 Bild-Links: {state}",
        'btn_delete_data': "🗑 Meine Daten löschen",
        'toast_saved': "Gespeichert ✓",
        'toast_need_email': "Hinterlege zuerst deine Kindle-Adresse.",
        'delete_confirm': (
            "🗑 <b>Alle deine Daten löschen?</b>\n\n"
            "Das entfernt deine Kindle-Adresse, deine Einstellungen und deinen Verlauf aus dem Bot. "
            "Bücher auf deinem Kindle bleiben dort."),
        'btn_delete_yes': "Ja, alles löschen",
        'btn_cancel': "Abbrechen",
        'deleted': "🗑 Erledigt, alles ist gelöscht. Schick /start, wenn du wiederkommen möchtest.",

        'history_title': "<b>📜 Deine Bücher</b> ({start}–{end} von {total})",
        'history_empty': "Noch keine Bücher. Schick mir einen Link, um loszulegen!",
        'history_hint': "Tippe auf eine Nummer, um das Buch nochmal zu senden.",

        'help': (
            "<b>❓ So funktioniert's</b>\n\n"
            "<b>Schick einen Link.</b> Füge ihn ein oder nutze <i>Teilen → Telegram</i> im Browser oder in "
            "einer App. Weitergeleitete Beiträge gehen auch, inklusive verlinktem Text und Links in "
            "Bildunterschriften. Bis zu {max} Links pro Nachricht.\n\n"
            "<b>Was funktioniert:</b> Substack, Medium und die meisten Nachrichtenseiten und Blogs. Bei "
            "Bezahl-Beiträgen bekommst du die kostenlose Vorschau.\n\n"
            "<b>Aus jedem Chat:</b> Antworte auf eine Nachricht mit Link und erwähne @{bot}. Ich schicke "
            "den Artikel an deinen Kindle und bestätige es hier.\n\n"
            "<b>Nichts angekommen?</b> Prüfe, ob <code>{sender}</code> bei Amazon als Absender freigegeben "
            "ist, und schick dann ein Testbuch über /settings.\n\n"
            "/settings: Kindle-Adresse, Zustellung, Bild-Links, Sprache\n"
            "/history: deine letzten Bücher\n"
            "/privacy: gespeicherte Daten, Daten löschen"),
        'privacy': (
            "<b>🔒 Datenschutz</b>\n\n"
            "<b>Was ich speichere:</b> deine Telegram-ID und deinen Namen, deine Kindle-Adresse, deine "
            "Einstellungen sowie Links und Titel der Artikel, die du mir geschickt hast (dein /history).\n\n"
            "<b>Wer das sieht:</b> Der Betreiber des Bots bekommt eine Nachricht mit dem Titel jedes Buchs "
            "und wer es angefordert hat, sowie Fehlerberichte zu fehlgeschlagenen Links.\n\n"
            "<b>Dateien:</b> Erzeugte EPUBs bleiben eine Weile auf dem Server, damit sie erneut gesendet "
            "werden können, und werden automatisch gelöscht, wenn der Speicher knapp wird.\n\n"
            "Du kannst jederzeit alles löschen:"),

        'guest_title': "An Kindle senden",
        'guest_sending': "📚 Alles klar, {name}! Ich liefere das Buch und bestätige es in unserem privaten Chat.",
        'guest_no_link': "📚 Antworte auf eine Nachricht mit Link und erwähne mich, dann schicke ich den Artikel an deinen Kindle.",
        'guest_not_setup': "📚 Richte mich zuerst in einem privaten Chat ein, dann kann ich Artikel an deinen Kindle schicken.",
        'btn_guest_setup': "📚 Einrichten",

        'test_book_title': "Deine Kindle-Einrichtung funktioniert!",
        'test_book_body': (
            "<h1>Es funktioniert! 🎉</h1>"
            "<p>Dieses Testbuch hat @{bot} geschickt. Ab jetzt landet hier jeder Artikel-Link, den du mir "
            "schickst.</p>"
            "<p>Tipp: Tippe im Browser oder in deiner Lese-App auf <i>Teilen → Telegram</i> und wähle den "
            "Chat mit dem Bot.</p>"),

        'setup_step2_pocketbook': (
            "<b>Schritt 2 von 3 · Meine Adresse freigeben</b>\n\n"
            "✅ Gespeichert: <code>{email}</code> (PocketBook)\n\n"
            "PocketBook nimmt nur Bücher von vertrauenswürdigen Absendern an. Wenn mein erstes Buch ankommt, "
            "schreibt dir PocketBook (an die Adresse deines PocketBook-Kontos) und fragt, ob es\n\n"
            "<code>{sender}</code>\n\n"
            "vertrauen soll. Bestätige das in dieser E-Mail und das Buch geht an deinen Reader."),
        'btn_got_it': "✅ Verstanden",
        'setup_step3_pocketbook': (
            "<b>Schritt 3 von 3 · Testen</b>\n\n"
            "Ich schicke ein kleines Testbuch an <code>{email}</code>. Bestätige meine Adresse in der E-Mail "
            "von PocketBook. Das Buch landet dann im Ordner <i>Send-to-PocketBook</i>, sobald dein Reader "
            "online ist."),
        'test_sent_pocketbook': (
            "📨 Testbuch an <code>{email}</code> geschickt.\n\n"
            "Falls PocketBook dir wegen eines neuen Absenders geschrieben hat, bestätige ihn. Ist das Buch "
            "auf deinem PocketBook angekommen? Es erscheint, sobald der Reader über WLAN synchronisiert hat."),
        'setup_done_pocketbook': (
            "🎉 <b>Alles bereit!</b> Schick mir einen Artikel-Link und er landet direkt auf deinem "
            "PocketBook.\n\n"
            "<b>Tipp:</b> Tippe im Browser oder in deiner Lese-App auf <i>Teilen → Telegram</i> und wähle "
            "diesen Chat."),
        'setup_skipped_pocketbook': (
            "👍 Gespeichert. Schick mir einen Artikel-Link und er geht an dein PocketBook. Falls nichts "
            "ankommt, starte den Test in /settings."),
        'troubleshoot_pocketbook': (
            "Kein Problem, meistens ist es eins davon:\n"
            "<blockquote expandable>"
            "1. Du hast <code>{sender}</code> noch nicht bestätigt. Schau im Posteingang deines "
            "PocketBook-Kontos nach einer E-Mail von PocketBook, auch im Spam.\n"
            "2. Die Adresse <code>{email}</code> stimmt nicht. Vergleiche sie auf deinem Reader mit "
            "<i>Einstellungen → Konten und Synchronisierung → Send-to-PocketBook</i>.\n"
            "3. Dein Reader hat noch nicht synchronisiert. Verbinde ihn mit dem WLAN und öffne den Ordner "
            "<i>Send-to-PocketBook</i>."
            "</blockquote>"),
        'target_kindle_pocketbook': "dein PocketBook",
        'target_both_pocketbook': "dein PocketBook und diesen Chat",
        'status_sending_pocketbook': "📧 Sende an dein PocketBook…",
        'footer_kindle_pocketbook': "✅ An dein PocketBook geschickt. Es erscheint, sobald dein Reader synchronisiert.",
        'footer_both_pocketbook': "✅ Auch an dein PocketBook geschickt.",
        'offer_pending_pocketbook': "Möchtest du „{title}“ auch auf deinem PocketBook?",
        'btn_send_to_kindle_pocketbook': "📖 An PocketBook senden",
        'test_book_title_pocketbook': "Deine PocketBook-Einrichtung funktioniert!",

        'months': "Jan. Feb. März Apr. Mai Juni Juli Aug. Sep. Okt. Nov. Dez.",
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    """The text for `key` in `lang` (falling back to English), with HTML-escaped arguments."""
    template = TEXTS.get(lang, {}).get(key) or TEXTS[DEFAULT_LANGUAGE][key]
    if not kwargs:
        return template
    values = {name: value if isinstance(value, Raw) else escape(str(value), quote=False)
              for name, value in kwargs.items()}
    return template.format(**values)


def for_device(key: str, address: str | None) -> str:
    """`key`, or its PocketBook version when `address` is a PocketBook address and that version exists.
    Kindle stays the default wording everywhere; only texts that would be wrong for a PocketBook differ."""
    if device_of(address) == POCKETBOOK and f'{key}_pocketbook' in TEXTS[DEFAULT_LANGUAGE]:
        return f'{key}_pocketbook'
    return key


def resolve_lang(user=None, tg_user=None) -> str:
    """The language the user picked in /settings, else their Telegram app language, else English."""
    if user is not None and getattr(user, 'language', None) in LANGUAGES:
        return user.language
    code = (getattr(tg_user, 'language_code', None) or '').lower()
    return 'de' if code.startswith('de') else DEFAULT_LANGUAGE


def format_size(lang: str, size: int) -> str:
    if size < 1024 * 1024:
        return f"{max(1, round(size / 1024))} KB"
    value = f"{size / (1024 * 1024):.1f}"
    return f"{value.replace('.', ',') if lang == 'de' else value} MB"


def format_date(lang: str, value) -> str:
    """'3 Nov 2026' / '3. Nov. 2026'"""
    month = t(lang, 'months').split()[value.month - 1]
    return f"{value.day}. {month} {value.year}" if lang == 'de' else f"{value.day} {month} {value.year}"
