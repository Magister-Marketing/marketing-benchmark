"""Workflow task: cold outbound sequences from a lead list.

The brief is an outbound standard a sales-development lead would hand over:
which leads must never be emailed and why, how the rest are cut into
segments and country groups, how many steps each sequence has and on which
days, and what every email must and must not say. The work is applying it to
every lead of a list without one slip, then writing every email of every
sequence that results under hard limits, with merge fields that are safe
only where the data says they are.

Everything here is derived from the constants below: the standard the
candidate reads, the lead list, the product facts, the reference answer and
the checker. A rule cannot say one thing in the brief and another in the
grader.

All brands, people, companies, domains and figures are invented.
"""
from __future__ import annotations

import csv
import io
import random
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path

from eval_runner.workflows import common

TASK_ID = "outbound-sequence"
FIXTURE_DIR = Path("eval_runner") / "fixtures" / "outbound-sequence"
FILES = ["excluded.csv", "assignments.csv", "sequences.csv"]

BRAND = "Brackenfold"
# The standard states today's date, so the reference never depends on the real one.
TODAY = date(2026, 3, 16)
RECENT_DAYS = 60
MIN_EMPLOYEES = 50
MAX_EMPLOYEES = 5000
ENTERPRISE_FROM = 1000

COMPETITOR_DOMAINS = ["dockhallow.example", "slotrook.example", "bayquell.example"]

# How a title is read. A title is a buying role when it contains no junior
# term and either a standalone role or both a department and a level term.
STANDALONE_ROLES = ["coo", "chief operating officer"]
DEPARTMENT_TERMS = ["operations", "logistics", "warehouse", "distribution", "supply chain",
                    "fulfilment", "fulfillment", "site"]
LEVEL_TERMS = ["director", "head", "manager", "vp", "vice president", "chief"]
JUNIOR_TERMS = ["assistant", "deputy", "intern", "trainee"]

# Reasons in the order they apply: the first that applies is the reason.
EXCLUSIONS = ["opted_out", "bounced", "existing_customer", "competitor", "recently_contacted",
              "not_buying_role", "company_size"]

EXECUTIVE_TERMS = ["coo", "chief", "vp", "vice president"]
COLD_CHAIN_INDUSTRIES = ["food", "pharma"]
SEGMENTS = ["executive", "cold_chain", "enterprise", "site_ops"]
STEP_DAYS = {
    "executive": [1, 4, 10],
    "cold_chain": [1, 5, 9, 16],
    "enterprise": [1, 6, 13, 22],
    "site_ops": [1, 3, 8],
}

RESTRICTED_COUNTRIES = ["BE", "DE", "ES", "FR", "IE", "IT", "NL", "SE"]
CANADA = "CA"
GROUPS = ["standard", "restricted", "canada"]
RESTRICTED_STEPS = 2
RESTRICTED_MIN_GAP = 4

SUBJECT_MAX = 45
BODY_MAX_WORDS = 110
PARAGRAPH_MARK = " / "
BANNED_SUBJECT_STARTS = ["Re:", "Fwd:", "Fw:"]
UNSUBSCRIBE = "Not for you? Reply STOP and we will not email you again."
ADDRESS = "Brackenfold Systems, 9 Linnet Yard, Corrowmouth CM4 2XR"
LEGITIMATE_INTEREST = "We write under legitimate interest, as your role covers inbound dock operations."
CANADA_LINE = "Sent to your business address under Canadian anti-spam law."
COUNTRY_LINES = {"restricted": LEGITIMATE_INTEREST, "canada": CANADA_LINE}
FORBIDDEN = ["guarantee", "guaranteed", "just checking in", "quick question", "circling back",
             "touch base", "touching base", "following up", "free trial", "act now"]

# Merge field -> the leads.csv column it is filled from, and what to write
# where it may not be used.
MERGE_COLUMNS = {"first_name": "first_name", "company": "company", "industry": "industry"}
GREETING = "Hi {{first_name}},"
GREETING_FALLBACK = "Hi there,"
# {{first_name}} has no fallback inside a sentence: its fallback is the greeting.
FALLBACKS = {"company": "your team", "industry": "your sector"}

SENDER = "Ines Calloway"
SENDER_ROLE = "Partnerships Lead"
PROOF_POINTS = [
    "Ostrel Fresh cut the average truck wait at its docks from 52 minutes to 17 minutes in 10 weeks.",
    "Pembrine Parts cut detention charges by 41% in its first quarter on Brackenfold.",
    "Sites on Brackenfold book 90% of dock slots without a phone call or an email.",
]
OFFER = "A 20-minute walkthrough of the dock calendar, set up with the prospect's own inbound volumes."

LEAD_COLUMNS = ["lead_id", "first_name", "title", "company", "industry", "employees", "country", "domain",
                "email_status", "opted_out", "existing_customer", "last_contacted"]
RANDOM_LEADS = 166
SEED = 20260505  # chosen for an even spread of reasons and sequences


# ── Reading text the same way everywhere ─────────────────────────────────────

# Bounded quantifiers only: a cell is at most 4,000 characters, and nothing
# here can backtrack over it.
_FIGURE = re.compile(r"\d{1,12}(?:[.,]\d{1,12}){0,4}")
_MERGE = re.compile(r"\{\{([^{}]{0,40})\}\}")
_MERGE_SPACED = re.compile(r"\{\{\s{0,5}([a-z_]{1,30})\s{0,5}\}\}")
_MAX_CELL = 4000


