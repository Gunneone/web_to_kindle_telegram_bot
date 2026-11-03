#!/usr/bin/env python3
"""
Offline tests for article extraction and EPUB conversion.

The HTML snippets reproduce the markup patterns found on real sites during the site survey
(see docs/site-compatibility.md) without copying any article content. No network access needed.
"""

import base64
import io
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from bs4 import BeautifulSoup
from PIL import Image

from web_scraper import Article, ExtractionError, MediumScraper, SubstackScraper, extract_url, normalize_url
from web_scraper.generic_scraper import GenericScraper
from web_scraper.html_cleanup import (best_srcset_url, promote_lazy_images, reveal_streamed_content,
                                      sanitize_for_kindle, strip_leading_title)
from requests.structures import CaseInsensitiveDict
from web_scraper.http import FetchResult, _meta_refresh_target, decode_html
from web_scraper.metadata import clean_title, extract_metadata, normalize_language, parse_date

PARAGRAPHS = ''.join(f'<p>Paragraph {i} of the article body, long enough to count as real prose for the '
                     f'extractor, with a few more words here and there to make it look natural.</p>'
                     for i in range(12))

SUBSTACK_PAGE = """<html lang="en"><head>
<meta name="author" content="Jane Writer">
<meta property="og:title" content="The Big Essay">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"NewsArticle",
 "headline":"The Big Essay","author":[{"@type":"Person","name":"Jane Writer"}],
 "datePublished":"2025-07-17T07:45:56+00:00","isAccessibleForFree":%(free)s,
 "publisher":{"@type":"Organization","name":"Thinking Out Loud"}}</script>
<link rel="preconnect" href="https://substackcdn.com"></head><body>
<article class="typography newsletter-post post">
 <div class="post-header"><h1 class="post-title">The Big Essay</h1><h3 class="subtitle">A subtitle</h3>
  <div class="pencraft pc-display-flex">Jane Writer Jul 17, 2025 264 Share</div></div>
 <div class="available-content"><div class="body markup">
  %(body)s
  <div class="captioned-image-container"><figure><a class="image-link" href="https://substackcdn.com/full.png">
   <div class="image2-inset"><picture>
    <source type="image/webp" srcset="https://substackcdn.com/image/fetch/w_424,f_webp/a.png 424w, https://substackcdn.com/image/fetch/w_1456,f_webp/a.png 1456w">
    <img src="https://substackcdn.com/image/fetch/w_1456,f_auto/a.png" srcset="https://substackcdn.com/image/fetch/w_424,f_auto/a.png 424w, https://substackcdn.com/image/fetch/w_1456,f_auto/a.png 1456w">
   </picture><div class="image-link-expand"><button>expand</button></div></div></a>
   <figcaption>A chart</figcaption></figure></div>
  <div class="subscription-widget-wrap"><p>Thanks for reading! Subscribe for free.</p>
   <form><input type="email"><button>Subscribe</button></form></div>
  <div class="youtube-wrap"><iframe src="https://www.youtube-nocookie.com/embed/abc"></iframe></div>
 </div></div>
 %(paywall)s
</article></body></html>"""

BLOG_WITH_SITE_HEADER = """<html lang="en-US"><head>
<meta property="og:title" content="Learning a few things about running SQLite">
<meta property="og:site_name" content="Julia Evans">
<title>Learning a few things about running SQLite | Julia Evans</title></head><body>
<header><h1><a href="/">Julia Evans</a></h1><nav><a href="/about">About</a></nav></header>
<main><article><h2>Learning a few things about running SQLite</h2>
<time datetime="2026-07-17">July 17</time>""" + PARAGRAPHS + """</article></main></body></html>"""

