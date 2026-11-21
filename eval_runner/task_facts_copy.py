"""The copy tasks: a launch copy pack and a catalog of product descriptions.

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
    catalog-descriptions   a 60-row spec table, a certificate register, a
                           warranty policy, last season's descriptions and a
                           style sheet in; 60 product descriptions out

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
# catalog-descriptions
# ═════════════════════════════════════════════════════════════════════════════

CATALOG_ID = "catalog-descriptions"
CATALOG_DIR = FIXTURE_DIR / CATALOG_ID
CATALOG_FILE = "descriptions.csv"
STORE = "Wrenfold Home"
PUBLISH_DATE = date(2027, 3, 2)
WORD_RANGE = (35, 75)
SPEC_COLUMNS = ["sku", "name", "category", "material", "width_cm", "depth_cm", "height_cm", "weight_kg",
                "colour", "certificate_ids", "warranty_years", "made_in", "features", "price_usd"]


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    family: str
    category: str
    material: str
    width: str
    depth: str
    height: str
    weight: str
    colour: str
    certificate_ids: tuple[str, ...]
    warranty_override: str
    made_in: str
    features: tuple[str, ...]
    price: str

    @property
    def dimensions(self) -> tuple[str, str, str]:
        return self.width, self.depth, self.height

    @property
    def warranty(self) -> str:
        """The warranty the description states: the row's own years, else the
        category's from the policy, else none ("")."""
        return self.warranty_override or WARRANTY_POLICY.get(self.category, "")

    @property
    def certifications(self) -> tuple[str, ...]:
        """The standards the product holds on the publish date, as the
        certificate register names them."""
        out = []
        for cert_id in self.certificate_ids:
            cert = CERTIFICATES[cert_id]
            if cert.counts and cert.standard not in out:
                out.append(cert.standard)
        return tuple(out)


@dataclass(frozen=True)
class Certificate:
    cert_id: str
    standard: str
    holder: str
    status: str
    valid_until: date

    @property
    def counts(self) -> bool:
        return self.status == "valid" and self.valid_until >= PUBLISH_DATE


FSC, GREENGUARD, OEKO_TEX, GOTS = "FSC", "GREENGUARD Gold", "OEKO-TEX Standard 100", "GOTS"
CERTIFICATES: dict[str, Certificate] = {cert.cert_id: cert for cert in [
    Certificate("FSC-C104211", FSC, "Baltwood Joinery", "valid", date(2028, 6, 30)),
    Certificate("FSC-C112233", FSC, "Mekong Timber Works", "valid", date(2027, 9, 30)),
    Certificate("FSC-C087654", FSC, "Douro Moveis", "valid", date(2027, 1, 31)),       # lapsed before the date
    Certificate("FSC-C099001", FSC, "Wisla Furniture", "suspended", date(2027, 12, 31)),
    Certificate("FSC-C120005", FSC, "Nordhavn Wood", "valid", date(2028, 3, 31)),     # no product of ours
    Certificate("GG-5531", GREENGUARD, "Lisboa Estofos", "valid", date(2027, 11, 30)),
    Certificate("GG-4120", GREENGUARD, "Lisboa Estofos", "expired", date(2026, 12, 31)),
    Certificate("OT-21.HIN.77045", OEKO_TEX, "Jaipur Looms", "valid", date(2027, 8, 31)),
    Certificate("OT-19.HIN.12201", OEKO_TEX, "Jaipur Looms", "valid", date(2027, 2, 28)),  # lapses two days before
    Certificate("GOTS-CU-8811", GOTS, "Jaipur Looms", "valid", date(2027, 10, 31)),
    Certificate("GOTS-CU-7702", GOTS, "Saigon Weavers", "withdrawn", date(2027, 6, 30)),
]}
WARRANTY_POLICY: dict[str, str] = {
    "desk": "5", "bookcase": "5", "side table": "2", "floor lamp": "2", "table lamp": "2", "dining chair": "2",
    "armchair": "2", "sofa": "10", "sideboard": "2", "media unit": "2", "wall shelf": "2", "bed frame": "10",
    "headboard": "2",
}
NO_WARRANTY_CATEGORIES = ("cushion", "storage basket", "laundry hamper", "planter")


def _p(sku, name, family, category, material, dims, weight, colour, certs, warranty, made_in, features, price):
    width, depth, height = dims
    return Product(sku, name, family, category, material, width, depth, height, weight, colour,
                   tuple(c for c in certs.split("; ") if c), warranty, made_in, tuple(features.split("; ")), price)