def figures(text: object) -> list[Decimal]:
    """Every figure written in digits: "52", "41%" -> 41, "1,240" -> 1240."""
    out = []
    for match in _FIGURE.findall(str(text or "")[:_MAX_CELL * 2]):
        try:
            out.append(Decimal(match.replace(",", "")))
        except InvalidOperation:
            continue
    return out


ALLOWED_FIGURES = frozenset({f for point in PROOF_POINTS for f in figures(point)} | set(figures(OFFER)))
PROOF_FIGURES = [set(figures(point)) for point in PROOF_POINTS]


def title_words(title: object) -> list[str]:
    return re.findall(r"[a-z0-9]{1,40}", str(title or "")[:400].lower())


def has_term(title: object, term: str) -> bool:
    return common.has_phrase(title_words(title), term.split())


def word_count(body: object) -> int:
    """Pieces between spaces that hold a letter or a digit: ` / ` is not a word."""
    return sum(1 for piece in str(body or "")[:_MAX_CELL].split() if any(ch.isalnum() for ch in piece))


def merge_fields(text: object) -> list[str]:
    return [name.strip().lower() for name in _MERGE.findall(str(text or "")[:_MAX_CELL * 2])]


# ── The rules, applied ────────────────────────────────────────────────────────

def is_competitor(domain: str) -> bool:
    domain = domain.strip().lower()
    return any(domain == rival or domain.endswith("." + rival) for rival in COMPETITOR_DOMAINS)


def is_buying_role(title: str) -> bool:
    if any(has_term(title, term) for term in JUNIOR_TERMS):
        return False
    if any(has_term(title, term) for term in STANDALONE_ROLES):
        return True
    return any(has_term(title, term) for term in DEPARTMENT_TERMS) and any(
        has_term(title, term) for term in LEVEL_TERMS)


def days_since(last_contacted: str) -> int | None:
    return (TODAY - date.fromisoformat(last_contacted)).days if last_contacted else None


def exclusion_reason(lead: dict) -> str | None:
    since = days_since(lead["last_contacted"])
    employees = int(lead["employees"])
    checks = {
        "opted_out": lead["opted_out"] == "yes",
        "bounced": lead["email_status"] == "bounced",
        "existing_customer": lead["existing_customer"] == "yes",
        "competitor": is_competitor(lead["domain"]),
        "recently_contacted": since is not None and since <= RECENT_DAYS,
        "not_buying_role": not is_buying_role(lead["title"]),
        "company_size": not MIN_EMPLOYEES <= employees <= MAX_EMPLOYEES,
    }
    return next((reason for reason in EXCLUSIONS if checks[reason]), None)


def segment(lead: dict) -> str:
    if any(has_term(lead["title"], term) for term in EXECUTIVE_TERMS):
        return "executive"
    if lead["industry"] in COLD_CHAIN_INDUSTRIES:
        return "cold_chain"
    if int(lead["employees"]) >= ENTERPRISE_FROM:
        return "enterprise"
    return "site_ops"


def country_group(country: str) -> str:
    if country in RESTRICTED_COUNTRIES:
        return "restricted"
    return "canada" if country == CANADA else "standard"


def send_days(segment_code: str, group: str) -> list[int]:
    days = list(STEP_DAYS[segment_code])
    if group != "restricted":
        return days
    first, second = days[0], days[1]
    return [first, max(second, first + RESTRICTED_MIN_GAP)][:RESTRICTED_STEPS]


# ── The lead list ─────────────────────────────────────────────────────────────

_FIRST_NAMES = ["Ada", "Amir", "Anya", "Bea", "Cai", "Dev", "Eli", "Ema", "Finn", "Gia", "Hana", "Ivo",
                "Jade", "Kai", "Lena", "Luca", "Mara", "Nia", "Omar", "Pia", "Raf", "Rosa", "Sami",
                "Tess", "Ugo", "Vera", "Wim", "Yara", "Noor", "Theo", "Lior", "Mina", "Otto", "Remi",
                "Saul", "Tova", "Juno", "Kofi", "Liv", "Nils", "Oona", "Pavel", "Quinn", "Rui",
                "Suki", "Tomas", "Uma", "Vik", "Zoe"]
_ROOT_HEADS = ["Zar", "Quel", "Vosk", "Brix", "Tarq", "Plen", "Grav", "Skel", "Drov", "Mirk", "Jund",
               "Frel", "Kov", "Wex", "Yorv", "Hesk"]
_ROOT_TAILS = ["ane", "ery", "ola", "ith", "ova", "unt"]
_SUFFIXES = {
    "food": ["Foods", "Fresh", "Dairy"],
    "pharma": ["Pharma", "Labs", "Health"],
    "retail": ["Retail", "Stores", "Home"],
    "wholesale": ["Wholesale", "Supply", "Trading"],
    "logistics": ["Logistics", "Freight", "Haulage"],
    "automotive": ["Auto Parts", "Motors", "Components"],
}
_INDUSTRY_WEIGHTS = {"food": 14, "pharma": 7, "retail": 18, "wholesale": 15, "logistics": 22, "automotive": 12}
_COUNTRY_WEIGHTS = {"US": 36, "GB": 14, "AU": 6, "CA": 9, "DE": 7, "FR": 6, "NL": 5, "IE": 4, "ES": 4,
                    "IT": 3, "BE": 3, "SE": 3}
_EXEC_TITLES = ["COO", "Chief Operating Officer", "VP Operations", "VP Logistics", "VP, Supply Chain",
                "Vice President, Operations", "Chief Supply Chain Officer"]
