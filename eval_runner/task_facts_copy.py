"""The copy tasks: a launch copy pack (more copy tasks follow).

Each task is a workflow task (``eval_runner/workflows``): this one module
builds the files the candidate reads, holds a reference answer written to
them, and turns a reply into counts of what the reply got wrong. Each task
has a thin module of its own in ``eval_runner/workflows`` (the interface the
runner and ``scripts/gen_workflow_tasks.py`` read), registered in
``workflows.MODULES`` under the task's id; ``facts(response_text, workflow)``
here serves whichever is asked for.

Everything a check applies is a constant here, and the same constant writes
the sentence of the document that states the rule, so a rule cannot say one
thing to the candidate and another to the grader. Nothing is random, so the
files are the same bytes on every run
(``scripts/gen_workflow_tasks.py``).

    launch-copy-pack       a launch brief, a claims register, a spec sheet,
                           voice rules and a placements table in; 72 assets
                           for four products out

All brands, products, people, places, sites and figures are invented.
"""
from __future__ import annotations

import csv
import io
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from eval_runner.workflows import common

FIXTURE_DIR = Path("eval_runner") / "fixtures"
# task id -> (its files, its checker, its reference reply), each added by the
# task's own section below.
_TASKS: dict[str, tuple] = {}

# A reply is untrusted text: every cell and line is cut to a bound before it
# is matched, and no pattern here can backtrack on a long line.
_MAX_TEXT = 1000
_MAX_DOCUMENT = 40_000


# ── Shared readers ───────────────────────────────────────────────────────────

_NUMBER = re.compile(r"(?<![A-Za-z0-9.])\d+(?:,\d{3})*(?:\.\d+)?")


def figures(text: str) -> list[Decimal]:
    """Every number written in digits, as a value: "$1,199.00" is 1199, "99.5%"
    is 99.5, "3x" is 3, "30-night" is 30. A digit inside a word ("MIRA15") is
    not a figure of its own."""
    out = []
    for match in _NUMBER.finditer(str(text or "")[:_MAX_DOCUMENT]):
        try:
            out.append(Decimal(match.group(0).replace(",", "")))
        except InvalidOperation:
            continue
    return out


def _plain(value: Decimal) -> str:
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _day(value: date) -> str:
    return f"{value:%b} {value.day}"


def _decimal(value: str) -> Decimal:
    return Decimal(value.replace(",", ""))


def word_list(text: str) -> list[str]:
    """Words as the rules count them: lower case, apostrophes dropped, any
    other punctuation (a hyphen too) a space."""
    lowered = str(text or "")[:_MAX_DOCUMENT].lower().replace("'", "").replace("’", "")
    return re.findall(r"[a-z0-9]+", lowered)


def has_words(text: str, phrase: str) -> bool:
    """Whether the phrase's words appear in the text, whole and in order."""
    return common.has_phrase(word_list(text), word_list(phrase))


def _clean_cell(text: str) -> str:
    """A text cell as the copy that will run: surrounding space, backticks and
    one pair of quotes the reply put around it taken off."""
    core = str(text or "")[:_MAX_TEXT].strip()
    if len(core) >= 2 and core[0] == core[-1] == "`":
        core = core[1:-1].strip()
    if len(core) >= 2 and core[0] == '"' and core[-1] == '"':
        try:
            core = next(csv.reader([core]))[0]
        except (csv.Error, StopIteration, IndexError):
            core = core[1:-1]
    elif len(core) >= 2 and core[0] == "“" and core[-1] == "”":
        core = core[1:-1]
    return core.strip()


def keyed_lines(document: str | None, header_first: str) -> list[tuple[str, str]]:
    """(key, value) for each row of a two-column file: the key is everything
    before the first comma (or the first cell of a Markdown table row), the
    value is the rest. A value with commas need not be quoted to be read
    whole. The header row and a table's rule line are skipped."""
    if not document:
        return []
    rows = []
    for raw in document.splitlines():
        line = raw[:_MAX_TEXT + 100].strip()
        if not line:
            continue
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if not cells or not cells[0].strip("-: "):
                continue
            key, value = cells[0], "|".join(cells[1:])
        elif "," in line:
            key, value = line.split(",", 1)
        else:
            continue
        if common.norm(key).replace(" ", "_") == header_first:
            continue
        rows.append((key.strip().strip("`*_ \"'"), _clean_cell(value)))
    return rows


def csv_file(text: str, name: str) -> str | None:
    """A named CSV file's lines as written, or None when the reply does not
    carry it. The file is found exactly as ``common.tables`` finds one (the
    same naming lines, fences, list items and ends, and the last copy with
    something in it wins); only its rows are left unparsed, so a text with an
    unquoted comma is still read whole."""
    lines = (text if isinstance(text, str) else "").splitlines()
    found: list[str] | None = None
    index = 0
    while index < len(lines):
        if common.file_named(lines[index]) != name or not common._starts_file(lines, index, tabular=True):
            index += 1
            continue
        index += 1
        body: list[str] = []
        fenced = False
        while index < len(lines):
            line = lines[index]
            if common._is_fence(line):
                index += 1
                if fenced or body:
                    break
                fenced = True
                continue
            if not fenced:
                if common.file_named(line) or common._is_heading(line):
                    break
                if not line.strip():
                    index += 1
                    if body:
                        break
                    continue
            body.append(line)
            index += 1
        if found is None or any(line.strip() for line in body):
            found = body
    return None if found is None else "\n".join(found)


# ═════════════════════════════════════════════════════════════════════════════
# launch-copy-pack
# ═════════════════════════════════════════════════════════════════════════════

LAUNCH_ID = "launch-copy-pack"
LAUNCH_DIR = FIXTURE_DIR / LAUNCH_ID
LAUNCH_FILE = "copy_pack.csv"

BRAND = "Larkspur"
LAUNCH_DATE = date(2027, 2, 24)
SMS_OPENING = "Larkspur:"
SMS_ENDING = "Reply STOP to opt out."
CHANNELS = ("search", "social", "email", "sms", "push")


@dataclass(frozen=True)
class LaunchProduct:
    code: str
    name: str              # the short name copy uses: "Halo Mini"
    launch_price: str
    regular_price: str
    offer_ends: str        # as copy writes it: "Mar 7"
    link: str
    who: str
    features: tuple[str, ...]

    @property
    def full_name(self) -> str:
        return f"{BRAND} {self.name}"


