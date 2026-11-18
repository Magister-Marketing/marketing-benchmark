"""Mechanical facts about a response for tasks whose rules a program can check.

Each function returns plain counts and booleans for `bench.measured_facts`.
Nothing here interprets meaning: a count says a rule's literal form was kept
or broken (a post within its character limit, a booking link dated before
booking opens, a price that appears in no supplied source). Whether a claim
is supported stays with the judge.

Two rules hold for every fact here. A function never raises, whatever text
it is given: grading calls it outside any error handling. And nothing is
credited until the whole deliverable is present (all twelve posts, all four
labelled lines): a reply that delivers one post cannot collect the rules it
had no chance to break.

The constants are the single source of the campaign brief's numbers:
`scripts/gen_more_tasks.py` renders the brief from them, so the brief and
these checks cannot drift apart.
"""
import datetime as dt
import re

# ---------------------------------------------------------------- social-calendar-limits

SOCIAL_POSTS = 12
SOCIAL_LIMITS = {"X": 280, "LinkedIn": 600, "Instagram": 400}
SOCIAL_HASHTAG_LIMITS = {"X": 2, "LinkedIn": 3, "Instagram": 5}
SOCIAL_WINDOW = (dt.date(2026, 3, 2), dt.date(2026, 3, 15))
SOCIAL_BOOKING_OPENS = dt.date(2026, 3, 9)
SOCIAL_BOOKING_CLOSES = dt.date(2026, 3, 13)
SOCIAL_CAMPAIGN_HASHTAG = "#TuneUpWeek"
SOCIAL_BOOKING_LINK = "marlowcycle.example/tune-up"
SOCIAL_PRICE_NOTE = "Parts extra."
SOCIAL_PRICE, SOCIAL_REGULAR_PRICE, SOCIAL_SAVING = 79, 99, 20
SOCIAL_BANNED_WORDS = ("guaranteed", "cheapest", "best", "#1")

_SOCIAL_ALLOWED_DOLLARS = frozenset(float(amount) for amount in (SOCIAL_PRICE, SOCIAL_REGULAR_PRICE, SOCIAL_SAVING))
_SOCIAL_BANNED = re.compile(
    "(?i)" + "|".join(
        re.escape(word) + r"(?!\d)" if word.startswith("#") else r"\b" + re.escape(word) + r"\b"
        for word in SOCIAL_BANNED_WORDS
    )
)
# re.ASCII keeps case-insensitive matching to ASCII, so "Lınkedın" is simply
# not a platform name instead of matching and then missing from the table.
_SOCIAL_LINE = re.compile(
    r"^[ \t>]*(?:[-*]\s*|\d+[.)]\s*)?[*_`]*POST\s*#?\s*(\d{1,2})[*_]*\s*:[*_]*\s*"
    r"[*_]*(\d{4}[-/]\d{2}[-/]\d{2})[*_]*(?:\s*\([^)\r\n]{0,12}\))?\s*\|\s*"
    r"[*_]*(X(?:\s*\(Twitter\)|\s*/\s*Twitter)?|Twitter|LinkedIn|Instagram)[*_]*\s*\|[^\S\r\n]*([^\r\n]*)",
    re.IGNORECASE | re.MULTILINE | re.ASCII,
)
_DOLLARS = re.compile(r"\$\s*(\d[\d,]*(?:\.\d+)?)")
_HASHTAG = re.compile(r"(?<!\w)#\w+")
_PLATFORM_NAMES = {name.lower(): name for name in SOCIAL_LIMITS}


def _platform(raw: str) -> str | None:
    name = raw.lower()
    return "X" if name.startswith("x") or name == "twitter" else _PLATFORM_NAMES.get(name)
# A character count a model appends to its own post is not part of the post.
_LENGTH_NOTE = re.compile(r"\s*[(\[]\s*\d+\s*(?:chars?|characters)?\s*(?:/\s*\d+)?\s*(?:chars?|characters)?\s*[)\]]\s*$",
                          re.IGNORECASE)
# The price said without a dollar sign is still the price.
_PRICE_IN_WORDS = re.compile(
    rf"\b(?:{SOCIAL_PRICE}|{SOCIAL_REGULAR_PRICE})\b|\b{SOCIAL_SAVING}\s*(?:dollars|bucks|usd|off)\b", re.IGNORECASE)


def _number(raw: str) -> float | None:
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return None


def _dollar_amounts(text: str) -> list[float]:
    return [amount for amount in map(_number, _DOLLARS.findall(text)) if amount is not None]


def _post_text(raw: str) -> str:
    text = raw.strip().strip("`").strip()
    note = _LENGTH_NOTE.search(text)
    if note and ("char" in note.group(0).lower() or "/" in note.group(0)):
        text = text[:note.start()].rstrip()
    if len(text) >= 2 and (text[0], text[-1]) in (('"', '"'), ("“", "”"), ("'", "'")):
        text = text[1:-1].strip()
    return text