_BUYER_TITLES = ["Operations Director", "Director of Logistics", "Head of Logistics", "Head of Operations",
                 "Warehouse Manager", "Distribution Manager", "Site Director", "Site Manager",
                 "Supply Chain Manager", "Logistics Manager", "Fulfilment Manager", "Head of Distribution",
                 "Warehouse Operations Manager", "Fulfillment Director", "Inbound Logistics Manager"]
_OTHER_TITLES = ["Logistics Coordinator", "IT Manager", "Finance Director", "Procurement Manager",
                 "Marketing Manager", "HR Director", "Senior Buyer", "Data Analyst", "Shift Supervisor",
                 "Operations Analyst", "Warehouse Supervisor", "Transport Planner"]


def _ago(days: int) -> str:
    return (TODAY - timedelta(days=days)).isoformat()


# Leads written by hand because a rule's edge is the point of them. Each is
# pinned in tests/test_workflow_outbound_sequence.py. Fields follow
# LEAD_COLUMNS from first_name on; the id is the lead's place in the list.
_PLANTED: dict[str, tuple] = {
    # Opted out and bounced: the first reason in the list is the reason.
    "L006": ("Rhea", "Logistics Manager", "Vantry Wholesale", "wholesale", 420, "US", "vantry.example",
             "bounced", "yes", "", ""),
    # A competitor's subdomain is the competitor.
    "L017": ("Milo", "Head of Operations", "Dockhallow UK", "logistics", 800, "GB", "uk.dockhallow.example",
             "valid", "", "", ""),
    # Ends with a competitor's name, but not after a dot: not a competitor.
    "L023": ("Anouk", "Warehouse Manager", "Middock Hallow Logistics", "logistics", 300, "US",
             "middockhallow.example", "valid", "", "", ""),
    # A competitor whose title is not a buying role: competitor comes first.
    "L031": ("Feliks", "Marketing Manager", "Slotrook", "logistics", 150, "DE", "slotrook.example",
             "valid", "", "", ""),
    # A competitor's own domain, in a restricted country.
    "L048": ("Colette", "Operations Director", "Bayquell", "logistics", 640, "FR", "bayquell.example",
             "valid", "", "", ""),
    # A competitor's subdomain, also contacted recently: competitor comes first.
    "L055": ("Benno", "Warehouse Manager", "Slotrook Europe", "logistics", 210, "NL", "eu.slotrook.example",
             "valid", "", "", _ago(12)),
    # Contacted exactly 60 days before today: excluded.
    "L038": ("Marta", "Distribution Manager", "Orvel Retail", "retail", 610, "US", "orvel.example",
             "valid", "", "", _ago(60)),
    # Contacted 61 days before today: not excluded.
    "L044": ("Jonas", "Warehouse Manager", "Pintel Wholesale", "wholesale", 230, "GB", "pintel.example",
             "valid", "", "", _ago(61)),
    # Bounced and an existing customer: bounced comes first.
    "L052": ("Esme", "Head of Logistics", "Carvoy Freight", "logistics", 540, "US", "carvoy.example",
             "bounced", "", "yes", ""),
    # `site` sits inside "Website": no department term.
    "L059": ("Arlo", "Website Manager", "Dunnet Stores", "retail", 380, "US", "dunnet.example",
             "valid", "", "", ""),
    # `coo` sits inside "Cooperative": no standalone role, no department.
    "L066": ("Hedda", "Cooperative Programs Director", "Lumsk Foods", "food", 290, "GB", "lumsk.example",
             "valid", "", "", ""),
    # A junior term overrides a department and a level.
    "L073": ("Teo", "Assistant Warehouse Manager", "Brevan Trading", "wholesale", 460, "US", "brevan.example",
             "valid", "", "", ""),
    # Exactly 50 employees is inside the range.
    "L081": ("Greta", "Site Manager", "Tolly Supply", "wholesale", 50, "US", "tolly.example",
             "valid", "", "", ""),
    # 49 employees is outside it.
    "L088": ("Imre", "Operations Director", "Fasko Haulage", "logistics", 49, "AU", "fasko.example",
             "valid", "", "", ""),
    # Exactly 5,000 employees is inside the range, and enterprise.
    "L095": ("Paloma", "Head of Distribution", "Grenwick Motors", "automotive", 5000, "US", "grenwick.example",
             "valid", "", "", ""),
    # 5,001 is outside it.
    "L102": ("Stellan", "Logistics Manager", "Morrisk Retail", "retail", 5001, "GB", "morrisk.example",
             "valid", "", "", ""),
    # Not a buying role and too small: the title comes first.
    "L109": ("Wren", "Finance Director", "Avrel Home", "retail", 20, "US", "avrel.example",
             "valid", "", "", ""),
    # An unknown email status is not a reason to exclude.
    "L116": ("Dorian", "Warehouse Operations Manager", "Kelpy Trading", "wholesale", 720, "US", "kelpy.example",
             "unknown", "", "", ""),
    # The one lead of cold_chain/standard with no first name: no {{first_name}} there.
    "L123": ("", "Distribution Manager", "Saffra Foods", "food", 640, "US", "saffra.example",
             "valid", "", "", ""),
    # No first name, but excluded: it does not stop {{first_name}} in executive/standard.
    "L130": ("", "VP Operations", "Hollin Retail", "retail", 900, "US", "hollin.example",
             "valid", "yes", "", ""),
    # A restricted country in the largest segment: two steps only.
    "L137": ("Lotte", "Warehouse Manager", "Mendle Retail", "retail", 380, "DE", "mendle.example",
             "valid", "", "", ""),
    # No company name: no {{company}} in site_ops/restricted.
    "L144": ("Joris", "Site Manager", "", "wholesale", 260, "BE", "veldmark.example",
             "valid", "", "", ""),
    # An executive title at a food company: executive comes before cold_chain.
    "L151": ("Sana", "Chief Operating Officer", "Quarra Foods", "food", 700, "US", "quarra.example",
             "valid", "", "", ""),
    # Pharma with 3,000 employees: cold_chain comes before enterprise.
    "L158": ("Bruno", "Head of Distribution", "Ilvent Pharma", "pharma", 3000, "GB", "ilvent.example",
             "valid", "", "", ""),
    # A level term and no department: not a buying role.
    "L165": ("Celia", "Chief of Staff", "Thorsk Logistics", "logistics", 1200, "US", "thorsk.example",
             "valid", "", "", ""),
    # Canada, enterprise.
    "L172": ("Elodie", "Supply Chain Director", "Narrow Pine Freight", "logistics", 2200, "CA", "narrowpine.example",
             "valid", "", "", ""),
    # Canada, cold chain.
    "L179": ("Wes", "Warehouse Manager", "Bellroot Dairy", "food", 310, "CA", "bellroot.example",
             "valid", "", "", ""),
    # A title with a comma; executive in a restricted country.
    "L186": ("Aoife", "VP, Logistics", "Strenna Supply", "wholesale", 850, "IE", "strenna.example",
             "valid", "", "", ""),
    # "Operational" is not `operations`.
    "L193": ("Kasper", "Operational Excellence Manager", "Varrow Components", "automotive", 1400, "SE",
             "varrow.example", "valid", "", "", ""),
    # `head` is a level term but not an executive one.
    "L198": ("Rowan", "Head of Logistics", "Pellick Stores", "retail", 400, "GB", "pellick.example",
             "valid", "", "", ""),
    # `vice president` is an executive term.
    "L200": ("Mateo", "Vice President, Supply Chain", "Oskarn Auto Parts", "automotive", 1500, "US",
             "oskarn.example", "valid", "", "", ""),
    # A department and no level term: not a buying role.
    "L009": ("Hugo", "Warehouse Supervisor", "Frisk Haulage", "logistics", 330, "US", "frisk.example",
             "valid", "", "", ""),
    # `deputy` is a junior term.
    "L012": ("Ilse", "Deputy Head of Logistics", "Corvel Freight", "logistics", 900, "NL", "corvel.example",
             "valid", "", "", ""),
    # "Distributor" is not `distribution`.
    "L027": ("Nadia", "Distributor Relations Manager", "Ambrel Pharma", "pharma", 1100, "FR", "ambrel.example",
             "valid", "", "", ""),
}