NEWS_WITH_LAZY_IMAGES = """<html lang="en-GB"><head>
<meta property="og:title" content="Inside the offensive">
<meta property="og:site_name" content="BBC News">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"NewsArticle",
 "headline":"Inside the offensive","datePublished":"2026-10-16T05:00:00Z",
 "author":[{"@type":"Person","name":"Dan Reporter"}],"publisher":{"@type":"Organization","name":"BBC"}}</script>
</head><body><article>
<figure><span class="Placeholder"><picture>
 <source type="image/webp" srcset="https://ichef.example/240/a.jpg.webp 240w, https://ichef.example/976/a.jpg.webp 976w">
 <img src="https://ichef.example/240/a.jpg" srcset="https://ichef.example/240/a.jpg 240w, https://ichef.example/976/a.jpg 976w" alt="Soldiers">
</picture></span><figcaption>Soldiers at the front</figcaption></figure>
""" + PARAGRAPHS + """
<figure><img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=" data-src="/images/b.jpg" alt="Drone"></figure>
""" + PARAGRAPHS + """
<div class="modal" role="dialog"><p>In order to comment you need to be a member.</p></div>
</article></body></html>"""

MEDIUM_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:content="http://purl.org/rss/1.0/modules/content/" version="2.0">
<channel><title><![CDATA[Netflix TechBlog - Medium]]></title>
<item><title><![CDATA[Other post]]></title><guid isPermaLink="false">https://medium.com/p/111111111111</guid>
<content:encoded><![CDATA[<p>Other</p>]]></content:encoded></item>
<item><title><![CDATA[Measuring Things]]></title><guid isPermaLink="false">https://medium.com/p/4c26be3a4d96</guid>
<dc:creator><![CDATA[Netflix Technology Blog]]></dc:creator><pubDate>Tue, 14 Oct 2026 18:01:02 GMT</pubDate>
<content:encoded><![CDATA[<h3>Measuring Things</h3><p>Body text of the post.</p>
<figure><img alt="" src="https://cdn-images-1.medium.com/max/1024/1*abc.png" /></figure>
<p><a href="https://netflixtechblog.com/x">Continue reading on Netflix TechBlog »</a></p>
<img src="https://medium.com/_/stat?event=post.clientViewed&referrerSource=full_rss&postId=4c26be3a4d96" width="1" height="1" alt="">]]></content:encoded>
</item></channel></rss>"""


def data_uri(image_format: str, size=(64, 32), mode='RGB') -> str:
    buffer = io.BytesIO()
    Image.new(mode, size, (200, 30, 30) if mode == 'RGB' else (200, 30, 30, 128)).save(buffer, image_format)
    return f'data:image/{image_format.lower()};base64,' + base64.b64encode(buffer.getvalue()).decode()


class TestMetadata(unittest.TestCase):

    def test_json_ld_author_date_publisher(self):
        meta = extract_metadata(NEWS_WITH_LAZY_IMAGES, 'https://www.bbc.co.uk/news/articles/x')
        self.assertEqual(meta.author, 'Dan Reporter')
        self.assertEqual(meta.published, '2026-10-16')
        self.assertEqual(meta.site_name, 'BBC News')
        self.assertEqual(meta.language, 'en-GB')

    def test_og_title_wins_over_site_header_h1(self):
        meta = extract_metadata(BLOG_WITH_SITE_HEADER, 'https://jvns.ca/blog/2026/07/17/sqlite/')
        self.assertEqual(meta.title, 'Learning a few things about running SQLite')

    def test_site_suffix_is_stripped(self):
        self.assertEqual(clean_title('Cat-Belling Problems — LessWrong', 'LessWrong', 'https://www.lesswrong.com/p'),
                         'Cat-Belling Problems')
        self.assertEqual(clean_title('Intent to Ship: JPEG XL – Mozilla Hacks - the Web developer blog',
                                     'Mozilla Hacks – the Web developer blog', 'https://hacks.mozilla.org/x'),
                         'Intent to Ship: JPEG XL')
        self.assertEqual(clean_title('Zimbabwean author denies using AI | The Guardian', None,
                                     'https://www.theguardian.com/x'), 'Zimbabwean author denies using AI')
        self.assertEqual(clean_title('Fridtjof Nansen - Wikipedia', None, 'https://en.wikipedia.org/wiki/Nansen'),
                         'Fridtjof Nansen')
        # Colons and hyphens inside the title are not separators
        self.assertEqual(clean_title('Pt3: The Status Wars of Apes', 'Knowingless', 'https://aella.substack.com/p'),
                         'Pt3: The Status Wars of Apes')

    def test_publisher_name_keeps_leading_by(self):
        html = ('<script type="application/ld+json">{"@type":"NewsArticle","headline":"X",'
                '"author":{"@type":"Person","name":"By Hannah Ritchie"},'
                '"publisher":{"@type":"Organization","name":"By the Numbers"}}</script>')
        meta = extract_metadata(html, 'https://www.sustainabilitybynumbers.com/p/x')
        self.assertEqual(meta.site_name, 'By the Numbers')
        self.assertEqual(meta.author, 'Hannah Ritchie')

    def test_date_formats(self):
        self.assertEqual(parse_date('2026-10-06 10:00:00 +0000 UTC'), '2026-10-06')
        self.assertEqual(parse_date('2025-07-17T07:45:56.679Z'), '2025-07-17')
        self.assertEqual(parse_date('Tue, 14 Oct 2026 18:01:02 GMT'), '2026-10-14')
        self.assertIsNone(parse_date('yesterday'))

    def test_language_normalization(self):
        self.assertEqual(normalize_language('en_US'), 'en-US')
        self.assertEqual(normalize_language('en-EUROPE'), 'en')
        self.assertEqual(normalize_language('DE'), 'de')
        self.assertIsNone(normalize_language('x'))


class TestHtmlHandling(unittest.TestCase):

    def test_utf8_page_without_charset_header(self):
        body = '<html><body><p>A driver’s license — naïve café</p></body></html>'.encode('utf-8')
        self.assertIn('driver’s license — naïve café', decode_html(body, 'text/html'))

    def test_meta_refresh_interstitial_is_detected(self):
        page = FetchResult(url='https://open.substack.com/pub/simonw/p/x', final_url='https://open.substack.com/pub/simonw/p/x',
                           status=200, headers=CaseInsensitiveDict(),
                           html='<head><noscript><META http-equiv="refresh" content="0;URL=https://simonw.substack.com/'
                                'p/x?a=1&#38;triedRedirect=true"></noscript></head>')
        self.assertEqual(_meta_refresh_target(page), 'https://simonw.substack.com/p/x?a=1&triedRedirect=true')
        page.html = '<html><body>' + 'x' * 30000 + '<meta http-equiv="refresh" content="300;url=/same"></body></html>'
        self.assertIsNone(_meta_refresh_target(page))  # auto-reload on a real article page is not a redirect

    def test_meta_charset_is_respected(self):
        body = '<html><head><meta charset="iso-8859-1"></head><body>Grüße</body></html>'.encode('iso-8859-1')
        self.assertIn('Grüße', decode_html(body, 'text/html'))

    def test_lazy_and_picture_images_are_promoted(self):
        soup = BeautifulSoup(NEWS_WITH_LAZY_IMAGES, 'lxml')
        promote_lazy_images(soup)
        sources = [img['src'] for img in soup.find_all('img')]
        self.assertEqual(sources, ['https://ichef.example/976/a.jpg', '/images/b.jpg'])
        self.assertEqual(soup.find_all('picture'), [])

    def test_larger_srcset_candidate_keeps_original_as_fallback(self):
        soup = BeautifulSoup('<img src="/330px.jpg" srcset="/960px.jpg 2x">', 'lxml')
        promote_lazy_images(soup)
        img = BeautifulSoup(sanitize_for_kindle(str(soup), 'https://en.wikipedia.org/wiki/X'), 'lxml').find('img')
        self.assertEqual(img['src'], 'https://en.wikipedia.org/960px.jpg')
        self.assertEqual(img['data-fallback-src'], 'https://en.wikipedia.org/330px.jpg')

    def test_noscript_fallback_replaces_placeholder(self):
        soup = BeautifulSoup('<div><img src="data:image/gif;base64,AAAA"><noscript><img src="/real.jpg"></noscript></div>',
                             'lxml')
        promote_lazy_images(soup)
        self.assertEqual([img['src'] for img in soup.find_all('img')], ['/real.jpg'])

    def test_custom_image_elements_and_template_placeholders(self):
        soup = BeautifulSoup('<div><a-img src="/imgs/ipad.png" alt="iPad"></a-img>'
                             '<amp-img src="https://x/amp.jpg"></amp-img><img src="${image}"></div>', 'lxml')
        promote_lazy_images(soup)
        result = BeautifulSoup(sanitize_for_kindle(str(soup), 'https://www.heise.de/news/x.html'), 'lxml')
        self.assertEqual([img['src'] for img in result.find_all('img')],
                         ['https://www.heise.de/imgs/ipad.png', 'https://x/amp.jpg'])

    def test_streamed_react_chunks_are_revealed(self):
        soup = BeautifulSoup('<body><div id="root"><template id="B:0"></template></div>'
                             '<div hidden id="S:0"><article>' + PARAGRAPHS + '</article></div></body>', 'lxml')
        reveal_streamed_content(soup)
        self.assertIsNone(soup.find('div', id='S:0').get('hidden'))

    def test_srcset_picks_largest_within_limit(self):
        self.assertEqual(best_srcset_url('a.jpg 320w, b.jpg 1400w, c.jpg 3000w'), 'b.jpg')
        self.assertEqual(best_srcset_url('a.jpg 1x, b.jpg 2x'), 'b.jpg')
        self.assertEqual(best_srcset_url('https://x/w_424,c_limit/a.png 424w, https://x/w_848,c_limit/a.png 848w'),
                         'https://x/w_848,c_limit/a.png')

    def test_sanitize_for_kindle(self):
        html = ('<div style="color:red" data-x="1"><img src="/a.png" srcset="/b.png 2x" loading="lazy">'
                '<iframe src="https://www.youtube.com/embed/abc"></iframe><svg><path/></svg>'
                '<button>Share</button><a href="/next">next</a><a href="#fn1">1</a>'
                '<span style="display:none"><math>x</math></span><p id="fn1">note</p>'
                '<img src="https://tombedor.dev/post/"></div>')
        result = sanitize_for_kindle(html, 'https://tombedor.dev/post/')
        soup = BeautifulSoup(result, 'lxml')
        self.assertEqual(soup.find('img').attrs, {'src': 'https://tombedor.dev/a.png'})
        self.assertIsNone(soup.find('iframe'))
        self.assertIn('Embedded video: youtube.com', soup.get_text())
        self.assertIsNone(soup.find('svg'))
        self.assertIsNone(soup.find('button'))
        self.assertIsNone(soup.find('math'))
        self.assertEqual(soup.find('a', string='next')['href'], 'https://tombedor.dev/next')
        self.assertEqual(soup.find('a', string='1')['href'], '#fn1')
        self.assertEqual(soup.find(string='note').parent['id'], 'fn1')
        self.assertIsNone(soup.find('div').get('style'))

    def test_strip_leading_title(self):
        html = '<h2>THE KICKER</h2><h1>My Title</h1><p>Body</p>'
        self.assertNotIn('My Title', strip_leading_title(html, 'My Title'))
        self.assertIn('My Title', strip_leading_title('<p>' + 'word ' * 40 + '</p><h2>My Title</h2>', 'My Title'))


class TestGenericScraper(unittest.TestCase):

    def setUp(self):
        self.cwd = os.getcwd()
        self.tmp = tempfile.mkdtemp()
        os.chdir(self.tmp)

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp)

    def test_blog_title_and_body(self):
        article = GenericScraper().extract_from_html('https://jvns.ca/x', 'https://jvns.ca/x', BLOG_WITH_SITE_HEADER)
        self.assertEqual(article.Title, 'Learning a few things about running SQLite')
        self.assertEqual(article.Published_At, '2026-07-17')
        self.assertIn('Paragraph 11', article.Content)
        self.assertEqual(article.Content.count('Learning a few things about running SQLite'), 1)

    def test_javascript_app_shell_is_rejected(self):
        shell = ('<html><head><title>Subscriptions</title></head><body><nav>Home Chat Activity Explore</nav>'
                 '<div><p>This site requires JavaScript to run correctly. Please turn on JavaScript or unblock '
                 'scripts. Home Subscriptions Chat Activity Explore Profile Create All Listen Paid Saved History '
                 'Sort by Priority Recent Get app</p></div></body></html>')
        with self.assertRaises(ExtractionError):
            GenericScraper().extract_from_html('https://substack.com/inbox', 'https://substack.com/inbox', shell)

    def test_news_images_byline_and_modal(self):
        article = GenericScraper().extract_from_html('https://www.bbc.co.uk/news/articles/x',
                                                     'https://www.bbc.co.uk/news/articles/x', NEWS_WITH_LAZY_IMAGES)
        soup = BeautifulSoup(article.Content, 'lxml')
        self.assertEqual(article.Author, 'Dan Reporter')
        self.assertIn('By Dan Reporter', article.Content)
        self.assertIn('https://ichef.example/976/a.jpg', [img['src'] for img in soup.find_all('img')])
        self.assertNotIn('you need to be a member', article.Content)
        self.assertEqual(article.Language, 'en-GB')


class TestSubstackScraper(unittest.TestCase):

    def setUp(self):
        self.cwd = os.getcwd()
        self.tmp = tempfile.mkdtemp()
        os.chdir(self.tmp)

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp)

    def page(self, free=True):
        return SUBSTACK_PAGE % {'free': 'true' if free else 'false', 'body': PARAGRAPHS,
                                'paywall': '' if free else '<div class="paywall" data-testid="paywall"><h2>Keep reading</h2></div>'}

    def test_detection(self):
        self.assertTrue(SubstackScraper.is_substack_site('https://substack.com/inbox/post/166333070'))
        self.assertTrue(SubstackScraper.is_substack_site('https://open.substack.com/pub/simonw/p/x'))
        self.assertTrue(SubstackScraper.is_substack_site('https://www.astralcodexten.com/p/x', self.page()))
        self.assertFalse(SubstackScraper.is_substack_site('https://www.superhuman.ai/p/x',
                                                          '<html>beehiiv <a href="https://substack.com">x</a></html>'))

    def test_metadata_and_cleanup(self):
        article = SubstackScraper().extract_from_html('https://substack.com/inbox/post/1',
                                                      'https://www.example.com/p/the-big-essay', self.page())
        self.assertEqual(article.URL, 'https://substack.com/inbox/post/1')
        self.assertEqual(article.Title, 'The Big Essay')
        self.assertEqual(article.Author, 'Jane Writer')
        self.assertEqual(article.Publication, 'Thinking Out Loud')
        self.assertEqual(article.Published_At, '2025-07-17')
        self.assertFalse(article.Is_Preview)
        self.assertIn('By Jane Writer', article.Content)
        self.assertIn('From: Thinking Out Loud', article.Content)
        self.assertIn('A subtitle', article.Content)
        self.assertEqual(article.Content.count('The Big Essay'), 1)
        self.assertNotIn('Subscribe for free', article.Content)
        soup = BeautifulSoup(article.Content, 'lxml')
        self.assertEqual([img['src'] for img in soup.find_all('img')],
                         ['https://substackcdn.com/image/fetch/w_1456,f_auto/a.png'])
        self.assertEqual(soup.find_all(['source', 'button', 'form', 'iframe']), [])
        self.assertIn('Embedded video', soup.get_text())

    def test_paid_post_is_marked_as_preview(self):
        article = SubstackScraper().extract_from_html('https://x.substack.com/p/a', 'https://x.substack.com/p/a',
                                                      self.page(free=False))
        self.assertTrue(article.Is_Preview)
        self.assertNotIn('Keep reading', article.Content)


class TestMediumScraper(unittest.TestCase):

    def test_post_id_and_feed_urls(self):
        url = 'https://medium.com/@karpathy/software-2-0-a64152b37c35?source=rss'
        self.assertEqual(MediumScraper.post_id(url), 'a64152b37c35')
        self.assertEqual(MediumScraper.post_id('https://medium.com/p/a64152b37c35'), 'a64152b37c35')
        self.assertIsNone(MediumScraper.post_id('https://example.com/about'))
        self.assertEqual(MediumScraper.feed_urls(url), ['https://medium.com/feed/@karpathy'])
        self.assertEqual(MediumScraper.feed_urls('https://medium.com/engineering-playbook/x-327307fb0bfa'),
                         ['https://medium.com/feed/engineering-playbook'])
        self.assertEqual(MediumScraper.feed_urls('https://karpathy.medium.com/x-a64152b37c35'),
                         ['https://karpathy.medium.com/feed', 'https://medium.com/feed/@karpathy'])
        self.assertEqual(MediumScraper.feed_urls('https://netflixtechblog.com/x-4c26be3a4d96'),
                         ['https://netflixtechblog.com/feed'])

    def test_detection(self):
        self.assertTrue(MediumScraper.is_medium_host('https://uxdesign.medium.com/x'))
        self.assertFalse(MediumScraper.is_medium_host('https://notmedium.com/x'))
        self.assertTrue(MediumScraper.is_medium_html('<meta property="al:ios:app_name" content="Medium">'))

    def test_article_from_feed(self):
        article = MediumScraper().article_from_feed(MEDIUM_FEED, '4c26be3a4d96', 'https://netflixtechblog.com/x-4c26be3a4d96')
        self.assertEqual(article.Title, 'Measuring Things')
        self.assertEqual(article.Author, 'Netflix Technology Blog')
        self.assertEqual(article.Publication, 'Netflix TechBlog')
        self.assertEqual(article.Published_At, '2026-10-14')
        self.assertTrue(article.Is_Preview)  # "Continue reading on ..." marks a member-only preview
        self.assertNotIn('_/stat', article.Content)
        self.assertEqual(article.Content.count('Measuring Things'), 1)
        self.assertIsNone(MediumScraper().article_from_feed(MEDIUM_FEED, 'ffffffffffff', 'https://x'))


class TestUrlUtils(unittest.TestCase):

    def test_extract_url_from_share_text(self):
        self.assertEqual(extract_url('Great read: The Overhang https://www.oneusefulthing.org/p/the-overhang?r=abc.'),
                         'https://www.oneusefulthing.org/p/the-overhang?r=abc')
        self.assertEqual(extract_url('medium.com/@karpathy/software-2-0-a64152b37c35'),
                         'https://medium.com/@karpathy/software-2-0-a64152b37c35')
        self.assertEqual(extract_url('https://en.wikipedia.org/wiki/Python_(programming_language)'),
                         'https://en.wikipedia.org/wiki/Python_(programming_language)')
        self.assertEqual(extract_url('(see https://example.com/post).'), 'https://example.com/post')
        self.assertIsNone(extract_url('hello there'))
        self.assertIsNone(extract_url('me@kindle.com'))

    def test_normalize_url(self):
        self.assertEqual(normalize_url('  www.example.com/x '), 'https://www.example.com/x')
        self.assertEqual(normalize_url('http://example.com'), 'http://example.com')


class TestEpubConverter(unittest.TestCase):

    def setUp(self):
        self.cwd = os.getcwd()
        self.tmp = tempfile.mkdtemp()
        os.chdir(self.tmp)
        import epub_converter
        self.converter = epub_converter

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp)

    def test_images_title_language_and_preview(self):
        webp = data_uri('WEBP', (2400, 1200))
        html = (f'<h1>T</h1><p>Body</p><a href="https://x"><img src="{webp}" alt="big"></a>'
                f'<img src="{webp}" alt="same image again"><img src="{data_uri("PNG", (1, 1))}" alt="">'
                f'<img src="{data_uri("PNG")}" alt="small png">')
        article = Article('https://example.com/a', 'TCP/IP: a "guide"?', 'Jane', '2026-10-01', html,
                          publication='Example', language='de', is_preview=True)
        path = self.converter.convert_to_epub(article)

        self.assertTrue(os.path.exists(path))
        self.assertTrue(path.endswith('tcp-ip-a-guide.epub'))
        with zipfile.ZipFile(path) as epub_zip:
            names = epub_zip.namelist()
            self.assertEqual(len(names), len(set(names)))
            xhtml = epub_zip.read('EPUB/content.xhtml').decode()
            opf = epub_zip.read('EPUB/content.opf').decode()
            soup = BeautifulSoup(xhtml, 'html.parser')
            sources = [img['src'] for img in soup.find_all('img')]
            # Every reference resolves exactly (case-sensitive) to a file in the zip
            self.assertEqual(len(sources), 3)
            for src in sources:
                self.assertIn(f'EPUB/{src}', names)
            self.assertEqual(sources[0], sources[1])  # duplicate image embedded once
            first = Image.open(io.BytesIO(epub_zip.read(f'EPUB/{sources[0]}')))
            self.assertEqual(first.format, 'JPEG')  # WebP converted
            self.assertEqual(first.width, 1600)  # and downscaled
            self.assertIsNone(soup.find('img').find_parent('a'))  # image links removed by default
            self.assertIn('<dc:language>de</dc:language>', opf)
            self.assertIn('full post is for paid subscribers', xhtml)
            self.assertIn('style.css', xhtml)

    def test_link_wrapping_several_images(self):
        html = f'<p>Gallery</p><a href="https://x/gallery"><img src="{data_uri("PNG")}"><img src="{data_uri("GIF")}"></a>'
        path = self.converter.convert_to_epub(Article('https://example.com/g', 'Gallery', None, None, html))
        with zipfile.ZipFile(path) as epub_zip:
            soup = BeautifulSoup(epub_zip.read('EPUB/content.xhtml'), 'html.parser')
        self.assertEqual(len(soup.find_all('img')), 2)
        self.assertIsNone(soup.find('a', href='https://x/gallery'))

    def test_unreachable_image_becomes_alt_text(self):
        article = Article('https://example.com/b', 'Broken', None, None,
                          '<p>Body</p><img src="data:image/png;base64,bm90IGFuIGltYWdl" alt="A diagram">')
        path = self.converter.convert_to_epub(article)
        with zipfile.ZipFile(path) as epub_zip:
            xhtml = epub_zip.read('EPUB/content.xhtml').decode()
        self.assertNotIn('<img', xhtml)
        self.assertIn('[Image: A diagram]', xhtml)

    def test_same_title_never_shares_a_file(self):
        def convert(url, title, body):
            return self.converter.convert_to_epub(Article(url, title, None, None, f'<p>{body}</p>'))

        books = {
            convert('https://a.example/notes', 'Weekly notes', 'First'): ('weekly-notes.epub', 'First'),
            convert('https://b.example/notes', 'Weekly notes', 'Second'): ('weekly-notes.epub', 'Second'),
            convert('https://a.example/notes', 'Weekly notes', 'Updated'): ('weekly-notes.epub', 'Updated'),
            convert('https://c.example/1', None, 'Untitled one'): ('untitled.epub', 'Untitled one'),
            convert('https://c.example/2', None, 'Untitled two'): ('untitled.epub', 'Untitled two'),
        }
        self.assertEqual(len(books), 5)  # five conversions, five different paths
        for path, (name, body) in books.items():
            self.assertEqual(os.path.basename(path), name)  # the name readers see stays the title slug
            with zipfile.ZipFile(path) as epub_zip:  # and each file still holds its own article
                self.assertIn(body, epub_zip.read('EPUB/content.xhtml').decode())

        # The disk monitor finds every book in the new layout and leaves no directories behind
        import disk_monitor
        found = [path for path, _ in disk_monitor.get_files_by_age(disk_monitor.EPUBS_DIR, '*.epub')]
        self.assertEqual(sorted(map(os.path.normpath, found)), sorted(map(os.path.normpath, books)))
        disk_monitor.cleanup_old_files(0)
        self.assertEqual(os.listdir(disk_monitor.EPUBS_DIR), [])


if __name__ == '__main__':
    unittest.main()