_OAK, _WALNUT, _ASH = "solid white oak", "solid walnut", "solid ash"
_FSC_A, _FSC_B, _FSC_OLD, _FSC_SUSP = "FSC-C104211", "FSC-C112233", "FSC-C087654", "FSC-C099001"
_DESK = "two cable ports; one shallow drawer; oiled finish"
_HALE = "five fixed shelves; wall anchor included"
_HALE_LOW = "three fixed shelves; wall anchor included"
_SHELF = "hidden brackets; screws included"
_CUSHION = "zip closure; washable cover; feather insert"
_COVE = "drainage hole; saucer included; unglazed finish"
PRODUCTS: list[Product] = [
    _p("WF-1101", "Linden Desk 100", "Linden", "desk", _OAK, ("100", "55", "75"), "19", "natural oak", _FSC_A, "",
       "Portugal", "one shallow drawer; oiled finish", "549"),
    _p("WF-1102", "Linden Desk 120", "Linden", "desk", _OAK, ("120", "60", "75"), "24", "natural oak", _FSC_A, "",
       "Portugal", _DESK, "649"),
    _p("WF-1103", "Linden Desk 140", "Linden", "desk", _OAK, ("140", "60", "75"), "", "natural oak", _FSC_A, "",
       "Portugal", _DESK, "729"),
    _p("WF-1104", "Linden Desk 160", "Linden", "desk", _OAK, ("160", "70", "75"), "33", "natural oak", _FSC_OLD, "7",
       "Lithuania", "two cable ports; two shallow drawers; oiled finish", "849"),
    _p("WF-1105", "Linden Desk 140, Walnut", "Linden", "desk", _WALNUT, ("140", "60", "75"), "26", "walnut", _FSC_B,
       "", "Portugal", _DESK, "899"),
    _p("WF-1201", "Hale Bookcase 60", "Hale", "bookcase", _OAK, ("60", "35", "180"), "29", "natural oak", "", "",
       "Lithuania", _HALE, "599"),
    _p("WF-1202", "Hale Bookcase 90", "Hale", "bookcase", _OAK, ("90", "35", "180"), "41", "natural oak", "", "",
       "Lithuania", _HALE, "899"),
    _p("WF-1203", "Hale Bookcase 90, Low", "Hale", "bookcase", _OAK, ("90", "35", "110"), "27", "natural oak", "", "",
       "Lithuania", _HALE_LOW, "649"),
    _p("WF-1204", "Hale Bookcase 90, Ash", "Hale", "bookcase", _ASH, ("90", "35", "180"), "38", "natural ash", _FSC_A,
       "", "Lithuania", _HALE, "849"),
    _p("WF-1205", "Hale Bookcase 60, Low", "Hale", "bookcase", _OAK, ("60", "35", "110"), "", "natural oak", "", "2",
       "", _HALE_LOW, "449"),
    _p("WF-1301", "Tove Side Table, Low", "Tove", "side table", _ASH, ("40", "40", "45"), "5", "natural ash", _FSC_A,
       "", "", "round top; tapered legs", "189"),
    _p("WF-1302", "Tove Side Table, Tall", "Tove", "side table", _ASH, ("40", "40", "55"), "5", "natural ash", _FSC_A,
       "", "", "round top; tapered legs", "209"),
    _p("WF-1303", "Tove Side Table, Square", "Tove", "side table", _ASH, ("40", "40", "45"), "6", "natural ash",
       _FSC_SUSP, "", "Poland", "square top; tapered legs", "199"),
    _p("WF-1304", "Tove Side Table, Walnut", "Tove", "side table", _WALNUT, ("40", "40", "45"), "5", "walnut", _FSC_B,
       "", "", "round top; tapered legs", "249"),
    _p("WF-1305", "Tove Nesting Tables", "Tove", "side table", _ASH, ("50", "40", "50"), "9", "natural ash", _FSC_A,
       "5", "Poland", "two tables that nest; round tops; tapered legs", "329"),
    _p("WF-1401", "Ferro Floor Lamp, Brass", "Ferro", "floor lamp", "brushed brass", ("30", "30", "152"), "6", "brass",
       "", "", "Poland", "linen drum shade; foot switch", "289"),
    _p("WF-1402", "Ferro Floor Lamp, Black", "Ferro", "floor lamp", "powder-coated steel", ("30", "30", "152"), "6",
       "black", "", "", "Poland", "linen drum shade; foot switch", "259"),
    _p("WF-1403", "Ferro Floor Lamp, White", "Ferro", "floor lamp", "powder-coated steel", ("30", "30", "152"), "6",
       "white", "", "", "Poland", "cotton drum shade; foot switch", "259"),
    _p("WF-1404", "Ferro Table Lamp, Brass", "Ferro", "table lamp", "brushed brass", ("25", "25", "48"), "2", "brass",
       "", "", "Poland", "linen drum shade; inline switch", "149"),
    _p("WF-1405", "Ferro Table Lamp, Black", "Ferro", "table lamp", "powder-coated steel", ("25", "25", "48"), "",
       "black", "", "", "", "linen drum shade; inline switch", "129"),
    _p("WF-1501", "Ivo Dining Chair, Walnut", "Ivo", "dining chair", _WALNUT, ("46", "52", "80"), "6", "walnut", _FSC_B,
       "", "Vietnam", "curved backrest; sold singly", "239"),
    _p("WF-1502", "Ivo Dining Chair, Oak", "Ivo", "dining chair", _OAK, ("46", "52", "80"), "6", "natural oak",
       _FSC_OLD, "", "Vietnam", "curved backrest; sold singly", "229"),
    _p("WF-1503", "Ivo Dining Chair, Linen Seat", "Ivo", "dining chair", "solid walnut with linen seat",
       ("46", "52", "80"), "7", "walnut and oat", f"{_FSC_B}; OT-21.HIN.77045", "", "Vietnam",
       "curved backrest; removable seat pad; sold singly", "279"),
    _p("WF-1504", "Ivo Dining Chair, Wool Seat", "Ivo", "dining chair", "solid walnut with wool seat",
       ("46", "52", "80"), "7", "walnut and charcoal", _FSC_B, "", "Vietnam",
       "curved backrest; removable seat pad; sold singly", "289"),
    _p("WF-1505", "Ivo Armchair", "Ivo", "armchair", "solid walnut with linen seat", ("58", "55", "80"), "9",
       "walnut and oat", f"{_FSC_B}; OT-19.HIN.12201", "5", "Vietnam",
       "curved backrest; armrests; removable seat pad", "389"),
    _p("WF-1601", "Marlow Sofa, Two-Seat", "Marlow", "sofa", "beech frame with recycled polyester upholstery",
       ("170", "92", "84"), "46", "slate grey", "GG-5531", "", "Portugal",
       "removable seat covers; two back cushions", "1490"),
    _p("WF-1602", "Marlow Sofa, Three-Seat", "Marlow", "sofa", "beech frame with recycled polyester upholstery",
       ("210", "92", "84"), "58", "slate grey", "GG-5531", "", "Portugal",
       "removable seat covers; three back cushions", "1890"),
    _p("WF-1603", "Marlow Sofa, Three-Seat, Wool", "Marlow", "sofa", "beech frame with wool upholstery",
       ("210", "92", "84"), "60", "moss green", "GG-4120", "", "Portugal",
       "removable seat covers; three back cushions", "2190"),
    _p("WF-1604", "Marlow Corner Sofa", "Marlow", "sofa", "beech frame with recycled polyester upholstery",
       ("260", "190", "84"), "", "slate grey", "GG-5531", "", "",
       "removable seat covers; four back cushions; chaise on the left or the right", "2690"),
    _p("WF-1605", "Marlow Armchair", "Marlow", "armchair", "beech frame with wool upholstery", ("90", "88", "84"),
       "24", "moss green", "GG-5531", "", "Portugal", "removable seat cushion; one back cushion", "849"),
    _p("WF-1701", "Wren Cushion, Organic Cotton", "Wren", "cushion", "organic cotton", ("50", "50", "15"), "1", "oat",
       "GOTS-CU-8811", "", "India", _CUSHION, "49"),
    _p("WF-1702", "Wren Cushion, Linen", "Wren", "cushion", "linen", ("50", "50", "15"), "1", "rust",
       "OT-21.HIN.77045", "", "India", _CUSHION, "59"),
    _p("WF-1703", "Wren Cushion, Wool", "Wren", "cushion", "wool", ("50", "50", "15"), "1", "charcoal",
       "OT-19.HIN.12201", "", "India", "zip closure; feather insert", "69"),
    _p("WF-1704", "Wren Lumbar Cushion, Linen", "Wren", "cushion", "linen", ("60", "40", "12"), "1", "rust",
       "OT-21.HIN.77045", "", "India", _CUSHION, "55"),
    _p("WF-1705", "Wren Cushion, Velvet", "Wren", "cushion", "recycled polyester velvet", ("50", "50", "15"), "1",
       "teal", "", "1", "", "zip closure; feather insert", "65"),
    _p("WF-1801", "Juno Sideboard 160", "Juno", "sideboard", "walnut veneer on MDF", ("160", "45", "75"), "52",
       "walnut", "", "", "Poland", "four push-to-open doors; adjustable shelves", "1150"),
    _p("WF-1802", "Juno Sideboard 200", "Juno", "sideboard", "walnut veneer on MDF", ("200", "45", "75"), "64",
       "walnut", "", "", "Poland", "five push-to-open doors; adjustable shelves", "1390"),
    _p("WF-1803", "Juno Sideboard 160, Oak", "Juno", "sideboard", "oak veneer on MDF", ("160", "45", "75"), "50",
       "natural oak", "", "", "Poland", "four push-to-open doors; adjustable shelves", "1090"),
    _p("WF-1804", "Juno Media Unit 120", "Juno", "media unit", "walnut veneer on MDF", ("120", "40", "50"), "31",
       "walnut", "", "", "Poland", "two push-to-open doors; cable outlet", "690"),
    _p("WF-1805", "Juno Media Unit 180", "Juno", "media unit", "walnut veneer on MDF", ("180", "40", "50"), "43",
       "walnut", "", "5", "Poland", "three push-to-open doors; cable outlet", "890"),
    _p("WF-1901", "Elm Wall Shelf 80", "Shelf", "wall shelf", "solid elm", ("80", "20", "4"), "", "natural elm", "", "",
       "Lithuania", _SHELF, "99"),
    _p("WF-1902", "Elm Wall Shelf 120", "Shelf", "wall shelf", "solid elm", ("120", "20", "4"), "4", "natural elm", "",
       "", "Lithuania", _SHELF, "139"),
    _p("WF-1903", "Birch Wall Shelf 80", "Shelf", "wall shelf", "birch plywood", ("80", "20", "4"), "2",
       "natural birch", _FSC_A, "", "Lithuania", _SHELF, "79"),
    _p("WF-1904", "Birch Wall Shelf 120", "Shelf", "wall shelf", "birch plywood", ("120", "20", "4"), "3",
       "natural birch", _FSC_SUSP, "", "Lithuania", _SHELF, "109"),
    _p("WF-1905", "Ash Wall Shelf 80", "Shelf", "wall shelf", _ASH, ("80", "20", "4"), "2", "natural ash", _FSC_A, "",
       "", _SHELF, "119"),
    _p("WF-2001", "Tern Bed Frame, Double", "Tern", "bed frame", _OAK, ("148", "208", "95"), "52", "natural oak", "",
       "", "Portugal", "slatted base; low headboard", "1290"),
    _p("WF-2002", "Tern Bed Frame, Queen", "Tern", "bed frame", _OAK, ("168", "218", "95"), "", "natural oak", "", "",
       "Portugal", "slatted base; low headboard", "1490"),
    _p("WF-2003", "Tern Bed Frame, King", "Tern", "bed frame", _OAK, ("198", "218", "95"), "71", "natural oak", "", "",
       "Portugal", "slatted base; low headboard; centre support leg", "1790"),
    _p("WF-2004", "Tern Bed Frame, Queen, Walnut", "Tern", "bed frame", _WALNUT, ("168", "218", "95"), "64", "walnut",
       _FSC_B, "", "Portugal", "slatted base; low headboard", "1990"),
    _p("WF-2005", "Tern Headboard, Queen", "Tern", "headboard", _OAK, ("168", "8", "95"), "18", "natural oak", "", "",
       "", "wall-mounted; fixings included", "590"),
    _p("WF-2101", "Brae Basket, Small", "Brae", "storage basket", "woven seagrass", ("30", "30", "30"), "1", "natural",
       "", "", "Vietnam", "two handles; folds flat when empty", "39"),
    _p("WF-2102", "Brae Basket, Medium", "Brae", "storage basket", "woven seagrass", ("40", "40", "45"), "",
       "natural", "", "", "Vietnam", "two handles; open top; folds flat when empty", "59"),
    _p("WF-2103", "Brae Basket, Large", "Brae", "storage basket", "woven seagrass", ("50", "50", "55"), "2", "natural",
       "", "", "Vietnam", "two handles; open top; folds flat when empty", "79"),
    _p("WF-2104", "Brae Basket, Medium, Hyacinth", "Brae", "storage basket", "woven water hyacinth",
       ("40", "40", "45"), "2", "natural", "", "", "Vietnam", "two handles; lid", "69"),
    _p("WF-2105", "Brae Hamper", "Brae", "laundry hamper", "woven water hyacinth with cotton liner",
       ("45", "35", "60"), "2", "natural", "", "2", "Vietnam", "removable cotton liner; lid", "119"),
    _p("WF-2201", "Cove Planter, Small", "Cove", "planter", "terracotta", ("20", "20", "18"), "1", "terracotta", "",
       "", "", _COVE, "25"),
    _p("WF-2202", "Cove Planter, Medium", "Cove", "planter", "terracotta", ("30", "30", "28"), "", "terracotta", "",
       "", "", _COVE, "47"),
    _p("WF-2203", "Cove Planter, Large", "Cove", "planter", "terracotta", ("40", "40", "36"), "6", "terracotta", "", "",
       "Portugal", _COVE, "79"),
    _p("WF-2204", "Cove Planter, Glazed", "Cove", "planter", "glazed stoneware", ("30", "30", "28"), "4", "sage", "",
       "", "Portugal", "drainage hole; glazed inside and out", "69"),
    _p("WF-2205", "Cove Planter, Concrete", "Cove", "planter", "concrete", ("40", "40", "36"), "14", "grey", "", "",
       "", "drainage hole; sealed finish", "89"),
]
PRODUCT_BY_SKU = {product.sku: product for product in PRODUCTS}
COUNTRIES = sorted({product.made_in for product in PRODUCTS if product.made_in})
# What says where a product is made, on a row that does not say: a country,
# the table's or another maker's. "Made in solid ash" says nothing of the kind.
ORIGINS = tuple(COUNTRIES) + ("Italy", "France", "Belgium", "Netherlands", "Canada", "Brazil", "Estonia", "Latvia",
                              "China", "Spain", "Germany", "Denmark", "Sweden", "Norway", "Finland", "Indonesia",
                              "Malaysia", "Thailand", "Mexico", "Turkey", "Romania", "Japan", "USA",
                              "United States", "America", "England", "Britain", "UK", "Europe", "Scandinavia")