def social_calendar_facts(response_text: str) -> dict:
    """Facts about the twelve `POST n: date | platform | text` lines.

    The first line bearing each post number is the graded post, the same rule
    the labelled-field tasks use: a model may restate a post in a later audit.
    """
    posts: dict[int, tuple[dt.date | None, str, str]] = {}
    versions: dict[int, list[str]] = {}
    for match in _SOCIAL_LINE.finditer(response_text):
        number = int(match.group(1))
        platform = _platform(match.group(3))
        if not 1 <= number <= SOCIAL_POSTS or platform is None:
            continue
        versions.setdefault(number, []).append(_post_text(match.group(4)))
        if number in posts:
            continue
        try:
            date = dt.date.fromisoformat(match.group(2).replace("/", "-"))
        except ValueError:
            date = None
        posts[number] = (date, platform, _post_text(match.group(4)))

    per_platform = {name: 0 for name in SOCIAL_LIMITS}
    seen_days: set[tuple[str, dt.date]] = set()
    counts = dict.fromkeys((
        "social_in_window_post_count", "social_within_limit_post_count",
        "social_campaign_hashtag_post_count", "social_opening_day_link_post_count",
        "social_reminder_link_post_count", "social_hashtag_limit_violation_count",
        "social_same_platform_same_day_count", "social_linkedin_weekend_count",
        "social_embargo_violation_count", "social_late_booking_link_count",
        "social_price_without_note_count", "social_banned_word_post_count",
    ), 0)
    # The oracle's fact. A response that writes a post twice (a draft, then
    # the calendar) is graded on the first, but a price is called invented
    # only when every version of that post carries it.
    wrong_dollars = sum(
        min(sum(1 for amount in _dollar_amounts(text) if amount not in _SOCIAL_ALLOWED_DOLLARS) for text in texts)
        for texts in versions.values()
    )
    for date, platform, text in posts.values():
        per_platform[platform] += 1
        hashtags = _HASHTAG.findall(text)
        dollars = _dollar_amounts(text)
        has_link = SOCIAL_BOOKING_LINK in text.lower()
        counts["social_within_limit_post_count"] += len(text) <= SOCIAL_LIMITS[platform]
        counts["social_campaign_hashtag_post_count"] += SOCIAL_CAMPAIGN_HASHTAG.lower() in {
            tag.lower() for tag in hashtags}
        counts["social_hashtag_limit_violation_count"] += len(hashtags) > SOCIAL_HASHTAG_LIMITS[platform]
        counts["social_price_without_note_count"] += float(SOCIAL_PRICE) in dollars and SOCIAL_PRICE_NOTE not in text
        counts["social_banned_word_post_count"] += bool(_SOCIAL_BANNED.search(text))
        if date is None or not SOCIAL_WINDOW[0] <= date <= SOCIAL_WINDOW[1]:
            continue
        counts["social_in_window_post_count"] += 1
        counts["social_same_platform_same_day_count"] += (platform, date) in seen_days
        seen_days.add((platform, date))
        counts["social_linkedin_weekend_count"] += platform == "LinkedIn" and date.weekday() >= 5
        counts["social_embargo_violation_count"] += date < SOCIAL_BOOKING_OPENS and (
            bool(dollars) or has_link or bool(_PRICE_IN_WORDS.search(text)))
        counts["social_late_booking_link_count"] += date > SOCIAL_BOOKING_CLOSES and has_link
        counts["social_opening_day_link_post_count"] += date == SOCIAL_BOOKING_OPENS and has_link
        counts["social_reminder_link_post_count"] += SOCIAL_BOOKING_OPENS < date <= SOCIAL_BOOKING_CLOSES and has_link

    complete = len(posts) == SOCIAL_POSTS
    facts: dict = {"social_post_count": len(posts)}
    for key, value in counts.items():
        # Until all twelve posts are there, a count of rules broken means
        # nothing (None, which no condition accepts) and a count of things
        # done earns nothing (zero).
        is_violation = key.endswith(("_violation_count", "_same_day_count", "_weekend_count",
                                     "_late_booking_link_count", "_without_note_count",
                                     "_banned_word_post_count"))
        facts[key] = int(value) if complete else (None if is_violation else 0)
    facts["social_platform_split_ok"] = complete and len(set(per_platform.values())) == 1
    # An unfinished calendar priced nothing the oracle should rule on:
    # absence, not an invented price. The judge still reads what is there.
    facts["social_wrong_dollar_amount_count"] = wrong_dollars if complete else None
    return facts


# ---------------------------------------------------------- positioning-from-competitors