LAUNCH_PRODUCTS: list[LaunchProduct] = [
    LaunchProduct("MINI", "Halo Mini", "$99", "$129", "Mar 7", "lrk.sp/mini",
                  "a small purifier for a desk, a nightstand or a small bedroom",
                  ("It runs on USB-C power.", "It has a built-in night light.",
                   "Auto mode and a sleep mode.", "There is no app and no Wi-Fi.")),
    LaunchProduct("ONE", "Halo One", "$199", "$249", "Mar 14", "lrk.sp/one",
                  "the everyday purifier for bedrooms and living rooms",
                  ("Wi-Fi, with schedules and filter reminders in the Larkspur app.",
                   "A washable pre-filter.", "Auto mode and a sleep mode.")),
    LaunchProduct("MAX", "Halo Max", "$329", "$399", "Mar 21", "lrk.sp/max",
                  "a purifier for large, open rooms",
                  ("Wi-Fi and the Larkspur app.", "A carbon filter and a washable pre-filter.",
                   "Auto mode and a sleep mode.")),
    LaunchProduct("PET", "Halo Pet", "$229", "$279", "Mar 14", "lrk.sp/pet",
                  "a purifier for homes with cats and dogs",
                  ("A carbon filter for odor.", "A washable pre-filter that catches pet hair.",
                   "Wi-Fi and the Larkspur app.", "Auto mode and a sleep mode.")),
]
LAUNCH_PRODUCT = {product.code: product for product in LAUNCH_PRODUCTS}
# What the launch team wants each product's copy to do. Words, no figures:
# the figures are the register's.
LAUNCH_NOTES: dict[str, str] = {
    "MINI": "Who buys it: renters, students and people who work from a small room, who want cleaner air "
            "where they sit or sleep and have no space for a floor unit. They ask whether it is loud at "
            "night and whether it needs a socket of its own. Lead with its size for the room it cleans and "
            "how quiet it is in sleep mode; the night light is the detail people remember. Do not suggest "
            "it is a smaller Halo One: it has its own filter and no app.",
    "ONE": "Who buys it: households replacing an old purifier or buying their first, for a bedroom or a "
           "living room. They compare room size, noise and running costs, and they like a schedule they can "
           "set and forget. Lead with the room size and the sleep mode; the app is the reason to choose it "
           "over a cheaper unit. Filter reminders answer the question people ask most after buying.",
    "MAX": "Who buys it: owners of open-plan homes, lofts and large living rooms, and small offices. They "
           "worry that one unit cannot cover the space. Lead with the room size, then the carbon filter. "
           "Smoke is a strong message where people have lived through wildfire seasons, and the register "
           "says where it may run.",
    "PET": "Who buys it: people with cats or dogs, often more than one, who notice dander, hair and odor. "
           "They have usually tried a general purifier. Lead with pet dander and odor; the pre-filter that "
           "catches pet hair is the practical detail. Do not make health claims about allergies, however "
           "often customers mention them.",
}
CHANNEL_NOTES = (
    "Search ads run on product and category searches. Social ads run in feeds, for each product's buyers below. "
    "Emails go to the pre-launch list, people who asked to hear about the launch. SMS goes to the opted-in "
    "list on the launch day. Push notifications go to people with the Larkspur app, who own a Breeze, a "
    "Drift or an Ember."
)
ALL_PRODUCTS = "all"


@dataclass(frozen=True)
class RegisterRow:
    product: str           # a product's short name, or "all"
    claim: str
    wording: str           # how copy writes the claim: its figure, or the phrase that makes it
    status: str            # approved, pending, withdrawn, internal
    channels: str = "all"  # "all", or channels joined by "; "
    valid_until: date | None = None
    note: str = ""

    def channel_set(self) -> set[str]:
        return set(CHANNELS) if self.channels == "all" else {c.strip() for c in self.channels.split(";")}

    def usable(self, product: LaunchProduct, channel: str) -> bool:
        return (self.status == "approved" and self.product in (product.name, ALL_PRODUCTS)
                and channel in self.channel_set()
                and (self.valid_until is None or self.valid_until >= LAUNCH_DATE))

    @property
    def is_phrase(self) -> bool:
        return not figures(self.wording)


