# Site compatibility report

Survey of the scrape → EPUB pipeline against 68 live article URLs (October 2026). Rerun it any time with:

```bash
python tests/site_survey/run.py            # uses tests/site_survey/urls.txt, prints a report
```

## Summary

|                                   | Before | After |
|-----------------------------------|--------|-------|
| Converted without error           | 55/66  | 68/68 |
| Medium posts                      | 0/11 (HTTP 403) | 11/11 (3 member-only posts flagged as previews) |
| Substack posts with correct author/publication/date | 0/15 | 15/15 |
| Truncated articles (BBC, Ars Technica, kottke.org) | 3 | 0 |
| EPUBs whose image references resolve (case-sensitive readers) | 0 | all |
| WebP/AVIF images inside EPUBs     | 4 articles | 0 |
| Articles with garbled characters  | 1 (Cloudflare blog) | 0 |
| Book language                     | always `en` | from the page (`de`, `en-GB`, ...) |

The survey covers Medium (medium.com/@user, publications, user.medium.com, custom domains), Substack
(*.substack.com, custom domains, and every share-link format), static/indie blogs, Ghost, WordPress(.com),
Blogger, Hashnode, dev.to, LessWrong, beehiiv, company tech blogs, BBC, Guardian, NPR, Al Jazeera, Ars
Technica, The Conversation, ProPublica, Quanta, Aeon, TechCrunch, Engadget, NASA, Wikipedia and German news
sites. Paywalled sites were excluded except for two paid Substack posts used as controls.

## Issues found and how they were fixed

| # | Issue | Fix |
|---|-------|-----|
| 1 | Medium answers every non-browser client with a Cloudflare block page (403) | `http.fetch` retries blocked requests with browser TLS impersonation (curl_cffi); `MediumScraper` falls back to the author's/publication's RSS feed (full text of the ~10 latest posts) if that is blocked too |
| 2 | EPUB `<img src="images/x">` pointed at `Images/x` | Images are stored as `Images/img_NNN.ext` and referenced with the same path |
| 3 | Substack: author always "Unknown Author", publication missing or wrong ("Simonw", "Open"), date = scrape time (Substack removed `og:site_name` and the byline element) | Metadata comes from the page's JSON-LD and `<meta>` tags (`metadata.py`) |
| 4 | Titles containing `/` produced a nonexistent EPUB path; ebooklib swallowed the error and the CLI reported success | Slugified file names; `write_epub`'s result is checked and the file is written atomically |
| 5 | readability returned only one section of BBC and Ars Technica articles and a login modal on kottke.org | Pop-ups/comments are removed before extraction, and trafilatura's result is used when readability is clearly shorter or lost the images |
| 6 | Lazy-loaded, `<picture>`, `<noscript>`, `<amp-img>`/`<a-img>` images were dropped | `promote_lazy_images` turns them into plain `<img>` tags (picking a srcset candidate ≤1600 px, with the original `src` as download fallback) |
| 7 | Site header `<h1>` used as title (jvns.ca → "Julia Evans") and site suffixes kept ("– LessWrong") | Title from `og:title`/JSON-LD with site-name suffix stripping |
| 8 | Author missing on most generic sites | JSON-LD/`<meta>`/trafilatura byline extraction |
| 9 | UTF-8 pages without a charset header were decoded as ISO-8859-1 | `decode_html` uses header, `<meta charset>`, then UTF-8 |
| 10 | Relative URLs resolved against the original URL instead of the redirect target | All URLs are resolved against the final URL |
| 11 | WebP/AVIF images embedded as-is | Pillow converts them to JPEG/PNG and downsizes images wider than 1600 px |
| 12 | Image downloads: default python-requests UA (Wikimedia 403), no timeout, sequential, failed images left as remote URLs | Shared session with browser UA, timeouts, 8 parallel downloads, 429 backoff, failed images replaced by their alt text |
| 13 | Duplicate image file names produced invalid EPUBs | Sequential image names, each source embedded once |
| 14 | Book language hard-coded to `en` | Language from `<html lang>` |
| 15 | Remote `<source srcset>`, iframes, Substack subscribe/share widgets left in the book | `sanitize_for_kindle` and Substack-specific cleanup; embeds become links |
| 16 | No timeouts anywhere | `(10, 30)` s timeouts on every request |
| 17 | Bot: whole message used as URL, blocking scraping inside the async handler, one generic error for everything, `is_url` never awaited | First URL extracted from the message, work runs in a thread, specific error messages, await fixed |
| 18 | `tests/test_substack_metadata.py` imported a removed function | Fixed; offline tests added in `tests/test_extraction.py` |