def _weighted(rng: random.Random, weights: dict[str, int]) -> str:
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def _random_leads() -> list[dict]:
    rng = random.Random(SEED)
    roots = [head + tail for head in _ROOT_HEADS for tail in _ROOT_TAILS]
    rng.shuffle(roots)
    leads: list[dict] = []
    for position, root in enumerate(roots):
        if len(leads) >= RANDOM_LEADS:
            break
        industry = _weighted(rng, _INDUSTRY_WEIGHTS)
        country = _weighted(rng, _COUNTRY_WEIGHTS)
        bucket = rng.random()
        if bucket < 0.06:
            employees = rng.randint(8, 49)
        elif bucket < 0.11:
            employees = rng.randint(5200, 14000)
        elif bucket < 0.36:
            employees = rng.randint(1000, 4800)
        else:
            employees = rng.randint(60, 980)
        if country == CANADA and industry not in COLD_CHAIN_INDUSTRIES and employees < ENTERPRISE_FROM:
            # Canada is a large-account and cold-chain market only: no site_ops sequence there.
            employees = rng.randint(1000, 4800)
        company = f"{root} {rng.choice(_SUFFIXES[industry])}"
        customer = "yes" if position % 25 == 7 else ""  # one company in 25 already buys
        for _ in range(rng.choice([1, 2, 2, 3, 3, 4])):
            draw = rng.random()
            if country == CANADA:
                title = rng.choice(_OTHER_TITLES) if draw < 0.12 else rng.choice(_BUYER_TITLES)
            elif draw < 0.17:
                title = rng.choice(_EXEC_TITLES)
            elif draw < 0.88:
                title = rng.choice(_BUYER_TITLES)
            else:
                title = rng.choice(_OTHER_TITLES)
            status = rng.random()
            leads.append({
                "first_name": rng.choice(_FIRST_NAMES),
                "title": title,
                "company": company,
                "industry": industry,
                "employees": str(employees),
                "country": country,
                "domain": f"{root.lower()}.example",
                "email_status": "bounced" if status < 0.06 else "unknown" if status < 0.14 else "valid",
                "opted_out": "yes" if rng.random() < 0.03 else "",
                "existing_customer": customer,
                "last_contacted": _ago(rng.randint(5, 240)) if rng.random() < 0.2 else "",
            })
    leads = leads[:RANDOM_LEADS]
    rng.shuffle(leads)
    return leads


@lru_cache(maxsize=1)
def leads() -> list[dict]:
    """The lead list, the same every time: planted leads at their own ids,
    the rest in the places between."""
    filler = iter(_random_leads())
    total = RANDOM_LEADS + len(_PLANTED)
    rows = []
    for index in range(1, total + 1):
        lead_id = f"L{index:03d}"
        if lead_id in _PLANTED:
            values = [str(value) for value in _PLANTED[lead_id]]
            rows.append({"lead_id": lead_id, **dict(zip(LEAD_COLUMNS[1:], values))})
        else:
            rows.append({"lead_id": lead_id, **next(filler)})
    return rows