APPROVED, PENDING, WITHDRAWN, INTERNAL = "approved", "pending", "withdrawn", "internal"
_EARLY = date(2027, 2, 20)
REGISTER: list[RegisterRow] = [
    # Every product.
    RegisterRow("all", "Warranty", "2-year warranty", APPROVED),
    RegisterRow("all", "Home trial", "30-night home trial", APPROVED, "search; social; email; push",
                note="Not in SMS: the trial terms need a link"),
    RegisterRow("all", "Shipping costs nothing", "free shipping", APPROVED),
    RegisterRow("all", "Auto mode sets the fan from the air quality sensor", "auto mode", APPROVED),
    RegisterRow("all", "Sleep mode dims the lights and slows the fan", "sleep mode", APPROVED),
    RegisterRow("all", "Launch day", "Feb 24", APPROVED, "email; push", note="Announcements only"),
    RegisterRow("all", "Meets the HEPA standard", "HEPA", WITHDRAWN, note="Retest pending"),
    RegisterRow("all", "Relief from allergies", "allergies", WITHDRAWN, note="A health claim"),
    RegisterRow("all", "Allergy relief", "allergy", WITHDRAWN, note="A health claim"),
    RegisterRow("all", "Helps with asthma", "asthma", WITHDRAWN, note="A health claim"),
    RegisterRow("all", "Removes viruses", "viruses", WITHDRAWN, note="Never tested"),
    RegisterRow("all", "Removes a virus", "virus", WITHDRAWN, note="Never tested"),
    RegisterRow("all", "Removes bacteria", "bacteria", WITHDRAWN, note="Never tested"),
    RegisterRow("all", "The quietest purifier", "quietest", WITHDRAWN, note="Not measured against others"),
    RegisterRow("all", "Ozone-free", "ozone-free", PENDING, note="Certificate expected in April"),
    RegisterRow("all", "Energy Star certified", "Energy Star", PENDING, note="Application filed"),
    RegisterRow("all", "Sold in more than 40 countries", "40 countries", INTERNAL, note="Distribution plan"),
    RegisterRow("all", "Units ordered for launch", "60,000 units", INTERNAL, note="Confidential"),
    # Halo Mini.
    RegisterRow("Halo Mini", "Launch price, until the launch offer ends", "$99", APPROVED),
    RegisterRow("Halo Mini", "The launch offer ends", "Mar 7", APPROVED),
    RegisterRow("Halo Mini", "Regular price", "$129", APPROVED),
    RegisterRow("Halo Mini", "Room size it cleans", "rooms up to 200 sq ft", APPROVED),
    RegisterRow("Halo Mini", "Air changes an hour in a 200 sq ft room", "5 air changes an hour", APPROVED,
                "search; email"),
    RegisterRow("Halo Mini", "Noise in sleep mode", "19 dB", APPROVED),
    RegisterRow("Halo Mini", "Filtration, independent lab", "99.5% of particles as small as 0.3 microns", APPROVED),
    RegisterRow("Halo Mini", "Filter life", "up to 6 months", APPROVED),
    RegisterRow("Halo Mini", "A built-in night light", "night light", APPROVED),
    RegisterRow("Halo Mini", "Runs on USB-C power", "USB-C", APPROVED),
    RegisterRow("Halo Mini", "Early-bird price", "$89", APPROVED, "email", _EARLY, "Pre-launch list only"),
    RegisterRow("Halo Mini", "Room size, first draft of the brief", "250 sq ft", WITHDRAWN,
                note="Written before testing; the tested size is 200 sq ft"),
    RegisterRow("Halo Mini", "Noise of the prototype", "16 dB", WITHDRAWN, note="Shipping units measure 19 dB"),
    RegisterRow("Halo Mini", "Filtration to the 99.97% standard", "99.97%", PENDING, note="Retest finishes in April"),
    RegisterRow("Halo Mini", "Control from the Larkspur app", "app", PENDING, note="Planned for 2028"),
    RegisterRow("Halo Mini", "Wi-Fi", "Wi-Fi", WITHDRAWN, note="Cut from the design"),
    RegisterRow("Halo Mini", "Retailer price", "$109", INTERNAL, note="Wholesale terms"),
    RegisterRow("Halo Mini", "Battery runtime", "8 hours", WITHDRAWN, note="The battery was cut from the design"),
    # Halo One.
    RegisterRow("Halo One", "Launch price, until the launch offer ends", "$199", APPROVED),
    RegisterRow("Halo One", "The launch offer ends", "Mar 14", APPROVED),
    RegisterRow("Halo One", "Regular price", "$249", APPROVED),
    RegisterRow("Halo One", "Room size it cleans", "rooms up to 480 sq ft", APPROVED),
    RegisterRow("Halo One", "Air changes an hour in a 480 sq ft room", "4 air changes an hour", APPROVED),
    RegisterRow("Halo One", "Noise in sleep mode", "22 dB", APPROVED),
    RegisterRow("Halo One", "Filtration, independent lab", "99.5% of particles as small as 0.3 microns", APPROVED),
    RegisterRow("Halo One", "Filter life", "up to 12 months", APPROVED),
    RegisterRow("Halo One", "Control from the Larkspur app", "app", APPROVED),
    RegisterRow("Halo One", "Wi-Fi", "Wi-Fi", APPROVED),
    RegisterRow("Halo One", "Filter reminders in the app", "filter reminders", APPROVED),
    RegisterRow("Halo One", "A washable pre-filter", "washable pre-filter", APPROVED),
    RegisterRow("Halo One", "Early-bird price", "$179", APPROVED, "email", _EARLY, "Pre-launch list only"),
    RegisterRow("Halo One", "Coverage, first draft of the brief", "600 sq ft", WITHDRAWN,
                note="Written before testing; the tested size is 480 sq ft"),
    RegisterRow("Halo One", "Noise of the prototype", "18 dB", WITHDRAWN, note="Shipping units measure 22 dB"),
    RegisterRow("Halo One", "Filtration to the 99.97% standard", "99.97%", PENDING, note="Retest finishes in April"),
    RegisterRow("Halo One", "Quieter than the Larkspur Breeze", "40% quieter", INTERNAL, note="Never measured"),
    RegisterRow("Halo One", "Pre-orders so far", "4,200 pre-orders", INTERNAL, note="Confidential"),
    RegisterRow("Halo One", "Helps clear smoke", "smoke", PENDING, note="Test report due in March"),
    RegisterRow("Halo One", "Captures pet dander", "pet dander", PENDING, note="Not tested on this model"),
    RegisterRow("Halo One", "Retailer price", "$219", INTERNAL, note="Wholesale terms"),
    # Halo Max.
    RegisterRow("Halo Max", "Launch price, until the launch offer ends", "$329", APPROVED),
    RegisterRow("Halo Max", "The launch offer ends", "Mar 21", APPROVED),
    RegisterRow("Halo Max", "Regular price", "$399", APPROVED),
    RegisterRow("Halo Max", "Room size it cleans", "rooms up to 1,100 sq ft", APPROVED),
    RegisterRow("Halo Max", "Air changes an hour in a 1,100 sq ft room", "3 air changes an hour", APPROVED,
                "social; email"),
    RegisterRow("Halo Max", "Noise in sleep mode", "26 dB", APPROVED),
    RegisterRow("Halo Max", "Filtration, independent lab", "99.7% of particles as small as 0.3 microns", APPROVED),
    RegisterRow("Halo Max", "Filter life", "up to 12 months", APPROVED),
    RegisterRow("Halo Max", "Control from the Larkspur app", "app", APPROVED),
    RegisterRow("Halo Max", "Wi-Fi", "Wi-Fi", APPROVED),
    RegisterRow("Halo Max", "A washable pre-filter", "washable pre-filter", APPROVED),
    RegisterRow("Halo Max", "A carbon filter", "carbon filter", APPROVED),
    RegisterRow("Halo Max", "Helps clear smoke", "smoke", APPROVED, "email", note="Email only: the test report "
                "has to be one click away"),
    RegisterRow("Halo Max", "Coverage, first draft of the brief", "1,400 sq ft", WITHDRAWN,
                note="Written before testing; the tested size is 1,100 sq ft"),
    RegisterRow("Halo Max", "Noise in sleep mode, revised fan", "24 dB", PENDING, note="New fan from May"),
    RegisterRow("Halo Max", "Filtration to the 99.97% standard", "99.97%", PENDING, note="Retest finishes in April"),
    RegisterRow("Halo Max", "Retailer price", "$349", INTERNAL, note="Wholesale terms"),
    RegisterRow("Halo Max", "Early-bird price", "$299", APPROVED, "email", _EARLY, "Pre-launch list only"),
    # Halo Pet.
    RegisterRow("Halo Pet", "Launch price, until the launch offer ends", "$229", APPROVED),
    RegisterRow("Halo Pet", "The launch offer ends", "Mar 14", APPROVED),
    RegisterRow("Halo Pet", "Regular price", "$279", APPROVED),
    RegisterRow("Halo Pet", "Room size it cleans", "rooms up to 480 sq ft", APPROVED),
    RegisterRow("Halo Pet", "Noise in sleep mode", "24 dB", APPROVED),
    RegisterRow("Halo Pet", "Filtration, independent lab", "99.5% of particles as small as 0.3 microns", APPROVED),
    RegisterRow("Halo Pet", "Filter life", "up to 6 months", APPROVED),
    RegisterRow("Halo Pet", "Captures pet dander", "pet dander", APPROVED),
    RegisterRow("Halo Pet", "A carbon filter", "carbon filter", APPROVED),
    RegisterRow("Halo Pet", "Reduces pet odor", "odor", APPROVED),
    RegisterRow("Halo Pet", "The pre-filter catches pet hair", "pet hair", APPROVED, "social; email"),
    RegisterRow("Halo Pet", "A washable pre-filter", "washable pre-filter", APPROVED),
    RegisterRow("Halo Pet", "Control from the Larkspur app", "app", APPROVED),
    RegisterRow("Halo Pet", "Wi-Fi", "Wi-Fi", APPROVED),
    RegisterRow("Halo Pet", "Captures 98% of pet dander", "98% of pet dander", PENDING, note="Lab report in review"),
    RegisterRow("Halo Pet", "Coverage, first draft of the brief", "500 sq ft", WITHDRAWN,
                note="Written before testing; the tested size is 480 sq ft"),
    RegisterRow("Halo Pet", "Air changes an hour", "4 air changes an hour", PENDING, note="Measured on Halo One only"),
    RegisterRow("Halo Pet", "Retailer price", "$239", INTERNAL, note="Wholesale terms"),
    RegisterRow("Halo Pet", "Early-bird price", "$199", APPROVED, "email", _EARLY, "Pre-launch list only"),
    # Accessories, claimed in the product's own copy in the channels listed.
    RegisterRow("Halo Mini", "Replacement filter price", "$19", APPROVED, "email; push"),
    RegisterRow("Halo One", "Replacement filter price", "$39", APPROVED, "email; push"),
    RegisterRow("Halo Max", "Replacement filter price", "$59", APPROVED, "email; push"),
    RegisterRow("Halo Pet", "Replacement filter price", "$45", APPROVED, "email; push"),
    RegisterRow("all", "A filter subscription saves", "15% on filters", APPROVED, "email",
                note="Subscription page only"),
    RegisterRow("all", "Filter subscription launch discount", "25% on filters", APPROVED, "email",
                date(2027, 1, 31), "Holiday promotion"),
    RegisterRow("Halo One", "Stand accessory price", "$49", PENDING, note="Stand ships in May"),
    RegisterRow("Halo Max", "Wheeled base", "wheeled base", PENDING, note="Ships in June"),
    RegisterRow("Halo Pet", "Washable pet-hair screen", "pet-hair screen", WITHDRAWN, note="Cut before launch"),
]
# Larkspur products already on sale: their claims are approved, for them.
REGISTER += [
    RegisterRow(name, claim, wording, APPROVED, channels)
    for name, rows in (
        ("Breeze", [("Price", "$179", "all"), ("Room size it cleans", "rooms up to 350 sq ft", "all"),
                    ("Noise in sleep mode", "25 dB", "all"), ("Filter life", "up to 9 months", "all"),
                    ("Filtration", "99% of particles as small as 0.3 microns", "all"),
                    ("Replacement filter price", "$35", "email; push"), ("A washable pre-filter",
                    "washable pre-filter", "all"), ("Air changes an hour", "3 air changes an hour", "all"),
                    ("Timer", "8-hour timer", "all"), ("Colors", "3 colors", "social; email")]),
        ("Drift", [("Price", "$149", "all"), ("Tank size", "4 liter tank", "all"),
                   ("Runtime on a full tank", "up to 40 hours", "all"), ("Room size", "rooms up to 400 sq ft", "all"),
                   ("Noise", "28 dB", "all"), ("Mist settings", "5 mist settings", "all"),
                   ("Humidity sensor", "humidity sensor", "all"), ("Top-fill tank", "top-fill tank", "all"),
                   ("Essential oil tray", "essential oil tray", "social; email"),
                   ("Replacement wick price", "$15", "email; push")]),
        ("Ember", [("Price", "$129", "all"), ("Heats rooms up to", "rooms up to 300 sq ft", "all"),
                   ("Heat settings", "3 heat settings", "all"), ("Tip-over switch", "tip-over switch", "all"),
                   ("Cool-touch case", "cool-touch case", "all"), ("Timer", "12-hour timer", "all"),
                   ("Noise", "35 dB", "all"), ("Power", "1,500 watts", "all"),
                   ("Thermostat", "digital thermostat", "all"), ("Remote control", "remote control", "social; email")]),
    )
    for claim, wording, channels in rows
]
OTHER_PRODUCTS = ("Breeze", "Drift", "Ember")
PHRASES = sorted({row.wording for row in REGISTER if row.is_phrase}, key=str.lower)