# What a description that names a certification says, by the certification.
CERT_MARKERS: dict[str, tuple[str, ...]] = {
    FSC: ("fsc", "forest stewardship"),
    GREENGUARD: ("greenguard",),
    OEKO_TEX: ("oeko tex", "oekotex"),
    GOTS: ("gots", "global organic textile"),
    "Fair Trade": ("fair trade", "fairtrade"),
}
CERT_WORDS = ("certified", "certification", "certifications", "certificate", "certificates")
CATALOG_BANNED = ["luxurious", "luxury", "timeless", "stunning", "perfect", "perfectly", "elevate", "elevates",
                  "must-have", "premium", "eco-friendly", "sustainable", "non-toxic", "handcrafted", "handmade",
                  "best"]
PRICE_WORDS = ("price", "priced", "pricing", "cost", "costs", "sale", "discount", "discounted", "usd")
PRICE_SIGNS = ("$", "€", "£")
WARRANTY_WORDS = ("warranty", "warranties", "warranted", "guarantee", "guaranteed")
WEIGHT_WORDS = ("kg", "kgs", "kilo", "kilos", "kilogram", "kilograms")


def spec_line(product: Product) -> str:
    line = (f"Material: {product.material}. "
            f"Dimensions: W {product.width} x D {product.depth} x H {product.height} cm.")
    return line + (f" Weight: {product.weight} kg." if product.weight else "")