def leads_csv() -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=LEAD_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(leads())
    return out.getvalue()


# ── The reference: what the standard produces from the list ─────────────────

def _group_order(key: tuple[str, str]) -> tuple[int, int]:
    return SEGMENTS.index(key[0]), GROUPS.index(key[1])


@lru_cache(maxsize=1)
def reference() -> dict:
    excluded: dict[str, str] = {}
    assigned: dict[str, tuple[str, str]] = {}
    by_id = {lead["lead_id"]: lead for lead in leads()}
    for lead in leads():
        reason = exclusion_reason(lead)
        if reason:
            excluded[lead["lead_id"]] = reason
        else:
            assigned[lead["lead_id"]] = (segment(lead), country_group(lead["country"]))
    sequences = {key: send_days(*key) for key in sorted(set(assigned.values()), key=_group_order)}
    members = {key: [by_id[i] for i, k in assigned.items() if k == key] for key in sequences}
    merge_allowed = {
        key: {field for field, column in MERGE_COLUMNS.items() if all(lead[column] for lead in members[key])}
        for key in sequences
    }
    emails = {(seg, group, step): day for (seg, group), days in sequences.items()
              for step, day in enumerate(days, 1)}
    return {
        "excluded": excluded, "assigned": assigned, "sequences": sequences, "members": members,
        "merge_allowed": merge_allowed, "emails": emails,
        "sends": sum(len(sequences[key]) for key in assigned.values()),
    }


def answers() -> dict[int, int]:
    """A1 leads excluded, A2 leads assigned, A3 emails the first full run sends."""
    ref = reference()
    return {1: len(ref["excluded"]), 2: len(ref["assigned"]), 3: ref["sends"]}


# The reference copy: one email per segment and step, with {co} where the
# company goes. Each cites exactly one proof point.
_COPY: dict[tuple[str, int], str] = {
    ("executive", 1): (
        "Detention charges are a line most operations leaders only see after the fact. Pembrine Parts cut "
        "theirs by 41% in its first quarter on Brackenfold, once carriers booked their own dock slots. / "
        "Would a 20-minute walkthrough on the inbound volumes of {co} be worth your time?"),
    ("executive", 2): (
        "One number from the dock floor: Ostrel Fresh cut the average truck wait at its docks from 52 minutes "
        "to 17 minutes in 10 weeks. Shorter waits mean fewer trucks idling at the gate and fewer escalations "
        "reaching you. / If that matters for {co} this year, I can show you how it works."),
    ("executive", 3): (
        "I will close the loop here. If inbound scheduling comes up in planning, the short version: sites on "
        "Brackenfold book 90% of dock slots without a phone call or an email. / Reply with a good week and "
        "I will send a time."),
    ("cold_chain", 1): (
        "Every minute a chilled load waits at the gate is a minute outside the cold chain. Ostrel Fresh cut "
        "the average truck wait at its docks from 52 minutes to 17 minutes in 10 weeks by letting carriers "
        "book their own unloading slots. / Could a 20-minute walkthrough help {co}?"),
    ("cold_chain", 2): (
        "Most {{industry}} sites I speak to still book reefer slots by phone. Sites on Brackenfold book 90% "
        "of dock slots without a phone call or an email, so the dock office sees each temperature-controlled "
        "delivery before it arrives. / Worth a look?"),
    ("cold_chain", 3): (
        "Early and late arrivals cost money after the truck leaves too. Pembrine Parts cut detention charges "
        "by 41% in its first quarter on Brackenfold. For a cold-chain site the bigger gain is fewer loads "
        "sitting in the yard. / Happy to show the calendar."),
    ("cold_chain", 4): (
        "Last note from me. If chilled loads waiting at the dock are not a problem for {co}, no reply needed. "
        "If they are, setup takes weeks, not months: Ostrel Fresh went from 52 minutes to 17 minutes of "
        "average truck wait in 10 weeks."),
    ("enterprise", 1): (
        "Running inbound across several sites usually means several booking spreadsheets and a lot of phone "
        "calls. Sites on Brackenfold book 90% of dock slots without a phone call or an email, in one calendar "
        "every site and carrier shares. / Would a 20-minute walkthrough for {co} be useful?"),
    ("enterprise", 2): (
        "At group scale, detention is a budget line rather than an annoyance. Pembrine Parts cut detention "
        "charges by 41% in its first quarter on Brackenfold after carriers began booking their own slots. / "
        "I can show how that report reads across sites."),
    ("enterprise", 3): (
        "A site-level result: Ostrel Fresh cut the average truck wait at its docks from 52 minutes to 17 "
        "minutes in 10 weeks. Rolled out one site at a time, that is how a network shortens gate queues "
        "without adding dock staff. / Shall I send times for a walkthrough?"),
    ("enterprise", 4): (
        "I will stop here. If dock booking moves up the list for {co}, one figure to keep: sites on Brackenfold "
        "book 90% of dock slots without a phone call or an email. A reply naming the right person on your "
        "side is just as welcome."),
    ("site_ops", 1): (
        "How many booking calls does your dock office take before lunch? Sites on Brackenfold book 90% of dock "
        "slots without a phone call or an email: carriers pick a free slot and you see the inbound plan before "
        "the first truck arrives. / Want to see it in a 20-minute walkthrough?"),
    ("site_ops", 2): (
        "Gate queues are usually a booking problem, not a staffing one. Ostrel Fresh cut the average truck wait "
        "at its docks from 52 minutes to 17 minutes in 10 weeks with the same dock team. / Is that something "
        "{co} is working on this year?"),
    ("site_ops", 3): (
        "Last one from me. If carriers arriving early or late cost you detention charges, Pembrine Parts cut "
        "theirs by 41% in its first quarter on Brackenfold. / If the timing is wrong, a one-word reply is "
        "fine and I will not write again."),
}
# Every subject of the programme, by segment, country group and step.
_SUBJECTS: dict[tuple[str, str], list[str]] = {
    ("executive", "standard"): ["Detention charges at {{company}}", "52 to 17 minutes at the gate",
                                "Closing the loop on dock booking"],
    ("executive", "restricted"): ["Detention costs across your docks", "Shorter truck waits for {{company}}"],
    ("cold_chain", "standard"): ["Chilled loads waiting at the gate", "Booking reefer slots without the phone",
                                 "Detention and cold-chain dwell time", "Last note on chilled dock waits"],
    ("cold_chain", "restricted"): ["Cold-chain dock waits", "Reefer slot booking at {{company}}"],
    ("cold_chain", "canada"): ["Chilled trucks at your gate", "Phone-free reefer bookings",
                               "Detention fees on chilled loads", "One last note on chilled loads"],
    ("enterprise", "standard"): ["One dock calendar for every site", "Detention as a budget line",
                                 "Gate queues, site by site", "Stopping here on dock booking"],
    ("enterprise", "restricted"): ["Dock booking across your sites", "Detention across a site network"],
    ("enterprise", "canada"): ["A shared dock calendar for {{company}}", "Detention spend across sites",
                               "Shorter gate queues per site", "Last note on dock scheduling"],
    ("site_ops", "standard"): ["Booking calls before lunch", "Gate queues are a booking problem",
                               "Detention charges from early trucks"],
    ("site_ops", "restricted"): ["Fewer booking calls at the dock", "Shorter queues at your gate"],
}