# The engineering spec sheet: figures for reference, none of them a claim.
SPEC_SHEET: dict[str, tuple[str, str, str, str]] = {
    "Clean air delivery rate (CFM)": ("130", "260", "540", "250"),
    "Recommended room, engineering estimate (sq ft)": ("220", "520", "1,200", "520"),
    "Noise in sleep mode, bench test (dB)": ("18", "21", "25", "23"),
    "Particles captured at 0.3 microns, bench test (%)": ("99.6", "99.6", "99.8", "99.6"),
    "Filter life, engineering estimate (months)": ("8", "14", "14", "8"),
    "Air changes an hour, engineering estimate": ("6", "5", "4", "5"),
    "Power at top speed (W)": ("18", "36", "58", "38"),
    "Power in sleep mode (W)": ("2", "3", "5", "3"),
    "Fan speeds": ("3", "4", "5", "4"),
    "Noise at top speed (dB)": ("44", "48", "53", "49"),
    "Weight (kg)": ("1.4", "3.6", "7.9", "3.8"),
    "Height (cm)": ("24", "52", "71", "53"),
    "Footprint (cm)": ("17 x 17", "26 x 26", "34 x 34", "26 x 26"),
    "Filter part number": ("LF-M1", "LF-O1", "LF-X1", "LF-P1"),
    "Sensor": ("PM2.5", "PM2.5", "PM2.5 and VOC", "PM2.5 and VOC"),
    "Cord length (m)": ("1.5", "1.8", "1.8", "1.8"),
    "Standby power (W)": ("0.5", "0.5", "0.8", "0.5"),
    "Filter stages": ("2", "3", "3", "4"),
    "Display brightness levels": ("2", "3", "3", "3"),
    "Run time to filter alert (hours)": ("4,000", "8,000", "8,000", "4,000"),
    "Operating temperature (F)": ("41 to 95", "41 to 95", "41 to 95", "41 to 95"),
    "Shipping box (in)": ("10 x 10 x 12", "14 x 14 x 24", "18 x 18 x 31", "14 x 14 x 24"),
}

BANNED_WORDS = ["best", "cleanest", "purest", "revolutionary", "miracle", "cure", "cures", "toxins",
                "medical-grade", "hospital-grade", "guarantee", "guaranteed"]
FREE_WORD = "free"
FREE_PHRASE = "free shipping"

# The characters an SMS may hold and still be sent as one 160-character
# message. Any other character sends the whole message as Unicode.
SMS_CHARACTERS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,:;!?'\"-()/&%+=@#*$")
SMS_UNICODE_LIMIT = 70


@dataclass(frozen=True)
class Placement:
    code: str
    name: str
    channel: str
    count: int
    limit: int
    price: bool
    must: str = ""          # what each asset must include: "", "full name", "name", "brand", "offer end"
    first_only: bool = False
    must_not: tuple[str, ...] = ()


PLACEMENTS: list[Placement] = [
    Placement("SH", "Search ad headline", "search", 5, 30, False, "full name", first_only=True),
    Placement("SD", "Search ad description", "search", 2, 90, True, "brand"),
    Placement("FP", "Social ad primary text", "social", 2, 125, True, "full name"),
    Placement("FH", "Social ad headline", "social", 2, 40, False, "name"),
    Placement("ES", "Email subject line", "email", 2, 45, False, must_not=(FREE_WORD,)),
    Placement("EP", "Email preheader", "email", 2, 85, True, "offer end"),
    Placement("SM", "SMS", "sms", 1, 160, True),
    Placement("PT", "Push notification title", "push", 1, 40, False, must_not=(BRAND,)),
    Placement("PB", "Push notification body", "push", 1, 100, True),
]
PLACEMENT = {placement.code: placement for placement in PLACEMENTS}
SMS_CODE = "SM"
MUST_LABELS = {"full name": "the product's full name", "name": "the product's name", "brand": f"`{BRAND}`",
               "offer end": "the date its launch offer ends"}