def warranty_phrase(product: Product) -> str:
    return f"{product.warranty}-year warranty"


def made_in_phrase(product: Product) -> str:
    return f"Made in {product.made_in}"


def blank_fields(product: Product) -> list[str]:
    return [name for name, value in (("weight_kg", product.weight), ("warranty", product.warranty),
                                     ("made_in", product.made_in)) if not value]


def given_facts(product: Product) -> list[str]:
    """The phrases a description of this row must carry."""
    out = list(product.certifications)
    if product.warranty:
        out.append(warranty_phrase(product))
    if product.made_in:
        out.append(made_in_phrase(product))
    return out


def own_facts_text(product: Product) -> str:
    return " ".join([product.name, product.category, product.material, product.colour, *product.features,
                     *product.certifications])


# ── The reference descriptions: selling text by hand, per family, from the row ──

def _closing(product: Product) -> str:
    parts = []
    if product.certifications:
        parts.append(f"It is {' and '.join(product.certifications)} certified.")
    if product.made_in and product.warranty:
        parts.append(f"Made in {product.made_in}, it comes with a {warranty_phrase(product)}.")
    elif product.made_in:
        parts.append(f"Made in {product.made_in}.")
    elif product.warranty:
        parts.append(f"It comes with a {warranty_phrase(product)}.")
    return " ".join(parts)