def _email(segment_code: str, group: str, step: int) -> tuple[str, str]:
    allowed = reference()["merge_allowed"][(segment_code, group)]
    subject = _SUBJECTS[(segment_code, group)][step - 1]
    copy = _COPY[(segment_code, step)].replace("{co}", "{{company}}" if "company" in allowed else FALLBACKS["company"])
    for field in FALLBACKS:
        if field not in allowed:
            subject = subject.replace("{{" + field + "}}", FALLBACKS[field])
            copy = copy.replace("{{" + field + "}}", FALLBACKS[field])
    greeting = GREETING if "first_name" in allowed else GREETING_FALLBACK
    parts = [greeting, copy, SENDER.split()[0]]
    if group in COUNTRY_LINES:
        parts.append(COUNTRY_LINES[group])
    parts.append(f"{UNSUBSCRIBE} {ADDRESS}")
    return subject, PARAGRAPH_MARK.join(parts)


def reference_answer() -> str:
    """A reply that follows the standard to the letter: what a checker must pass."""
    ref = reference()
    out = ["Outbound programme for Brackenfold, from the lead list and the outbound standard.", ""]

    def block(name: str, header: list[str], rows: list[list]) -> None:
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
        out.extend([f"### {name}", "```csv", buffer.getvalue().rstrip("\n"), "```", ""])

    block("excluded.csv", ["lead_id", "reason"], [[i, reason] for i, reason in sorted(ref["excluded"].items())])
    block("assignments.csv", ["lead_id", "segment", "country_group"],
          [[i, seg, group] for i, (seg, group) in sorted(ref["assigned"].items())])
    rows = []
    for (seg, group), days in ref["sequences"].items():
        for step, day in enumerate(days, 1):
            subject, body = _email(seg, group, step)
            rows.append([seg, group, step, day, subject, body])
    block("sequences.csv", ["segment", "country_group", "step", "send_day", "subject", "body"], rows)
    figures_ = answers()
    out += [f"A1: {figures_[1]}", f"A2: {figures_[2]}", f"A3: {figures_[3]}", ""]
    return "\n".join(out)


# ── The documents the candidate reads ────────────────────────────────────────

def _quoted(terms: list[str]) -> str:
    return ", ".join(f"`{term}`" for term in terms)


def product_facts_md() -> str:
    # Bullets, not a numbered list: the only digits here are figures and the address.
    points = "\n".join(f"- {point}" for point in PROOF_POINTS)
    return f"""# Brackenfold: product facts

Brackenfold Dock is dock appointment scheduling for warehouses and
distribution centres. Carriers book their own unloading slots in a shared dock
calendar, the site sees every inbound truck before it arrives, and the dock
office stops taking booking calls.

## Proof points

{points}

## The offer

{OFFER}

## Sender

Every email is sent by {SENDER}, {SENDER_ROLE} at Brackenfold.

## Postal address

{ADDRESS}
"""