def launch_assets() -> list[tuple[str, LaunchProduct, Placement]]:
    return [(f"{product.code}-{placement.code}-{n:02d}", product, placement)
            for product in LAUNCH_PRODUCTS for placement in PLACEMENTS for n in range(1, placement.count + 1)]


def required_strings(asset_id: str, product: LaunchProduct, placement: Placement) -> tuple[str, ...]:
    if not placement.must or (placement.first_only and not asset_id.endswith("-01")):
        return ()
    return ({"full name": product.full_name, "name": product.name, "brand": BRAND,
             "offer end": product.offer_ends}[placement.must],)


# ── The reference copy, written to the register and the rules ───────────────

LAUNCH_COPY: dict[str, str] = {
    "MINI-SH-01": "Larkspur Halo Mini Purifier",
    "MINI-SH-02": "Cleans Rooms Up to 200 sq ft",
    "MINI-SH-03": "Quiet 19 dB Sleep Mode",
    "MINI-SH-04": "Built-In Night Light",
    "MINI-SH-05": "5 Air Changes an Hour",
    "MINI-SD-01": "Larkspur Halo Mini cleans rooms up to 200 sq ft. $99 until Mar 7, then $129.",
    "MINI-SD-02": "Larkspur Halo Mini runs on USB-C, with a night light and a 19 dB sleep mode.",
    "MINI-FP-01": "Meet Larkspur Halo Mini: cleaner air for rooms up to 200 sq ft, with a 19 dB sleep mode. "
                  "$99 until Mar 7.",
    "MINI-FP-02": "Larkspur Halo Mini captures 99.5% of particles as small as 0.3 microns. Try it for 30 nights "
                  "at home.",
    "MINI-FH-01": "Halo Mini, sized for a nightstand",
    "MINI-FH-02": "Halo Mini, with a built-in night light",
    "MINI-ES-01": "Meet Larkspur Halo Mini",
    "MINI-ES-02": "A night light that cleans the air",
    "MINI-EP-01": "Larkspur Halo Mini is $99 until Mar 7. Available Feb 24, with free shipping.",
    "MINI-EP-02": "Rooms up to 200 sq ft and the launch price until Mar 7, with free shipping.",
    "MINI-SM-01": "Larkspur: Halo Mini is here. Cleaner air for rooms up to 200 sq ft, $99 until Mar 7. "
                  "lrk.sp/mini Reply STOP to opt out.",
    "MINI-PT-01": "Halo Mini is here",
    "MINI-PB-01": "Cleaner air for small rooms, $99 until Mar 7. Free shipping on every order.",
    "ONE-SH-01": "Larkspur Halo One Purifier",
    "ONE-SH-02": "Rooms Up to 480 sq ft",
    "ONE-SH-03": "Quiet 22 dB Sleep Mode",
    "ONE-SH-04": "Control It From the App",
    "ONE-SH-05": "4 Air Changes an Hour",
    "ONE-SD-01": "Larkspur Halo One cleans rooms up to 480 sq ft. $199 until Mar 14, then $249.",
    "ONE-SD-02": "Larkspur Halo One has Wi-Fi, filter reminders in the app and a washable pre-filter.",
    "ONE-FP-01": "Meet Larkspur Halo One: cleaner air in rooms up to 480 sq ft, and a 22 dB sleep mode. "
                 "$199 until Mar 14.",
    "ONE-FP-02": "Larkspur Halo One captures 99.5% of particles as small as 0.3 microns. Set its schedule in "
                 "the app.",
    "ONE-FH-01": "Halo One runs at 22 dB in sleep mode",
    "ONE-FH-02": "Halo One: schedules from the app",
    "ONE-ES-01": "Meet Larkspur Halo One",
    "ONE-ES-02": "Cleaner air in rooms up to 480 sq ft",
    "ONE-EP-01": "Larkspur Halo One is $199 until Mar 14, then $249. Available Feb 24.",
    "ONE-EP-02": "A filter that lasts up to 12 months, and the launch price until Mar 14.",
    "ONE-SM-01": "Larkspur: Halo One is here. Rooms up to 480 sq ft and a 22 dB sleep mode, $199 until Mar 14. "
                 "lrk.sp/one Reply STOP to opt out.",
    "ONE-PT-01": "Halo One is here",
    "ONE-PB-01": "Cleaner air for rooms up to 480 sq ft. $199 until Mar 14.",
    "MAX-SH-01": "Larkspur Halo Max Purifier",
    "MAX-SH-02": "Big Rooms Up to 1,100 sq ft",
    "MAX-SH-03": "Captures 99.7% of Particles",
    "MAX-SH-04": "Carbon Filter Included",
    "MAX-SH-05": "Wi-Fi and App Control",
    "MAX-SD-01": "Larkspur Halo Max cleans rooms up to 1,100 sq ft. $329 until Mar 21, then $399.",
    "MAX-SD-02": "Larkspur Halo Max has a carbon filter and a washable pre-filter, with a 2-year warranty.",
    "MAX-FP-01": "Meet Larkspur Halo Max: cleaner air in open rooms up to 1,100 sq ft, 3 air changes an hour. "
                 "$329 until Mar 21.",
    "MAX-FP-02": "Larkspur Halo Max captures 99.7% of particles as small as 0.3 microns, with a 26 dB sleep "
                 "mode.",
    "MAX-FH-01": "Halo Max cleans up to 1,100 sq ft",
    "MAX-FH-02": "Halo Max: Wi-Fi, the app and auto mode",
    "MAX-ES-01": "Meet Larkspur Halo Max",
    "MAX-ES-02": "Help clear smoke from big rooms",
    "MAX-EP-01": "Larkspur Halo Max is $329 until Mar 21, then $399. Available Feb 24.",
    "MAX-EP-02": "3 air changes an hour in 1,100 sq ft, and the launch price until Mar 21.",
    "MAX-SM-01": "Larkspur: Halo Max is here. Cleaner air for rooms up to 1,100 sq ft, $329 until Mar 21. "
                 "lrk.sp/max Reply STOP to opt out.",
    "MAX-PT-01": "Halo Max is here",
    "MAX-PB-01": "Big rooms, cleaner air: up to 1,100 sq ft. $329 until Mar 21.",
    "PET-SH-01": "Larkspur Halo Pet Purifier",
    "PET-SH-02": "Captures Pet Dander",
    "PET-SH-03": "Carbon Filter for Pet Odor",
    "PET-SH-04": "Cleans Rooms Up to 480 sq ft",
    "PET-SH-05": "Quiet 24 dB Sleep Mode",
    "PET-SD-01": "Larkspur Halo Pet captures pet dander in rooms up to 480 sq ft. $229 until Mar 14.",
    "PET-SD-02": "Larkspur Halo Pet has a carbon filter for odor and a washable pre-filter. Free shipping.",
    "PET-FP-01": "Meet Larkspur Halo Pet: it captures pet dander, and its pre-filter catches pet hair. "
                 "$229 until Mar 14, then $279.",
    "PET-FP-02": "Larkspur Halo Pet captures 99.5% of particles as small as 0.3 microns. Try it for 30 nights "
                 "at home.",
    "PET-FH-01": "Halo Pet catches pet hair",
    "PET-FH-02": "Halo Pet: a carbon filter for odor",
    "PET-ES-01": "Meet Larkspur Halo Pet",
    "PET-ES-02": "Less pet odor, less pet hair",
    "PET-EP-01": "Larkspur Halo Pet is $229 until Mar 14, then $279. Available Feb 24.",
    "PET-EP-02": "A carbon filter for odor, a 2-year warranty, and the launch price until Mar 14.",
    "PET-SM-01": "Larkspur: Halo Pet is here. It captures pet dander in rooms up to 480 sq ft, $229 until Mar 14. "
                 "lrk.sp/pet Reply STOP to opt out.",
    "PET-PT-01": "Halo Pet is here",
    "PET-PB-01": "Less pet odor at home. $229 until Mar 14, with free shipping.",
}