# A sentence per family, written for its products, saying what their shared
# features plainly are or do.
_FAMILY_LINE: dict[str, str] = {
    "Linden": "The oiled finish leaves the grain of the wood on show.",
    "Hale": "A wall anchor holds it to the wall.",
    "Tove": "Its legs taper toward the floor.",
    "Ferro": "The shade sits on top of the stand.",
    "Ivo": "Its backrest curves around the sitter.",
    "Marlow": "Its frame is beech.",
    "Wren": "Its cover closes with a zip.",
    "Juno": "Its doors open with a push.",
    "Shelf": "Its brackets stay out of sight.",
    "Tern": "It is made of solid wood.",
    "Brae": "Its sides are woven.",
    "Cove": "Water drains through the hole in its base.",
}


def catalog_prose(product: Product) -> str:
    article = "an" if product.category[0] in "aeiou" else "a"
    return " ".join(part for part in (
        f"{product.name} is {article} {product.category} in {product.material}, in {product.colour}.",
        f"Features: {', '.join(product.features)}.",
        _FAMILY_LINE[product.family],
        _closing(product),
    ) if part)


def catalog_description(product: Product) -> str:
    return f"{catalog_prose(product)} {spec_line(product)}"


def catalog_reference_answer() -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["sku", "description"])
    for product in PRODUCTS:
        writer.writerow([product.sku, catalog_description(product)])
    return "\n".join([
        f"The {len(PRODUCTS)} descriptions, each from its own row, the certificate register and the warranty policy.",
        "",
        f"### {CATALOG_FILE}",
        "```csv",
        buffer.getvalue().rstrip("\n"),
        "```",
        "",
    ])


# ── Last season's descriptions: some still right, some stale ────────────────