def outbound_standard_md() -> str:
    days = "\n".join(
        f"| `{seg}` | {len(STEP_DAYS[seg])} | {', '.join(str(d) for d in STEP_DAYS[seg])} |" for seg in SEGMENTS)
    return f"""# Brackenfold outbound standard

Apply this to leads.csv as written: do not improve on it, and do not skip a
lead. Today is {TODAY.isoformat()}. In leads.csv an empty `opted_out` or
`existing_customer` means no, and an empty `last_contacted` means never.

## How a term matches a title

Split the title into words at every character that is not a letter or a
digit, in lower case. A term matches when all its words appear in the title
as whole words, next to each other and in order. `head` matches "Head of
Logistics", not "Headcount Planner"; `coo` matches "COO", not "Coordinator".

## Step 1. Exclusions

Check every lead against these, in this order. The first that applies is the
lead's reason. An excluded lead gets no segment and no email.

1. `opted_out`: `opted_out` is `yes`.
2. `bounced`: `email_status` is `bounced` (`unknown` is not a reason).
3. `existing_customer`: `existing_customer` is `yes`.
4. `competitor`: `domain` is one of {_quoted(COMPETITOR_DOMAINS)}, or ends
   with a dot followed by one of them (a subdomain: `eu.dockhallow.example`).
   Ending with the name alone is not enough: `mydockhallow.example` is not one.
5. `recently_contacted`: `last_contacted` is {RECENT_DAYS} calendar days or fewer before today.
   {RECENT_DAYS} days before is excluded; {RECENT_DAYS + 1} is not.
6. `not_buying_role`: the title is not a buying role. A buying role
   contains no junior term, and either contains a standalone role or
   contains both a department term and a level term.
   - Standalone roles: {_quoted(STANDALONE_ROLES)}
   - Department terms: {_quoted(DEPARTMENT_TERMS)}
   - Level terms: {_quoted(LEVEL_TERMS)}
   - Junior terms: {_quoted(JUNIOR_TERMS)}
7. `company_size`: `employees` is under {MIN_EMPLOYEES} or over {MAX_EMPLOYEES:,}
   ({MIN_EMPLOYEES} and {MAX_EMPLOYEES:,} are inside).

## Step 2. Segments

Every lead left belongs to the first segment whose rule it meets.

1. `executive`: the title contains any of {_quoted(EXECUTIVE_TERMS)}.
2. `cold_chain`: `industry` is {' or '.join(f"`{name}`" for name in COLD_CHAIN_INDUSTRIES)}.
3. `enterprise`: `employees` is {ENTERPRISE_FROM:,} or more.
4. `site_ops`: every other lead.

## Step 3. Country groups

- `restricted`: `country` is one of {_quoted(RESTRICTED_COUNTRIES)}.
- `canada`: `country` is `{CANADA}`.
- `standard`: every other country.

## Step 4. Sequences

One sequence for each segment and country group with at least one assigned
lead, and none for any other. Each lead receives every step of its sequence.

| Segment | Steps | Send day of each step |
|---|---|---|
{days}

`standard` and `canada` get every step on these days. `restricted` gets steps
1 and 2 only, and step 2 at least {RESTRICTED_MIN_GAP} days after step 1: if
the segment's step 2 day is less than {RESTRICTED_MIN_GAP} days after its step
1 day, step 2 moves to step 1's day plus {RESTRICTED_MIN_GAP}.

## Step 5. Copy

- A subject is at most {SUBJECT_MAX} characters as written, spaces included, a
  merge field counted as written (`{{{{company}}}}` is 11). It does not start
  with {' or '.join(f"`{start}`" for start in BANNED_SUBJECT_STARTS)}.
- No two emails of the programme share a subject. Subjects that differ only
  in case, spaces, punctuation or merge fields count as the same.
- A body is one line: a space, a slash and a space (` / `) between
  paragraphs, never a line break. At most {BODY_MAX_WORDS} words: a word is anything
  between spaces holding a letter or a digit, so the slash is not one and a
  merge field is one. The greeting, the country sentence, the unsubscribe
  sentence and the address all count.
- A body opens with its greeting (Step 6). Its last words are the
  unsubscribe sentence followed by the postal address in product_facts.md.
  Unsubscribe sentence: `{UNSUBSCRIBE}`
- Every `restricted` email, and no other, contains:
  `{LEGITIMATE_INTEREST}`
- Every `canada` email, and no other, contains:
  `{CANADA_LINE}`
- Never, in any case, as whole words (a hyphen counts as a space):
  {_quoted(FORBIDDEN)}.
- Each email cites exactly one of the three proof points: it cites one when
  its subject or body states one of that proof point's figures.
- Every figure in digits in a subject or body is a figure of a proof point or
  of the offer, as written there; work out no new figure (a difference, a
  total). The only other digits allowed are in the postal address.

## Step 6. Merge fields

A merge field is written `{{{{name}}}}` and filled from the lead's own row,
from the column of the same name. Only these exist:
{_quoted(["{{" + field + "}}" for field in MERGE_COLUMNS])}.

A merge field may be used in a sequence's emails only if every lead assigned
to that sequence (segment and country group) has a value in its column.
Excluded leads do not count. Where one may not be used, write its fallback:
`{{{{company}}}}` -> `{FALLBACKS['company']}`, `{{{{industry}}}}` -> `{FALLBACKS['industry']}`.

Every body opens with `{GREETING}` where `{{{{first_name}}}}` may be used,
and with `{GREETING_FALLBACK}` where it may not.
"""


def fixtures() -> dict[str, str]:
    return {
        "leads.csv": leads_csv(),
        "outbound_standard.md": outbound_standard_md(),
        "product_facts.md": product_facts_md(),
    }


# ── The checker ───────────────────────────────────────────────────────────────