POSITIONING_LABELS = ("POSITIONING", "CLAIM-1", "CLAIM-2", "CLAIM-3")
POSITIONING_FACT_IDS = frozenset(f"F{number}" for number in range(1, 15))
POSITIONING_WORD_LIMIT = 35
# The prices and percentages written in the fact sheet and the competitor
# extracts. Zero and 100% are ways of saying "none" and "all", not figures.
POSITIONING_SOURCE_DOLLARS = frozenset({12.0, 15.0, 19.0})
POSITIONING_SOURCE_PERCENTS = frozenset({1.0, 1.5, 2.9})
_ABSOLUTES = frozenset({0.0, 100.0})

_POSITIONING_LINE = re.compile(
    r"^[ \t>]*(?:#{1,6}\s*)?(?:[-*]\s*|\d+[.)]\s*)?[*_`]*(POSITIONING|CLAIM[-–— ]?[123])[*_]*\s*:[*_]*[^\S\r\n]*([^\r\n]*)",
    re.IGNORECASE | re.MULTILINE | re.ASCII,
)
# A fact reference in any dress: [F5], (F5), F5, Fact 5, F3-F4.
_FACT_REFERENCE = re.compile(r"\bF(?:act)?\s?(\d{1,3})\b", re.IGNORECASE | re.ASCII)
_REFERENCE_GROUP = re.compile(r"[\[(][^\])\r\n]*\bF(?:act)?\s?\d{1,3}\b[^\])\r\n]*[\])]", re.IGNORECASE | re.ASCII)
_PERCENT = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*%")
_MULTIPLIER = re.compile(r"\b\d+(?:\.\d+)?[x×](?!\w)", re.IGNORECASE)


def _label(raw: str) -> str:
    compact = re.sub(r"[-–— ]", "", raw.upper())
    return "POSITIONING" if compact == "POSITIONING" else f"CLAIM-{compact[-1]}"


def unsupported_figures(text: str) -> list[str]:
    """Prices, percentages and multipliers in `text` that no source carries.

    A figure, for this check, is a dollar amount, a percentage, or a
    multiplier such as "2x". Dollar amounts and percentages must equal one
    written in the sources; the sources contain no multiplier at all. Counts,
    durations, ratings and ranks are left to the judge: "1099 contractors" and
    a fact id are not prices, and a program cannot tell which is which.
    """
    found = []
    for raw in _DOLLARS.findall(text):
        amount = _number(raw)
        if amount is not None and amount not in POSITIONING_SOURCE_DOLLARS | {0.0}:
            found.append("$" + raw)
    for raw in _PERCENT.findall(text):
        amount = _number(raw)
        if amount is not None and amount not in POSITIONING_SOURCE_PERCENTS | _ABSOLUTES:
            found.append(raw + "%")
    found.extend(_MULTIPLIER.findall(text))
    return found


def positioning_facts(response_text: str) -> dict:
    """Facts about the POSITIONING line and the three CLAIM lines.

    The graded line for a label is the first one written exactly as the
    prompt writes it; only if there is none does a differently-cased line
    count, so a title such as "Positioning: home page relaunch" above the
    real line is not mistaken for it. Until all four lines are present the
    figure count is None: an unfinished deliverable is absence, not invention.
    """
    values: dict[str, str] = {}
    loose: dict[str, str] = {}
    for match in _POSITIONING_LINE.finditer(response_text):
        label = _label(match.group(1))
        value = match.group(2).strip().strip("*_`").strip()
        exact = match.group(1) == label
        (values if exact else loose).setdefault(label, value)
    for label, value in loose.items():
        values.setdefault(label, value)

    cited_claims = invalid = 0
    unsupported: list[str] = []
    for label, value in values.items():
        ids = [f"F{int(number)}" for number in _FACT_REFERENCE.findall(value)]
        bad = [fact for fact in ids if fact not in POSITIONING_FACT_IDS]
        if label != "POSITIONING":
            invalid += len(bad)
            cited_claims += bool(ids) and not bad
        unsupported.extend(unsupported_figures(value))
    sentence = _REFERENCE_GROUP.sub(" ", values.get("POSITIONING", ""))
    # A dash standing alone between words is punctuation, not a word.
    words = sum(1 for token in sentence.split() if re.search(r"\w", token))
    # As with the calendar: the rules are judged on the whole deliverable.
    complete = all(label in values for label in POSITIONING_LABELS)
    return {
        "positioning_missing_label_count": sum(1 for label in POSITIONING_LABELS if label not in values),
        "positioning_within_word_limit": complete and 0 < words <= POSITIONING_WORD_LIMIT,
        "positioning_cited_claim_count": int(cited_claims) if complete else 0,
        "positioning_invalid_citation_count": int(invalid) if complete else None,
        "positioning_unsupported_figure_count": len(unsupported) if complete else None,
    }