# ── The rules, applied to one text ───────────────────────────────────────────

def sms_limit(text: str) -> int:
    """160, or 70 when one character sends the message as Unicode."""
    return PLACEMENT[SMS_CODE].limit if all(ch in SMS_CHARACTERS for ch in text) else SMS_UNICODE_LIMIT


def limit_for(placement: Placement, text: str) -> int:
    return sms_limit(text) if placement.code == SMS_CODE else placement.limit


def banned_in(text: str) -> int:
    """Banned words and phrases (whole words, any case, a hyphen splits a
    word), the word free anywhere but in "free shipping", and each !."""
    words = word_list(text)
    count = sum(1 for word in BANNED_WORDS if common.has_phrase(words, word_list(word)))
    count += sum(1 for index, word in enumerate(words)
                 if word == FREE_WORD and words[index + 1:index + 2] != ["shipping"])
    return count + str(text).count("!")


def exclusions_in(placement: Placement, text: str) -> int:
    """The word free as a word; anything else as its characters, any case."""
    return sum(1 for string in placement.must_not
               if (has_words(text, string) if string == FREE_WORD else common.norm(string) in common.norm(text)))


def usable_figures(product: LaunchProduct, channel: str) -> frozenset[Decimal]:
    return frozenset(value for row in REGISTER if row.usable(product, channel) for value in figures(row.wording))


def uncleared_figures(product: LaunchProduct, channel: str, text: str) -> int:
    """Figures the register does not let this product's copy state in this channel."""
    allowed = usable_figures(product, channel)
    return sum(1 for value in figures(text) if value not in allowed)


def uncleared_claims(product: LaunchProduct, channel: str, text: str) -> int:
    """Claim phrases from the register that copy of this product may not make
    in this channel: pending, withdrawn or internal, another product's, or
    approved for other channels only, or expired by the launch day."""
    return sum(1 for phrase in PHRASES if has_words(text, phrase) and not any(
        row.wording == phrase and row.usable(product, channel) for row in REGISTER))


def other_products_named(product: LaunchProduct, text: str) -> int:
    """Other Larkspur products the text names: another Halo, or one already on sale."""
    names = [other.name for other in LAUNCH_PRODUCTS if other is not product] + list(OTHER_PRODUCTS)
    return sum(1 for name in names if has_words(text, name))


def states_price(product: LaunchProduct, text: str) -> bool:
    """A $ amount, or the product's own launch or regular price written
    without its $ ("199 dollars")."""
    own = {_decimal(product.launch_price.strip("$")), _decimal(product.regular_price.strip("$"))}
    return bool(re.search(r"\$\s?\d", text)) or any(value in own for value in figures(text))


def price_rule_errors(product: LaunchProduct, placement: Placement, text: str) -> int:
    """A price where the placement allows none; the launch price without the
    date its offer ends; the regular price without the launch price."""
    values = set(figures(text))
    launch = _decimal(product.launch_price.strip("$"))
    regular = _decimal(product.regular_price.strip("$"))
    errors = 0
    if not placement.price and states_price(product, text):
        errors += 1
    if launch in values and not missing_strings(text, (product.offer_ends,)) == 0:
        errors += 1
    if regular in values and launch not in values:
        errors += 1
    return errors


def sms_format_errors(product: LaunchProduct, text: str) -> int:
    core = text.strip()
    return ((not core.lower().startswith(SMS_OPENING.lower()))
            + (product.link.lower() not in core.lower())
            + (not core.lower().endswith(SMS_ENDING.lower())))


def missing_strings(text: str, strings: tuple[str, ...]) -> int:
    flat = common.norm(text)
    return sum(1 for string in strings if common.norm(string) not in flat)


def opening_words(text: str) -> list[str]:
    """Words as the headline rule reads them: lower case, apostrophes dropped,
    a number with its decimal point and its % sign one word, & a word, any
    other punctuation a space."""
    lowered = str(text or "")[:_MAX_TEXT].lower().replace("'", "").replace("\u2019", "")
    return re.findall(r"\d+(?:[.,]\d+)*%?|[a-z0-9]+|&", lowered)


def opening(text: str) -> tuple[str, ...]:
    return tuple(opening_words(text)[:2])


def same_copy(text: str) -> str:
    return " ".join(word_list(text))


# ── The reference reply and the documents ────────────────────────────────────

def launch_reference_answer() -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["asset_id", "text"])
    for asset_id, _product, _placement in launch_assets():
        writer.writerow([asset_id, LAUNCH_COPY[asset_id]])
    return "\n".join([
        "The launch copy pack for the four Halo purifiers, from the brief, the claims register, the voice rules "
        "and the placements table.",
        "",
        f"### {LAUNCH_FILE}",
        "```csv",
        buffer.getvalue().rstrip("\n"),
        "```",
        "",
    ])


def launch_brief_md() -> str:
    products = []
    for product in LAUNCH_PRODUCTS:
        features = "\n".join(f"- {feature}" for feature in product.features)
        products.append(f"""## {product.full_name} (code {product.code})

{product.name} is {product.who}. Its SMS link is `{product.link}`.

{features}

{LAUNCH_NOTES[product.code]}""")
    return f"""# Larkspur Halo: launch brief

{BRAND} launches four air purifiers on {_day(LAUNCH_DATE)}, {LAUNCH_DATE.year}: the Halo Mini, Halo One,
Halo Max and Halo Pet. Each has its own launch price until its own launch
offer ends; the prices and the dates are in claims_register.csv.

What copy may say about a product is decided by the claims register, not by
this brief or the spec sheet. The brief tells you what each product is for.

## Channels

{CHANNEL_NOTES}

{chr(10).join(chr(10) + text for text in products).strip()}
"""