def _code(text: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", common.norm(str(text or "")[:200])).strip("_")


def _lead_id(text: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(text or "")[:40].upper())


def _step(text: object) -> int | None:
    match = re.search(r"\d{1,3}", str(text or "")[:40])
    return int(match.group(0)) if match else None


def _flat(text: object) -> str:
    """Lower case, one space between words, merge fields written `{{name}}`."""
    return _MERGE_SPACED.sub(lambda m: "{{" + m.group(1) + "}}", common.norm(str(text or "")[:_MAX_CELL]))


def _subject_key(subject: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _MERGE.sub("", subject[:_MAX_CELL].lower()))


_FOOTER = common.norm(f"{UNSUBSCRIBE} {ADDRESS}").rstrip(" .")
COPY_CHECKS = ["subject", "body", "footer", "country_line", "forbidden", "unknown_merge", "merge_fallback", "claims"]


def _copy_errors(key: tuple[str, str, int], row: dict | None) -> dict[str, int]:
    """What one expected email gets wrong: a missing one is one error on each check."""
    if row is None:
        return {name: 1 for name in COPY_CHECKS}
    seg, group, _step_number = key
    subject = common.cell(row, "subject")[:_MAX_CELL]
    body = common.cell(row, "body")[:_MAX_CELL]
    flat_body = _flat(body)
    every = f"{subject} {body}"
    errors = {name: 0 for name in COPY_CHECKS}
    errors["subject"] = int(not subject or len(subject) > SUBJECT_MAX or any(
        subject.lower().startswith(start.lower()) for start in BANNED_SUBJECT_STARTS))
    errors["body"] = int(not body or word_count(body) > BODY_MAX_WORDS)
    errors["footer"] = int(not flat_body.replace(" / ", " ").rstrip(" .").endswith(_FOOTER))
    for line_group, line in COUNTRY_LINES.items():
        errors["country_line"] += int((common.norm(line) in flat_body) != (group == line_group))
    words = common.words(every)
    errors["forbidden"] = sum(1 for phrase in FORBIDDEN if common.has_phrase(words, common.words(phrase)))
    used = merge_fields(every)
    errors["unknown_merge"] = sum(1 for name in used if name not in MERGE_COLUMNS)
    allowed = reference()["merge_allowed"].get((seg, group), set())
    greeting = GREETING if "first_name" in allowed else GREETING_FALLBACK
    errors["merge_fallback"] = int(
        any(name in MERGE_COLUMNS and name not in allowed for name in used)
        or not flat_body.startswith(common.norm(greeting)))
    found = figures(every.lower().replace(ADDRESS.lower(), " "))
    errors["claims"] = sum(1 for figure in found if figure not in ALLOWED_FIGURES)
    errors["claims"] += int(sum(1 for point in PROOF_FIGURES if point & set(found)) != 1)
    return errors


def facts(response_text: str, workflow: str = TASK_ID) -> dict:
    """Counts of what a reply got wrong. Every count measures work against the
    reference, so a missing file is that many errors, never zero: a reply that
    leaves a deliverable out earns nothing on its checks."""
    ref = reference()
    found = common.tables(response_text or "", FILES)
    known = {lead["lead_id"] for lead in leads()}
    excluded = {_lead_id(common.cell(r, "lead_id", "id")): r for r in (found["excluded.csv"] or [])}
    assigned = {_lead_id(common.cell(r, "lead_id", "id")): r for r in (found["assignments.csv"] or [])}
    excluded.pop("", None)
    assigned.pop("", None)
    listed = [_lead_id(common.cell(r, "lead_id", "id")) for name in ("excluded.csv", "assignments.csv")
              for r in (found[name] or [])]
    listed = [i for i in listed if i]

    rows = found["sequences.csv"] or []
    keys = [(_code(common.cell(r, "segment")), _code(common.cell(r, "country_group", "group")),
             _step(common.cell(r, "step"))) for r in rows]
    by_key = dict(zip(keys, rows))
    expected = ref["emails"]
    send_day_errors = sum(
        1 for key, day in expected.items()
        if key not in by_key or _step(common.cell(by_key[key], "send_day", "day")) != day)
    copy = {name: 0 for name in COPY_CHECKS}
    present: list[str] = []
    for key in expected:
        for name, count in _copy_errors(key, by_key.get(key)).items():
            copy[name] += count
        subject = common.cell(by_key[key], "subject") if key in by_key else ""
        if subject:
            present.append(_subject_key(subject))
    repeated = (len(expected) - len(present)) + (len(present) - len(set(present)))

    def wrong(columns: tuple[str, ...], index: int) -> int:
        return sum(
            1 for lead_id, target in ref["assigned"].items()
            if lead_id not in assigned or _code(common.cell(assigned[lead_id], *columns)) != target[index])

    return {
        "workflow_missing_file_count": sum(1 for name in FILES if found[name] is None),
        # Leads in neither file, listed twice, or not in the list at all.
        "workflow_lead_accounting_error_count": (
            len(known - set(listed)) + (len(listed) - len(set(listed))) + len(set(listed) - known)),
        "workflow_exclusion_error_count": len(set(ref["assigned"]) ^ (set(assigned) & known)),
        "workflow_wrong_reason_count": sum(
            1 for lead_id, reason in ref["excluded"].items()
            if lead_id not in excluded or _code(common.cell(excluded[lead_id], "reason", "reason_code")) != reason),
        "workflow_wrong_segment_count": wrong(("segment",), 0),
        "workflow_wrong_country_group_count": wrong(("country_group", "group"), 1),
        # Emails missing, extra, or given twice, per segment, country group and step.
        "workflow_sequence_row_error_count": (
            len(set(expected) - set(keys)) + len(set(keys) - set(expected)) + (len(keys) - len(set(keys)))),
        "workflow_send_day_error_count": send_day_errors,
        "workflow_subject_error_count": copy["subject"],
        "workflow_repeated_subject_count": repeated,
        "workflow_body_limit_error_count": copy["body"],
        "workflow_footer_error_count": copy["footer"],
        "workflow_country_line_error_count": copy["country_line"],
        "workflow_forbidden_phrase_count": copy["forbidden"],
        "workflow_unknown_merge_field_count": copy["unknown_merge"],
        "workflow_merge_fallback_error_count": copy["merge_fallback"],
        "workflow_claim_error_count": copy["claims"],
    }