Found during the fixes:
- `open.substack.com` share links now answer with a meta-refresh page instead of an HTTP redirect, so `fetch` follows those.
- LessWrong streams its article in hidden React chunks (`<div hidden id="S:n">`), which are now revealed before extraction.

## Paywalled posts

Paid-only Substack posts (`div.paywall` marker / JSON-LD `isAccessibleForFree: false`) and member-only Medium
posts are extracted from what a non-subscriber sees, sent as a preview, and end with a notice linking to the
full post. The bot tells the user it was a preview.

## Known limitations

- Medium's RSS fallback only covers each author's or publication's ~10 most recent posts. It's only needed if
  the browser-impersonating request gets blocked too (more likely from datacenter IPs than from home connections).
- Wikipedia articles with hundreds of formula images (e.g. *Fourier transform*) hit Wikimedia's rate limits;
  formulas that couldn't be downloaded show their LaTeX alt text. Downloads stop after 300 images.
- Some sites expose no author metadata at all (Paul Graham, danluu.com, Cloudflare blog).
- Images inside lightbox widgets (Ars Technica) and on a few other sites are still lost by both extractors.
- Pages that only render with JavaScript (e.g. Notion) are rejected with an explanation.

## Survey results (after the fixes)

Words: extracted (reference from JSON-LD `articleBody` or the page's `<article>` paragraphs; 0 = no reference).
Images: embedded in the EPUB / found in the article.

| URL | Scraper | Title | Author | Date | Lang | Words (ref) | Images | Time | Flags |
|---|---|---|---|---|---|---|---|---|---|
| netflixtechblog.com/measuring-the-impact-of-personalize | medium | Measuring the Impact of Personalized Recommen | Netflix Technology Blog | 2026-07-10 | en | 2478 (2170) | 6/6 | 2.8s |  |
| netflixtechblog.com/integrating-netflixs-foundation-mod | medium | Integrating Netflix’s Foundation Model into P | Netflix Technology Blog | 2025-11-17 | en | 1680 (1630) | 4/4 | 3.8s |  |
| medium.com/blog/writers-distrust-ai-but-love-using-it-9 | medium | Writers distrust AI, but love using it | The Medium Newsletter | 2026-10-07 | en | 961 (957) | 2/2 | 1.1s |  |
| uxdesign.cc/nobody-feels-heard-by-a-report-c5a06d96bc39 | medium | Nobody feels heard by a report | Wira Indra Kusuma | 2026-10-15 | en | 244 (205) | 1/1 | 3.0s | preview |
| karpathy.medium.com/software-2-0-a64152b37c35 | medium | Software 2.0 | Andrej Karpathy | 2017-11-11 | en | 2158 (2134) | 4/4 | 0.8s |  |
| karpathy.medium.com/yes-you-should-understand-backprop- | medium | Yes you should understand backprop | Andrej Karpathy | 2016-12-19 | en | 1573 (1452) | 5/5 | 1.0s |  |
| medium.com/@rajkanjariya2020/the-problem-with-ai-agents | medium | The Problem With AI Agents Isn’t Intelligence | Raj Kanjariya | 2026-10-16 | en | 3907 (3262) | 3/3 | 2.6s |  |
| medium.com/engineering-playbook/my-best-engineer-asked- | medium | My Best Engineer Asked Me to Remove His Name  | Software Engineering Know | 2026-10-16 | en | 2887 (2715) | 1/1 | 1.8s |  |
| pub.towardsai.net/how-to-ask-ai-a-question-it-cant-just | medium | How to Ask AI a Question It Can’t Just Agree  | Adam Jaber | 2026-10-16 | en | 248 (227) | 1/1 | 3.1s | preview |
| oliviadobbs13.medium.com/ocean-acidification-carbon-dio | medium | Ocean Acidification: Carbon Dioxide’s Second  | Liv L. Dobbs, MPH | 2026-10-16 | en | 240 (222) | 1/1 | 1.4s | preview |
| medium.com/@willr45/finite-number-of-souls-1c11ba1c9e28 | medium | Finite number of souls | Vijo Joy | 2026-10-16 | en | 492 (393) | 0/0 | 1.4s |  |
| astralcodexten.com/p/ai-safety-is-not-a-corporate-plot | substack | AI Safety Is Not A Corporate Plot | Scott Alexander | 2026-10-15 | en | 3167 (3084) | 6/6 | 0.4s |  |
| astralcodexten.com/p/your-book-review-we-present-televi | substack | Your Book Review: We Present Television | Scott Alexander | 2026-10-10 | en | 9319 (9249) | 11/11 | 0.5s |  |
| oneusefulthing.org/p/the-overhang | substack | The Overhang | Ethan Mollick | 2026-09-18 | en | 2122 (2060) | 5/5 | 1.0s |  |
| simonw.substack.com/p/2026-in-llms-so-far | substack | 2026 in LLMs (so far) | Simon Willison | 2026-09-28 | en | 7732 (7418) | 57/57 | 1.7s |  |
| noahpinion.blog/p/maybe-the-rapture-is-already-here | substack | Maybe the Rapture is already here | Noah Smith | 2026-10-09 | en | 1606 (1574) | 5/5 | 0.5s |  |
| thezvi.substack.com/p/arguments-about-ai-consciousness- | substack | Arguments About AI Consciousness Remain Highl | Zvi Mowshowitz | 2026-10-13 | en | 5004 (4940) | 6/6 | 1.1s |  |
| garymarcus.substack.com/p/we-must-recall-open-ended-ai- | substack | We must recall open-ended AI agents with inte | Gary Marcus | 2026-10-10 | en | 469 (439) | 2/2 | 1.2s |  |
| aella.substack.com/p/the-hotness-curve-how-age-changes | substack | The Hotness Curve (how age changes a woman's  | Aella | 2026-06-24 | en | 2426 (2320) | 19/19 | 1.2s |  |
| aella.substack.com/p/pt3-the-status-wars-of-apes | substack | Pt3: The Status Wars of Apes | Aella | 2025-07-17 | en | 2995 (2987) | 5/5 | 1.0s |  |
| sustainabilitybynumbers.com/p/population-growth-decline | substack | Population growth or decline will have little | Hannah Ritchie | 2025-07-15 | en | 2322 (2242) | 5/5 | 1.1s |  |
| substack.com/inbox/post/166333070 | substack | Can We Save Our Internet From The Bots, AND P | Liv Boeree | 2025-07-01 | en | 957 (905) | 2/2 | 0.9s |  |
| substack.com/inbox/post/169101264 | substack | Pt4: Power Hierarchies | Aella | 2025-07-31 | en | 3288 (3276) | 5/5 | 0.9s |  |
| substack.com/home/post/p-216098733 | substack | The Overhang | Ethan Mollick | 2026-09-18 | en | 2122 (2060) | 5/5 | 1.4s |  |
| open.substack.com/pub/simonw/p/2026-in-llms-so-far?r=ab | substack | 2026 in LLMs (so far) | Simon Willison | 2026-09-28 | en | 7732 (7418) | 57/57 | 2.1s |  |
| substack.com/@noahpinion/p-219538380 | substack | Maybe the Rapture is already here | Noah Smith | 2026-10-09 | en | 1606 (1574) | 5/5 | 1.3s |  |
| paulgraham.com/greatwork.html | readability | How to Do Great Work |  | 2023-01-01 |  | 11952 (0) | 3/4 | 1.9s | no-author, img-failed:1 |
| danluu.com/look-stupid/ | readability | Willingness to look stupid |  | 2020-01-26 | en | 5451 (2923) | 0/0 | 0.5s | no-author |
| jvns.ca/blog/2026/07/17/learning-about-running-sqlite/ | readability | Learning a few things about running SQLite | Julia Evans | 2026-07-17 | en | 969 (807) | 0/0 | 0.5s |  |
| simonwillison.net/2026/Oct/12/python-3-15/ | readability | Hello Python 3.15, goodbye 3.10, and now I ca | Simon Willison | 2026-10-12 | en-GB | 981 (0) | 1/1 | 0.6s |  |
| lilianweng.github.io/posts/2024-11-28-reward-hacking/ | readability | Reward Hacking in Reinforcement Learning | Lilian Weng | 2024-11-28 | en-US | 7798 (7713) | 24/24 | 3.3s |  |
| herman.bearblog.dev/on-reading-books/ | readability | On reading books |  | 2026-09-22 | en | 850 (840) | 3/3 | 0.6s | no-author |
| waitbutwhy.com/2015/01/artificial-intelligence-revoluti | readability | The AI Revolution: The Road to Superintellige | Tim Urban | 2015-01-22 | en-US | 7702 (7010) | 17/17 | 2.9s |  |
| elroy.bot/blog/2025/07/29/ai-is-a-floor-raiser-not-a-ce | readability | AI is a Floor Raiser, not a Ceiling Raiser | Tom Bedor | 2025-07-29 | en | 1021 (816) | 7/7 | 2.6s |  |
| kottke.org/26/10/chromatic-inkscapes | readability | Chromatic Inkscapes | Jason Kottke | 2026-10-16 | en | 72 (0) | 6/6 | 2.0s |  |
| troyhunt.com/weekly-update-525/ | trafilatura | Weekly Update 525: AI Data Breach Hyperbole | Troy Hunt | 2026-10-13 | en | 205 (0) | 0/0 | 0.4s |  |
| blog.codinghorror.com/you-cant-vibe-code-love/ | readability | You Can't "Vibe Code" Love | Jeff Atwood | 2026-08-31 | en | 576 (424) | 3/3 | 1.5s |  |
| terrytao.wordpress.com/2026/10/15/why-are-we-even-doing | readability | Why are we even doing all this? | Terence Tao | 2026-10-15 | en | 1232 (0) | 0/0 | 1.5s |  |
| projectzero.google/2026/10/emergency-patching.html | readability | How to fix a bug in a fix | Natalie Silvanovich | 2026-10-06 | en | 2057 (1861) | 0/0 | 0.5s |  |
| townhall.hashnode.com/hashnode-docs-free-license-for-op | trafilatura | Free Hashnode License for Open Source Project | Haimantika Mitra | 2024-10-21 | en | 384 (337) | 1/1 | 1.9s |  |
| dev.to/nabeelbaghoor/voicemail-detection-is-a-classifie | readability | Voicemail Detection Is a Classifier. Plan for | Nabeel Hassan | 2026-10-16 | en | 1592 (1262) | 0/0 | 0.4s |  |
| lesswrong.com/posts/SwYBLQvo8MddDcCwz/cat-belling-probl | readability | Cat-Belling Problems | Eliezer Yudkowsky | 2026-09-03 |  | 7449 (0) | 5/5 | 2.0s |  |
| superhuman.ai/p/meta-s-muse-is-coming-to-mac | readability | Meta's Muse is coming to Mac | Zain Kahn | 2026-10-16 | en | 1171 (0) | 10/10 | 1.4s |  |
| stackoverflow.blog/2026/10/16/formal-methods-say-you-re | readability | AI says you’re right, formal methods say you’ | Phoebe Sajor | 2026-10-16 | en | 129 (108) | 1/1 | 1.3s |  |
| smashingmagazine.com/2026/10/how-name-things/ | readability | A Practical Guide To Naming Things | Vitaly Friedman | 2026-10-06 | en | 1435 (1147) | 10/10 | 1.8s |  |
| blog.cloudflare.com/verified-bots-accountability/ | readability | Continuous accountability for Verified bots |  | 2026-10-16 | en-US | 1059 (979) | 6/6 | 2.1s | no-author |
| github.blog/engineering/architecture-optimization/from- | readability | From 2,500 requests to 24: Rebuilding star hi | Taylor Cuilty | 2026-10-14 | en-US | 1655 (4) | 2/2 | 0.6s |  |
| martinfowler.com/articles/are-harnesses-worth-the-cost. | readability | Are Harnesses Worth the Cost? | Naresh Jain | 2026-10-13 |  | 3692 (3577) | 6/6 | 1.8s |  |
| hacks.mozilla.org/2026/08/intent-to-ship-jpeg-xl/ | readability | Intent to Ship: JPEG XL | Jake Archibald | 2026-08-24 | en-US | 583 (525) | 3/3 | 1.0s |  |
| bbc.co.uk/news/articles/cvx284w16z1po | trafilatura | Inside Ukrainian offensive pushing Russia bac | Dan Johnson | 2026-10-16 | en-GB | 1208 (1187) | 7/7 | 0.7s |  |
| theguardian.com/technology/2026/oct/14/zimbabwean-autho | readability | Zimbabwean author Simbarashe Kundizeza denies | Rachel Savage | 2026-10-14 | en | 674 (639) | 1/1 | 0.5s |  |
| npr.org/2026/10/16/nx-s1-6005201/health-treatment-menop | readability | Hot flashes, night sweats, insomnia – OB-GYNS | Shannon Firth | 2026-10-16 | en | 977 (996) | 4/4 | 0.8s |  |
| aljazeera.com/economy/2026/10/16/meta-employees-say-lul | trafilatura | Meta employees say Lula’s accounts restricted | AP; Reuters | 2026-10-16 | en | 364 (346) | 1/1 | 0.5s |  |
| arstechnica.com/gaming/2026/10/us-rep-proposes-bill-to- | readability | US Rep proposes bill to give video game buyer | Samuel Axon | 2026-10-16 | en | 805 (785) | 0/0 | 1.3s |  |
| theconversation.com/japans-mmx-mission-aims-to-swipe-so | readability | Japan’s MMX mission aims to swipe soil sample | Daniel Brown | 2026-10-16 | en | 1135 (1076) | 5/5 | 2.1s |  |
| propublica.org/article/missouri-plan-judge-selection-re | readability | Frustrated by Losses in the Courts, Missouri  | Jeremy Kohler | 2026-10-15 | en-US | 1603 (1586) | 3/3 | 1.1s |  |
| quantamagazine.org/how-do-fungi-keep-the-planet-healthy | trafilatura | How Do Fungi Keep the Planet Healthy? | Steven Strogatz; Janna Le | 2026-10-15 | en | 9974 (10215) | 4/4 | 1.4s |  |
| aeon.co/essays/the-century-long-search-for-the-limits-t | readability | The century-long search for the limits to kno | Alexander V Gheorghiu | 2026-10-15 | en | 3138 (3347) | 3/3 | 1.5s |  |
| techcrunch.com/2026/10/16/porsches-electric-macan-turbo | readability | Porsche’s electric Macan Turbo is an automoti | Tim De Chant | 2026-10-16 | en-US | 1208 (1347) | 6/6 | 1.4s |  |
| engadget.com/2288908/if-memory-shortages-last-tech-comp | readability | If memory shortages last, tech companies shou | Igor Bonifacic | 2026-10-16 | en-US | 864 (844) | 0/0 | 0.9s |  |
| science.nasa.gov/missions/hubble/nasas-hubble-spies-spi | readability | NASA's Hubble Spies Spiral’s Edge | Andrea Gianopoulos | 2026-10-16 | en-US | 243 (290) | 1/1 | 2.0s |  |
| en.wikipedia.org/wiki/Fridtjof_Nansen | readability | Fridtjof Nansen | Contributors to Wikimedia | 2002-01-24 | en | 13191 (10063) | 18/20 | 24.8s | img-failed:2 |
| en.wikipedia.org/wiki/Fourier_transform | readability | Fourier transform | Contributors to Wikimedia | 2002-05-17 | en | 16066 (21113) | 394/521 | 38.0s | img-failed:127 |
| tagesschau.de/ausland/europa/selenskyj-eu-gipfel-102.ht | readability | Selenskyj beim EU-Gipfel: Unterstützung für d | Stephan Stuchlik | 2026-10-16 | de | 965 (1030) | 2/2 | 1.2s |  |
| spektrum.de/news/super-chandrasekhar-wenn-weisse-zwerge | readability | Weiße Zwerge: Schwerer als die Theorie erlaub | Simon Misof | 2026-10-16 | de | 1185 (1109) | 1/1 | 1.0s |  |
| heise.de/news/Apple-Website-in-Frankreich-leakt-neues-i | readability | Apple-Website in Frankreich leakt neues iPad  | Ben Schwan | 2026-10-16 | de | 423 (0) | 2/2 | 1.4s |  |
| noahpinion.blog/p/ai-vs-the-railroads | substack | AI vs. the railroads | Noah Smith | 2026-10-15 | en | 888 (835) | 6/6 | 0.5s | preview |
| garymarcus.substack.com/p/generative-ai-in-disarray | substack | Generative AI in disarray | Gary Marcus | 2026-10-15 | en | 42 (44) | 1/1 | 0.5s | preview |

68/68 converted, 68 without serious flags (uppercase flags are serious).
