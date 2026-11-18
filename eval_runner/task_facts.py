"""Mechanical facts about a response for tasks whose rules a program can check.

Each function returns plain counts and booleans for `bench.measured_facts`.
Nothing here interprets meaning: a count says a rule's literal form was
kept or broken (a post within its character limit, a booking link dated
before the embargo lifts, a figure that appears in no supplied source).
Whether a claim is supported, or a softer leak of embargoed news occurred,
stays with the judge.

Counts of things done right (`..._post_count`) are zero for an empty reply,
so they earn nothing for saying nothing. Counts of violations are guards.

The constants repeat what the task's own brief tells the candidate.
`tests/test_more_tasks.py` fails when they and the fixtures disagree.
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
SOCIAL_CAMPAIGN_HASHTAG = "#tuneupweek"
SOCIAL_BOOKING_LINK = "marlowcycle.example/tune-up"
SOCIAL_PRICE_NOTE = "Parts extra."
SOCIAL_ALLOWED_DOLLARS = (79.0, 99.0, 20.0)
_SOCIAL_BANNED = re.compile(r"(?i)\b(?:guaranteed|cheapest|best)\b|#1(?!\d)")
_SOCIAL_LINE = re.compile(
    r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?POST\s+(\d{1,2})(?:\*\*)?\s*:(?:\*\*)?\s*"
    r"(\d{4}-\d{2}-\d{2})\s*\|\s*(X|LinkedIn|Instagram)\s*\|[^\S\r\n]*([^\r\n]*)"
)
_DOLLARS = re.compile(r"\$\s*(\d[\d,]*(?:\.\d+)?)")
_HASHTAG = re.compile(r"(?<!\w)#\w+")
_PLATFORM_NAMES = {name.lower(): name for name in SOCIAL_LIMITS}


def _dollar_amounts(text: str) -> list[float]:
    return [float(raw.replace(",", "")) for raw in _DOLLARS.findall(text)]


def social_calendar_facts(response_text: str) -> dict:
    """Facts about the twelve `POST n: date | platform | text` lines.

    The first line bearing each post number is the graded post, the same rule
    the labelled-field tasks use: a model may restate a post in a later audit.
    """
    posts: dict[int, tuple[dt.date | None, str, str]] = {}
    for match in _SOCIAL_LINE.finditer(response_text):
        number = int(match.group(1))
        if not 1 <= number <= SOCIAL_POSTS or number in posts:
            continue
        try:
            date = dt.date.fromisoformat(match.group(2))
        except ValueError:
            date = None
        text = match.group(4).strip().strip("`").strip()
        posts[number] = (date, _PLATFORM_NAMES[match.group(3).lower()], text)

    per_platform = {name: 0 for name in SOCIAL_LIMITS}
    seen_days: set[tuple[str, dt.date]] = set()
    facts = dict.fromkeys((
        "social_in_window_post_count", "social_within_limit_post_count",
        "social_campaign_hashtag_post_count", "social_hashtag_limit_violation_count",
        "social_same_platform_same_day_count", "social_linkedin_weekend_count",
        "social_embargo_violation_count", "social_late_booking_link_count",
        "social_price_without_note_count", "social_banned_word_post_count",
    ), 0)
    for date, platform, text in posts.values():
        per_platform[platform] += 1
        hashtags = _HASHTAG.findall(text)
        dollars = _dollar_amounts(text)
        has_link = SOCIAL_BOOKING_LINK in text.lower()
        facts["social_within_limit_post_count"] += len(text) <= SOCIAL_LIMITS[platform]
        facts["social_campaign_hashtag_post_count"] += SOCIAL_CAMPAIGN_HASHTAG in {tag.lower() for tag in hashtags}
        facts["social_hashtag_limit_violation_count"] += len(hashtags) > SOCIAL_HASHTAG_LIMITS[platform]
        facts["social_price_without_note_count"] += 79.0 in dollars and SOCIAL_PRICE_NOTE not in text
        facts["social_banned_word_post_count"] += bool(_SOCIAL_BANNED.search(text))
        if date is None or not SOCIAL_WINDOW[0] <= date <= SOCIAL_WINDOW[1]:
            continue
        facts["social_in_window_post_count"] += 1
        facts["social_same_platform_same_day_count"] += (platform, date) in seen_days
        seen_days.add((platform, date))
        facts["social_linkedin_weekend_count"] += platform == "LinkedIn" and date.weekday() >= 5
        facts["social_embargo_violation_count"] += date < SOCIAL_BOOKING_OPENS and (bool(dollars) or has_link)
        facts["social_late_booking_link_count"] += date > SOCIAL_BOOKING_CLOSES and has_link

    facts = {key: int(value) for key, value in facts.items()}
    facts["social_post_count"] = len(posts)
    facts["social_platform_split_ok"] = all(count == 4 for count in per_platform.values())
    # With no post at all nothing was priced: absence, not an invented price.
    facts["social_wrong_dollar_amount_count"] = sum(
        1 for amount in _dollar_amounts(response_text) if amount not in SOCIAL_ALLOWED_DOLLARS
    ) if posts else None
    return facts


# ---------------------------------------------------------- positioning-from-competitors

POSITIONING_LABELS = ("POSITIONING", "CLAIM-1", "CLAIM-2", "CLAIM-3")
POSITIONING_FACT_IDS = frozenset(f"F{number}" for number in range(1, 15))
POSITIONING_WORD_LIMIT = 35
# Every figure written in the fact sheet and the competitor extracts.
POSITIONING_SOURCE_NUMBERS = frozenset({
    1.0, 2.0, 2.9, 3.0, 4.0, 4.6, 5.0, 7.0, 9.0, 11.0, 12.0, 14.0, 15.0, 19.0, 24.0, 30.0,
    60.0, 135.0, 212.0, 1840.0, 2025.0, 2026.0, 21000.0, 400000.0,
})
_POSITIONING_LINE = re.compile(
    r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?(POSITIONING|CLAIM-[123])(?:\*\*)?\s*:(?:\*\*)?[^\S\r\n]*([^\r\n]*)"
)
_CITATION_GROUP = re.compile(r"\[([^\]\r\n]*)\]")
_CITATION_ID = re.compile(r"(?i)\bF\s?(\d{1,3})\b")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def positioning_facts(response_text: str) -> dict:
    """Facts about the POSITIONING line and the three CLAIM lines.

    A claim's citations are the fact ids inside its square brackets. Figures
    are read from the four graded lines only, citations removed, so a fact id
    is never mistaken for a figure. With no graded line at all the figure
    count is None: nothing was asserted, which is absence, not invention.
    """
    values: dict[str, str] = {}
    for match in _POSITIONING_LINE.finditer(response_text):
        label = match.group(1).upper()
        if label not in values:
            values[label] = match.group(2).strip().strip("*_`").strip()

    cited_claims = invalid = unsupported = 0
    for label, value in values.items():
        ids = [f"F{int(number)}" for group in _CITATION_GROUP.findall(value)
               for number in _CITATION_ID.findall(group)]
        bad = [fact for fact in ids if fact not in POSITIONING_FACT_IDS]
        if label != "POSITIONING":
            invalid += len(bad)
            cited_claims += bool(ids) and not bad
        unsupported += sum(
            1 for token in _NUMBER.findall(_CITATION_GROUP.sub(" ", value))
            if float(token.replace(",", "")) not in POSITIONING_SOURCE_NUMBERS
        )
    positioning_words = len(_CITATION_GROUP.sub(" ", values.get("POSITIONING", "")).split())
    return {
        "positioning_missing_label_count": sum(1 for label in POSITIONING_LABELS if label not in values),
        "positioning_within_word_limit": 0 < positioning_words <= POSITIONING_WORD_LIMIT,
        "positioning_cited_claim_count": int(cited_claims),
        "positioning_invalid_citation_count": int(invalid),
        "positioning_unsupported_figure_count": unsupported if values else None,
    }