# Last year's launch, as it ran: the Breeze's figures, and wording the 2025
# rules allowed and this launch's do not.
BREEZE_LAUNCH: list[tuple[str, str]] = [
    ("Search ad headline", "Larkspur Breeze Air Purifier"),
    ("Search ad headline", "Larkspur Breeze: Quiet Air"),
    ("Search ad headline", "Cleans Rooms Up to 350 sq ft"),
    ("Search ad headline", "Only 25 dB in Sleep Mode"),
    ("Search ad headline", "Now $179, Free Shipping"),
    ("Search ad headline", "HEPA-Style Filtration"),
    ("Search ad headline", "The Quietest Breeze Yet"),
    ("Search ad headline", "8-Hour Timer Built In"),
    ("Search ad headline", "3 Colors to Choose From"),
    ("Search ad headline", "Try It Free for 30 Days"),
    ("Search ad description", "Larkspur Breeze cleans rooms up to 350 sq ft and runs at 25 dB. Just $179!"),
    ("Search ad description", "Allergy season? Breeze captures 99% of particles. Free returns, 2-year warranty."),
    ("Search ad description", "A washable pre-filter, an 8-hour timer and filters that last up to 9 months."),
    ("Search ad description", "The best way to breathe easy at home. Breeze ships free in 2 days."),
    ("Social ad primary text", "Meet Larkspur Breeze: clean air for rooms up to 350 sq ft, at a whisper-quiet "
                               "25 dB. Grab yours for $179!"),
    ("Social ad primary text", "Breeze captures 99% of particles as small as 0.3 microns, so allergy season "
                               "feels lighter. Try it free for 30 days."),
    ("Social ad primary text", "3 colors, an 8-hour timer and a filter that lasts up to 9 months. Larkspur "
                               "Breeze fits every room."),
    ("Social ad headline", "Breeze: quiet, clean, $179"),
    ("Social ad headline", "Breathe easier with Breeze"),
    ("Social ad headline", "The purifier allergy sufferers love"),
    ("Email subject line", "Free shipping on Larkspur Breeze!"),
    ("Email subject line", "Your quietest nights start here"),
    ("Email subject line", "Breeze is here: 25 dB of calm"),
    ("Email subject line", "Last chance: Breeze at $179"),
    ("Email preheader", "Rooms up to 350 sq ft, 25 dB in sleep mode and free returns for 30 days."),
    ("Email preheader", "The launch price ends Sunday. Free shipping on every order."),
    ("Email preheader", "Allergy relief in 3 colors, from $179."),
    ("SMS", "Larkspur: Breeze is here! Clean air for rooms up to 350 sq ft, just $179. lrk.sp/breeze "
            "Reply STOP to opt out."),
    ("SMS", "Larkspur: Last day for Breeze at $179 \u2014 free shipping ends tonight. lrk.sp/breeze "
            "Reply STOP to opt out."),
    ("Push notification title", "Larkspur Breeze is here"),
    ("Push notification title", "Breathe easy tonight"),
    ("Push notification body", "Clean air for rooms up to 350 sq ft, at 25 dB. Just $179."),
    ("Push notification body", "Filters from $35, delivered every 9 months. Free shipping."),
]


def breeze_launch_md() -> str:
    rows = "\n".join(f"| {placement} | {text} |" for placement, text in BREEZE_LAUNCH)
    return f"""# Last year's launch: Larkspur Breeze (2025)

The copy that ran for the Breeze launch, kept for its tone. It was written
under the 2025 rules, before the claims register and before this launch's
voice rules, and it makes the Breeze's claims, not a Halo's. Nothing in it is
a source for this launch.

| placement | text as it ran |
|---|---|
{rows}
"""


def claims_register_csv() -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["claim_id", "product", "claim", "copy_wording", "status", "channels", "valid_until", "note"])
    for index, row in enumerate(REGISTER, 1):
        writer.writerow([f"CR-{index:03d}", row.product, row.claim, row.wording, row.status, row.channels,
                         f"{row.valid_until:%Y-%m-%d}" if row.valid_until else "", row.note])
    return buffer.getvalue()


def spec_sheet_md() -> str:
    header = "| | " + " | ".join(product.name for product in LAUNCH_PRODUCTS) + " |"
    rows = "\n".join(f"| {name} | " + " | ".join(values) + " |" for name, values in SPEC_SHEET.items())
    return f"""# Halo engineering spec sheet

For reference only. These are engineering measurements, not claims: copy
states none of them unless the claims register approves the same claim.

{header}
|---|{"---|" * len(LAUNCH_PRODUCTS)}
{rows}
"""


def voice_rules_md() -> str:
    banned = ", ".join(f"`{word}`" for word in BANNED_WORDS)
    channels = ", ".join(f"`{channel}`" for channel in CHANNELS)
    return f"""# {BRAND} voice rules

These apply to every asset of the launch.

## Claims come from the register

1. An asset may state a claim about its product only when claims_register.csv
   has a row for that claim that is usable for the asset: its `status` is
   `approved`, its `product` is the asset's product or `all`, its `channels`
   are `all` or include the asset's channel ({channels}; placements.md
   gives each placement's channel), and its `valid_until` is blank or not
   before the launch day, {_day(LAUNCH_DATE)}, {LAUNCH_DATE.year}. A claim's
   `copy_wording` is how copy writes it.
2. Figures: every number an asset writes in digits must be a number in the
   `copy_wording` of a row usable for that asset. No other number in digits:
   no figure from the spec sheet or the brief, no times, counts or dates of
   your own.
3. The phrases in `copy_wording` that carry no figure (`app`, `pet dander`,
   `HEPA` and the rest) are claims too: an asset uses one only when a row
   with that wording is usable for it.
4. Each asset is about its own product: it names no other Halo product
   and no other Larkspur product (the Breeze, the Drift or the Ember).
5. Nothing else about a product: no award, endorsement, ranking, review,
   comparison with another product, or health outcome.

## Prices

6. An asset that states its product's launch price also states the date
   that product's launch offer ends, as the register writes it. An asset may
   state its product's regular price only when it also states the launch
   price. An asset in a placement that allows no price (see placements.md)
   states no amount of money at all.

## Words

7. No exclamation marks.
8. Never use these words, in any case, as a whole word or as part of a
   hyphenated word: {banned}.
9. The word `{FREE_WORD}`, alone or as part of a hyphenated word (`dust-free`),
   appears only in the exact phrase `{FREE_PHRASE}`. Not `free returns`, not
   `free trial`, not `ships free`.

## Repeats

10. No two assets in the pack have the same text. Case, spacing and
    punctuation do not make two texts different.
"""