PREVIOUS: dict[str, str] = {
    "WF-1102": "Linden Desk 120 is a desk in solid white oak, in natural oak, with two cable ports, one shallow "
               "drawer and an oiled finish. It is FSC certified. Made in Portugal, it comes with a 5-year warranty. "
               "Material: solid white oak. Dimensions: W 120 x D 60 x H 75 cm. Weight: 24 kg.",
    "WF-1103": "Linden Desk 140 is our roomiest oak desk, with two cable ports and one shallow drawer. FSC certified "
               "and made in Portugal, with a 5-year warranty. Material: solid white oak. Dimensions: W 140 x D 60 x "
               "H 75 cm. Weight: 28 kg.",
    "WF-1104": "Linden Desk 160 is the largest Linden, in solid white oak, with two cable ports and two shallow "
               "drawers. It is FSC certified. Made in Portugal, with a 5-year warranty. Material: solid white oak. "
               "Dimensions: W 160 x D 70 x H 75 cm. Weight: 33 kg.",
    "WF-1203": "Hale Bookcase 90, Low is a low bookcase in solid white oak with three fixed shelves and a wall "
               "anchor. Made in Lithuania, with a 5-year warranty. Material: solid white oak. Dimensions: W 90 x "
               "D 35 x H 120 cm. Weight: 27 kg.",
    "WF-1205": "Hale Bookcase 60, Low is the smallest Hale, in solid white oak. Made in Lithuania, with a 5-year "
               "warranty. Material: solid white oak. Dimensions: W 60 x D 35 x H 110 cm. Weight: 19 kg.",
    "WF-1303": "Tove Side Table, Square is a square side table in FSC certified solid ash on tapered legs. Made in "
               "Poland, with a 2-year warranty. Material: solid ash. Dimensions: W 40 x D 40 x H 45 cm. Weight: 6 kg.",
    "WF-1305": "Tove Nesting Tables are two solid ash tables that nest, FSC certified. Made in Poland, with a "
               "2-year warranty. Material: solid ash. Dimensions: W 50 x D 40 x H 50 cm. Weight: 9 kg.",
    "WF-1403": "Ferro Floor Lamp, White pairs a white powder-coated steel stand with a linen drum shade and a foot "
               "switch. Made in Poland, with a 2-year warranty. Material: powder-coated steel. Dimensions: W 30 x "
               "D 30 x H 152 cm. Weight: 6 kg.",
    "WF-1405": "Ferro Table Lamp, Black is a table lamp in powder-coated steel with a linen drum shade. Made in "
               "Poland, with a 2-year warranty. Material: powder-coated steel. Dimensions: W 25 x D 25 x H 48 cm. "
               "Weight: 2 kg.",
    "WF-1502": "Ivo Dining Chair, Oak is a dining chair in solid white oak with a curved backrest, sold singly. "
               "It is FSC certified. Made in Vietnam, with a 2-year warranty. Material: solid white oak. Dimensions: "
               "W 46 x D 52 x H 80 cm. Weight: 6 kg.",
    "WF-1505": "Ivo Armchair is an armchair in solid walnut with a linen seat that is OEKO-TEX Standard 100 "
               "certified. The walnut is FSC certified. Made in Vietnam, with a 2-year warranty. Material: solid "
               "walnut with linen seat. Dimensions: W 58 x D 55 x H 80 cm. Weight: 9 kg.",
    "WF-1601": "Marlow Sofa, Two-Seat is a sofa with a beech frame and recycled polyester upholstery, in slate grey, "
               "with removable seat covers and two back cushions. It is GREENGUARD Gold certified. Made in Portugal, "
               "it comes with a 10-year warranty. Material: beech frame with recycled polyester upholstery. "
               "Dimensions: W 170 x D 92 x H 84 cm. Weight: 46 kg.",
    "WF-1603": "Marlow Sofa, Three-Seat, Wool is a wool sofa on a beech frame, in moss green. It is GREENGUARD Gold "
               "certified. Made in Portugal, with a 10-year warranty. Material: beech frame with wool upholstery. "
               "Dimensions: W 210 x D 92 x H 84 cm. Weight: 60 kg.",
    "WF-1604": "Marlow Corner Sofa seats the whole family, with a chaise on either side. GREENGUARD Gold certified. "
               "Made in Portugal, with a 10-year warranty. Material: beech frame with recycled polyester upholstery. "
               "Dimensions: W 260 x D 190 x H 84 cm. Weight: 82 kg.",
    "WF-1703": "Wren Cushion, Wool is a wool cushion in charcoal with a washable cover and a feather insert. It is "
               "OEKO-TEX Standard 100 certified. Made in India. Material: wool. Dimensions: W 50 x D 50 x H 15 cm. "
               "Weight: 1 kg.",
    "WF-1705": "Wren Cushion, Velvet is a velvet cushion in teal. Made in India. Material: recycled polyester velvet. "
               "Dimensions: W 50 x D 50 x H 15 cm. Weight: 1 kg.",
    "WF-1802": "Juno Sideboard 200 is a long sideboard in walnut veneer on MDF with four push-to-open doors. Made in "
               "Poland, with a 2-year warranty. Material: walnut veneer on MDF. Dimensions: W 200 x D 45 x H 75 cm. "
               "Weight: 64 kg.",
    "WF-1805": "Juno Media Unit 180 is a media unit in walnut veneer with three push-to-open doors and a cable "
               "outlet. Made in Poland, with a 2-year warranty. Material: walnut veneer on MDF. Dimensions: W 180 x "
               "D 40 x H 50 cm. Weight: 43 kg.",
    "WF-1904": "Birch Wall Shelf 120 is a shelf in FSC certified birch plywood on hidden brackets. Made in "
               "Lithuania, with a 2-year warranty. Material: birch plywood. Dimensions: W 120 x D 20 x H 4 cm. "
               "Weight: 3 kg.",
    "WF-2002": "Tern Bed Frame, Queen is a bed frame in solid white oak with a slatted base and a low headboard. "
               "Made in Portugal, with a 10-year warranty. Material: solid white oak. Dimensions: W 168 x D 218 x "
               "H 95 cm. Weight: 66 kg.",
    "WF-2005": "Tern Headboard, Queen is a wall-mounted headboard in solid white oak. Made in Portugal, with a "
               "10-year warranty. Material: solid white oak. Dimensions: W 168 x D 8 x H 95 cm. Weight: 18 kg.",
    "WF-2104": "Brae Basket, Medium, Hyacinth is a basket of woven water hyacinth with two handles and a lid. Made "
               "in Vietnam, with a 2-year warranty. Material: woven water hyacinth. Dimensions: W 40 x D 40 x "
               "H 45 cm. Weight: 2 kg.",
    "WF-2105": "Brae Hamper is a laundry hamper of woven water hyacinth with a removable cotton liner and a lid. "
               "Made in Vietnam. Material: woven water hyacinth with cotton liner. Dimensions: W 45 x D 35 x H 60 cm. "
               "Weight: 2 kg.",
    "WF-2203": "Cove Planter, Large is a terracotta planter with a drainage hole and a saucer. Made in Italy. "
               "Material: terracotta. Dimensions: W 40 x D 40 x H 36 cm. Weight: 6 kg.",
    "WF-2205": "Cove Planter, Concrete is a concrete planter with a drainage hole and a sealed finish. Made in "
               "Portugal. Material: concrete. Dimensions: W 40 x D 40 x H 36 cm. Weight: 14 kg.",
}


# ── The documents ────────────────────────────────────────────────────────────

def product_specs_csv() -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(SPEC_COLUMNS)
    for p_ in PRODUCTS:
        writer.writerow([p_.sku, p_.name, p_.category, p_.material, p_.width, p_.depth, p_.height, p_.weight,
                         p_.colour, "; ".join(p_.certificate_ids), p_.warranty_override, p_.made_in,
                         "; ".join(p_.features), p_.price])
    return buffer.getvalue()