def placements_md() -> str:
    rows = []
    for placement in PLACEMENTS:
        must = MUST_LABELS.get(placement.must, "-")
        if placement.first_only and placement.must:
            must = f"asset 01 only: {must}"
        if placement.code == SMS_CODE:
            must = "see SMS below"
        must_not = " and ".join(f"the word `{string}`" if string == FREE_WORD else f"`{string}`"
                                for string in placement.must_not) or "-"
        rows.append(f"| `{placement.code}` | {placement.name} | {placement.channel} | {placement.count} | "
                    f"{placement.limit} | {'yes' if placement.price else 'no'} | {must} | {must_not} |")
    per_product = sum(placement.count for placement in PLACEMENTS)
    total = per_product * len(LAUNCH_PRODUCTS)
    sms = PLACEMENT[SMS_CODE]
    allowed = "".join(sorted(SMS_CHARACTERS - set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 ")))
    first = PLACEMENTS[0]
    codes = ", ".join(f"`{product.code}`" for product in LAUNCH_PRODUCTS)
    names = "; ".join(f"{product.code}: `{product.full_name}`, `{product.name}`" for product in LAUNCH_PRODUCTS)
    return f"""# Placements: Halo launch

Every product ({codes}) gets the assets below: {per_product} per product, {total} in all.
An asset's id is the product code, the placement code and its number in two
digits, joined by hyphens: `MINI-{first.code}-01` to `MINI-{first.code}-{first.count:02d}`, `ONE-SD-01`, and so on.

The limit is the most characters an asset may hold, every space and
punctuation mark included. "Must include" and "must not include" mean the
exact characters shown, in any case. A product's full name and its name:
{names}.

| code | placement | channel | assets per product | limit | price allowed | must include | must not include |
|---|---|---|---:|---:|---|---|---|
{chr(10).join(rows)}

## Search ad headlines

No two of a product's {first.count} headlines open with the same two words. Two
headlines open the same way when their first two words are the same,
compared in lower case. Apostrophes are dropped, a number with its decimal
point and its % sign is one word (`99.5%`), `&` is a word, and any other
punctuation is read as a space (`2-Year` is two words).

## SMS

Every SMS opens with `{SMS_OPENING}`, carries its product's SMS link (see the
brief), and ends with exactly `{SMS_ENDING}` All three count toward the limit.

An SMS stays within {sms.limit} characters only when every character in it is a
letter A to Z or a to z, a digit, a space, or one of these: `{allowed}`. Any
other character (a curly apostrophe or quote, an em or en dash, an emoji, an
accented letter) sends the whole message as Unicode, and a Unicode SMS may
hold only {SMS_UNICODE_LIMIT} characters.
"""


def launch_fixtures() -> dict[str, str]:
    return {
        "launch_brief.md": launch_brief_md(),
        "claims_register.csv": claims_register_csv(),
        "spec_sheet.md": spec_sheet_md(),
        "breeze_launch_2025.md": breeze_launch_md(),
        "voice_rules.md": voice_rules_md(),
        "placements.md": placements_md(),
    }


# ── The checker ──────────────────────────────────────────────────────────────

_ASSET_KEY = re.compile(r"([A-Za-z]{3,4})[-_ ]?([A-Za-z]{2})[-_ ]?0*(\d{1,2})")


def _asset_key(raw: str) -> str | None:
    """An asset id as a join key ("one-sh-1" is ONE-SH-01), for a product
    and a placement the table has; any other first cell (a stray line of
    prose) is not an asset row."""
    match = _ASSET_KEY.fullmatch(raw.strip()[:16])
    if not match or match.group(1).upper() not in LAUNCH_PRODUCT or match.group(2).upper() not in PLACEMENT:
        return None
    return f"{match.group(1).upper()}-{match.group(2).upper()}-{int(match.group(3)):02d}"


LAUNCH_FACTS = (
    "workflow_missing_file_count",
    "workflow_asset_coverage_error_count",
    "workflow_duplicate_asset_id_count",
    "workflow_over_limit_count",
    "workflow_sms_format_error_count",
    "workflow_required_string_missing_count",
    "workflow_placement_exclusion_count",
    "workflow_price_rule_error_count",
    "workflow_uncleared_figure_count",
    "workflow_uncleared_claim_count",
    "workflow_other_product_named_count",
    "workflow_banned_word_count",
    "workflow_headline_opening_clash_count",
    "workflow_duplicate_copy_count",
)


def launch_facts(response_text: str) -> dict[str, int]:
    """Counts of what a reply got wrong. An asset that is missing counts
    against every check it would be held to, so leaving copy out never
    earns credit for the rules it would have had to follow."""
    document = csv_file(response_text, LAUNCH_FILE)
    expected = {asset_id: (product, placement) for asset_id, product, placement in launch_assets()}
    texts: dict[str, str] = {}
    repeated = unknown = 0
    seen: set[str] = set()
    for raw, value in keyed_lines(document, "asset_id"):
        key = _asset_key(raw)
        if key is None:
            continue
        if key in seen:
            repeated += 1
            continue
        seen.add(key)
        if key not in expected:
            unknown += 1
            continue
        if value:
            texts[key] = value

    out = dict.fromkeys(LAUNCH_FACTS, 0)
    out["workflow_missing_file_count"] = int(document is None)
    missing = [asset_id for asset_id in expected if asset_id not in texts]
    out["workflow_asset_coverage_error_count"] = len(missing) + unknown
    out["workflow_duplicate_asset_id_count"] = repeated + len(missing)
    for asset_id, (product, placement) in expected.items():
        text = texts.get(asset_id)
        if text is None:
            out["workflow_over_limit_count"] += 1
            out["workflow_sms_format_error_count"] += 3 if placement.code == SMS_CODE else 0
            out["workflow_required_string_missing_count"] += len(required_strings(asset_id, product, placement))
            out["workflow_placement_exclusion_count"] += len(placement.must_not)
            for name in ("workflow_price_rule_error_count", "workflow_uncleared_figure_count",
                         "workflow_uncleared_claim_count", "workflow_other_product_named_count",
                         "workflow_banned_word_count"):
                out[name] += 1
            continue
        out["workflow_over_limit_count"] += len(text) > limit_for(placement, text)
        if placement.code == SMS_CODE:
            out["workflow_sms_format_error_count"] += sms_format_errors(product, text)
        out["workflow_required_string_missing_count"] += missing_strings(
            text, required_strings(asset_id, product, placement))
        out["workflow_placement_exclusion_count"] += exclusions_in(placement, text)
        out["workflow_price_rule_error_count"] += price_rule_errors(product, placement, text)
        out["workflow_uncleared_figure_count"] += uncleared_figures(product, placement.channel, text)
        out["workflow_uncleared_claim_count"] += uncleared_claims(product, placement.channel, text)
        out["workflow_other_product_named_count"] += other_products_named(product, text)
        out["workflow_banned_word_count"] += banned_in(text)

    for product in LAUNCH_PRODUCTS:
        headlines = [asset_id for asset_id, (p, placement) in expected.items()
                     if p is product and placement.code == PLACEMENTS[0].code]
        openings = Counter(opening(texts[asset_id]) for asset_id in headlines if asset_id in texts)
        out["workflow_headline_opening_clash_count"] += (
            sum(count * (count - 1) // 2 for count in openings.values())
            + sum(asset_id not in texts for asset_id in headlines))
    copies = Counter(same_copy(text) for text in texts.values())
    out["workflow_duplicate_copy_count"] = sum(count - 1 for count in copies.values()) + len(missing)
    return out


_TASKS[LAUNCH_ID] = (launch_fixtures, launch_facts, launch_reference_answer)


# ═════════════════════════════════════════════════════════════════════════════
# The workflow interface
# ═════════════════════════════════════════════════════════════════════════════

TASK_IDS = tuple(_TASKS)


def fixtures_for(task_id: str) -> dict[str, str]:
    """One task's files, by file name."""
    return _TASKS[task_id][0]()


def reference_answer(task_id: str) -> str:
    return _TASKS[task_id][2]()


def facts(response_text: str, workflow: str) -> dict[str, int]:
    """The counts one task's checks read, for the task the runner names."""
    return _TASKS[workflow][1](response_text if isinstance(response_text, str) else "")