def certificates_csv() -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["certificate_id", "standard", "holder", "status", "valid_until"])
    for cert in CERTIFICATES.values():
        writer.writerow([cert.cert_id, cert.standard, cert.holder, cert.status, f"{cert.valid_until:%Y-%m-%d}"])
    return buffer.getvalue()


def warranty_policy_md() -> str:
    rows = "\n".join(f"| {category} | {years} years |" for category, years in WARRANTY_POLICY.items())
    rows += "\n" + "\n".join(f"| {category} | none |" for category in NO_WARRANTY_CATEGORIES)
    return f"""# {STORE}: warranty policy

Every product carries the warranty of its category, below, unless its row in
product_specs.csv gives a number in `warranty_years`: that number is the
product's warranty instead, longer or shorter. A product whose category has
none and whose row gives none has no warranty.

| category | warranty |
|---|---|
{rows}
"""


def previous_descriptions_md() -> str:
    entries = "\n\n".join(f"### {sku}\n\n{text}" for sku, text in PREVIOUS.items())
    return f"""# Last season's descriptions

The descriptions published for the autumn catalog, for {len(PREVIOUS)} products. Some
products have changed since: where a description here and product_specs.csv,
certificates.csv or warranty_policy.md disagree, the description is out of
date. Reuse its wording only where it still agrees.

{entries}
"""


SAMPLE = _p("WF-0000", "Sample Table", "Tove", "table", "solid cherry", ("50", "50", "50"), "7", "cherry",
            "", "", "", "round top", "100")


def style_sheet_md() -> str:
    banned = ", ".join(f"`{word}`" for word in CATALOG_BANNED)
    low, high = WORD_RANGE
    no_weight = _p("WF-0000", "Sample Table", "Tove", "table", "solid cherry", ("50", "50", "50"), "", "cherry",
                   "", "", "", "round top", "100")
    return f"""# {STORE}: product description style sheet

Every product in product_specs.csv gets one description, written from its
own row, the certificate register (certificates.csv) and the warranty policy
(warranty_policy.md), and nothing else. The catalog is published on
{_day(PUBLISH_DATE)}, {PUBLISH_DATE.year}.

## Shape

1. {low} to {high} words, the spec line included. A word is anything between two
   spaces.
2. Begin with the product's name, exactly as the `name` column writes it.
3. End with the spec line, and put nothing after it. The spec line is:

   `Material: <material>. Dimensions: W <width_cm> x D <depth_cm> x H <height_cm> cm. Weight: <weight_kg> kg.`

   The material is written exactly as the `material` column writes it, the
   dimensions are the row's own numbers, and the `x` is a lower-case letter x.
   When `weight_kg` is blank, the spec line stops after `cm.`, with no weight
   part. For a made-up row, with and without a weight:

   `{spec_line(SAMPLE)}`

   `{spec_line(no_weight)}`

## Facts

4. Use only the product's own facts: its name, category, material, colour,
   features, certifications, warranty and where it is made. Saying what a
   listed feature plainly is or does is fine. Add no other use, feature,
   finish, care advice or comparison, and never name another product or
   another product's material.
5. Warranty: the product's warranty is its row's `warranty_years` when that
   has a number, and otherwise its category's in warranty_policy.md. State it
   once as `<n>-year warranty`, in digits with a hyphen (`2-year warranty`).
   When the product has none, say nothing about a warranty or a guarantee.
6. Where it is made: when `made_in` has a country, say `Made in <country>`.
   When it is blank, name no country and do not say where it is made.
7. Certifications: `certificate_ids` lists the product's certificates. A
   certificate counts only when certificates.csv gives it the status `valid`
   and a `valid_until` on or after the publish date. Name the `standard` of
   every certificate that counts, exactly as certificates.csv writes it, and
   no other standard. When none counts, do not use the words certified or
   certification at all.
8. Weight: only in the spec line, and only when `weight_kg` has a number.
   When it is blank, say nothing about weight anywhere.
9. A size given outside the spec line is one of the row's own dimensions, in
   cm.
10. No price: no amount of money, and none of the words price, priced,
    pricing, cost, sale or discount.
11. Last season's descriptions (previous_descriptions.md) may be reused only
    where they still agree with the row, the register and the policy.

## Words

12. Never use these words, in any case, whole or as part of a hyphenated
    word: {banned}.
"""


def catalog_fixtures() -> dict[str, str]:
    return {
        "product_specs.csv": product_specs_csv(),
        "certificates.csv": certificates_csv(),
        "warranty_policy.md": warranty_policy_md(),
        "previous_descriptions.md": previous_descriptions_md(),
        "style_sheet.md": style_sheet_md(),
    }


# ── The checker ──────────────────────────────────────────────────────────────

_SKU = re.compile(r"WF[-_ ]?(\d{4})")
_SIZE = re.compile(r"(?<![A-Za-z0-9.])(\d+(?:\.\d+)?)\s?(cm|mm|m)\b", re.IGNORECASE)


def _sku(raw: str) -> str | None:
    match = _SKU.fullmatch(raw.strip().upper()[:12])
    return f"WF-{match.group(1)}" if match else None


def split_spec(text: str) -> tuple[str, str]:
    """(selling text, spec line): the spec line starts at the last
    "Material:"; with none, the whole text is selling text."""
    index = text.lower().rfind("material:")
    return (text, "") if index < 0 else (text[:index], text[index:])


def opens_with_name(product: Product, text: str) -> bool:
    return common.norm(text).startswith(common.norm(product.name))


def spec_line_right(product: Product, text: str) -> bool:
    """The description ends with the row's spec line, character for character
    apart from spacing and case."""
    return common.norm(split_spec(text)[1]) == common.norm(spec_line(product))


def given_missing(product: Product, text: str) -> int:
    return sum(1 for phrase in given_facts(product) if not has_words(text, phrase))


def blank_invented(product: Product, text: str) -> int:
    """One for each blank field the description fills in anyway."""
    words = word_list(text)
    count = 0
    if not product.weight:
        count += any(word in WEIGHT_WORDS or word.startswith("weigh") for word in words)
    if not product.warranty:
        count += any(word in WARRANTY_WORDS for word in words)
    if not product.made_in:
        count += any(has_words(text, origin) for origin in ORIGINS)
    return count


def certs_not_held(product: Product, text: str) -> int:
    count = sum(1 for cert, markers in CERT_MARKERS.items()
                if cert not in product.certifications and any(has_words(text, marker) for marker in markers))
    if not product.certifications:
        count += any(word in CERT_WORDS for word in word_list(text))
    return count


def mentions_price(product: Product, text: str) -> bool:
    words = set(word_list(text))
    return (any(sign in text for sign in PRICE_SIGNS) or any(word in words for word in PRICE_WORDS)
            or Decimal(product.price) in figures(text))


def catalog_banned_in(text: str) -> int:
    words = word_list(text)
    return sum(1 for word in CATALOG_BANNED if common.has_phrase(words, word_list(word)))


def _cm(value: str, unit: str) -> Decimal:
    number = Decimal(value)
    return number * {"cm": 1, "mm": Decimal("0.1"), "m": 100}[unit.lower()]


def foreign_facts(product: Product, text: str) -> int:
    """In the selling text: other products named, other products' materials,
    and sizes that are not this row's own dimensions."""
    selling = split_spec(text)[0]
    own_name, own_facts = word_list(product.name), word_list(own_facts_text(product))
    count = 0
    named_materials: set[str] = set()
    for other in PRODUCTS:
        if other.sku == product.sku:
            continue
        if not common.has_phrase(own_name, word_list(other.name)) and has_words(selling, other.name):
            count += 1
        material = other.material
        if (material not in named_materials and not common.has_phrase(own_facts, word_list(material))
                and has_words(selling, material)):
            named_materials.add(material)
            count += 1
    own_sizes = {Decimal(value) for value in product.dimensions}
    count += sum(1 for value, unit in _SIZE.findall(selling[:_MAX_DOCUMENT]) if _cm(value, unit) not in own_sizes)
    return count


CATALOG_FACTS = (
    "workflow_missing_file_count",
    "workflow_product_coverage_error_count",
    "workflow_name_opening_error_count",
    "workflow_word_range_error_count",
    "workflow_spec_line_error_count",
    "workflow_given_fact_missing_count",
    "workflow_blank_field_invented_count",
    "workflow_cert_not_held_count",
    "workflow_price_mention_count",
    "workflow_banned_word_count",
    "workflow_foreign_fact_count",
)


def catalog_facts(response_text: str) -> dict[str, int]:
    """Counts of what a reply got wrong. A missing description counts against
    every check it would be held to."""
    document = csv_file(response_text, CATALOG_FILE)
    texts: dict[str, str] = {}
    seen: set[str] = set()
    repeated = unknown = 0
    for raw, value in keyed_lines(document, "sku"):
        key = _sku(raw)
        if key is None:
            continue
        if key in seen:
            repeated += 1
            continue
        seen.add(key)
        if key not in PRODUCT_BY_SKU:
            unknown += 1
            continue
        if value:
            texts[key] = value
    out = dict.fromkeys(CATALOG_FACTS, 0)
    out["workflow_missing_file_count"] = int(document is None)
    out["workflow_product_coverage_error_count"] = (
        sum(product.sku not in texts for product in PRODUCTS) + unknown + repeated)
    low, high = WORD_RANGE
    for product in PRODUCTS:
        text = texts.get(product.sku)
        if text is None:
            for name in ("workflow_name_opening_error_count", "workflow_word_range_error_count",
                         "workflow_spec_line_error_count", "workflow_cert_not_held_count",
                         "workflow_price_mention_count", "workflow_banned_word_count",
                         "workflow_foreign_fact_count"):
                out[name] += 1
            out["workflow_given_fact_missing_count"] += len(given_facts(product))
            out["workflow_blank_field_invented_count"] += len(blank_fields(product))
            continue
        out["workflow_name_opening_error_count"] += not opens_with_name(product, text)
        out["workflow_word_range_error_count"] += not low <= len(text.split()) <= high
        out["workflow_spec_line_error_count"] += not spec_line_right(product, text)
        out["workflow_given_fact_missing_count"] += given_missing(product, text)
        out["workflow_blank_field_invented_count"] += blank_invented(product, text)
        out["workflow_cert_not_held_count"] += certs_not_held(product, text)
        out["workflow_price_mention_count"] += mentions_price(product, text)
        out["workflow_banned_word_count"] += catalog_banned_in(text)
        out["workflow_foreign_fact_count"] += foreign_facts(product, text)
    return out


_TASKS[CATALOG_ID] = (catalog_fixtures, catalog_facts, catalog_reference_answer)


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
