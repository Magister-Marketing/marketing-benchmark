"""The copy tasks: launch-copy-pack, catalog-descriptions and claims-check.

For each task:

- the committed files are what the module generates, byte for byte, and fit
  one model call;
- every value the task file states (a count, a list of figures, a corrected
  figure) is recomputed here from the committed files by code that does not
  use the module's constants, and matches;
- a reference reply written by hand passes every program check, and a blank
  reply earns nothing;
- the careless reading each task is built to catch scores zero on the checks
  it touches, and leaves the others as they were;
- the edges of each rule are pinned.
"""
import csv
import io
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import gen_workflow_tasks  # noqa: E402
from eval_runner import bench, workflows  # noqa: E402
from eval_runner import task_facts_copy as m  # noqa: E402

FIXTURES = REPO_ROOT / "eval_runner" / "fixtures"


def task_file(task_id: str) -> dict:
    return json.loads((REPO_ROOT / "eval_runner" / "tasks" / f"{task_id}.json").read_text())


def by_id(task: dict) -> dict[str, dict]:
    return {c["id"]: c for section in bench.RUBRIC_SECTIONS for c in task["rubric"][section]}


def results(task: dict, text: str) -> dict:
    return bench.programmatic_results(task, bench.measured_facts(task, text))


def scores(task: dict, text: str) -> dict[str, float]:
    return {name: item["score"] for name, item in results(task, text).items()}


def swap(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, f"{old!r} appears {text.count(old)} times"
    return text.replace(old, new)


def md_table(text: str, first_header: str) -> list[dict[str, str]]:
    """The Markdown table whose first header cell is first_header, as rows."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if line.startswith("|") and cells[0] == first_header:
            rows = []
            for row in lines[index + 2:]:
                if not row.startswith("|"):
                    break
                rows.append(dict(zip(cells, (cell.strip() for cell in row.strip().strip("|").split("|")))))
            return rows
    raise AssertionError(f"no table headed {first_header!r}")


def numbers_in(text: str) -> list[Decimal]:
    return [Decimal(n.replace(",", "")) for n in re.findall(r"(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?", text)]


def the_files_are_generated(task_id: str) -> None:
    task = task_file(task_id)
    generated = m.fixtures_for(task_id)
    assert sorted(Path(path).name for path in task["fixtures"]) == sorted(generated)
    for path in task["fixtures"]:
        assert (REPO_ROOT / path).read_text() == generated[Path(path).name], path
    assert gen_workflow_tasks.drift() == []
    assert task["workflow"] == task_id
    interface = workflows.module_for(task_id)
    assert interface.TASK_ID == task_id and interface.fixtures() == generated
    assert interface.reference_answer() == m.reference_answer(task_id)
    assert interface.facts("") == m.facts("", task_id)
    assert sum(len((REPO_ROOT / path).read_bytes()) for path in task["fixtures"]) < 60_000


def the_reference_passes_and_a_blank_reply_earns_nothing(task_id: str) -> None:
    task = task_file(task_id)
    reference = m.reference_answer(task_id)
    passed = results(task, reference)
    assert passed and all(item["pass"] and item["score"] == 1.0 for item in passed.values()), {
        name: item["evidence"] for name, item in passed.items() if not item["pass"]}
    assert all(value == 0 for value in m.facts(reference, task_id).values())
    assert not any(item["pass"] for item in results(task, "").values())
    assert bench.free_credit_scores(task) == {}
    criteria = by_id(task)
    judged = [c for c in criteria.values() if "programmatic" not in c]
    assert 10 <= len(criteria) <= 18
    assert len(judged) == 1 and (len(criteria) - len(judged)) / len(criteria) >= 0.7
    named = {c["programmatic"]["fact"] for c in criteria.values() if "programmatic" in c}
    assert named == set(m.facts("", task_id))
    # Rubric 2: a file that groups its rows with blank lines is read whole (a run read it as 18 rows of 72).
    assert task["split"] == "development" and (task["prompt_version"], task["rubric_version"]) == (1, 2)
    assert task["prompt"].endswith("This is copy for review. Publish nothing and fetch nothing external.")
    for skill in task["skills"]:
        assert (REPO_ROOT / skill).is_file()


def zero_at_least(task: dict, text: str, touched: set[str]) -> dict[str, float]:
    """The careless reply scores zero on every check it touches (other checks
    may lose some credit too)."""
    got = scores(task, text)
    assert all(got[name] == 0.0 for name in touched), {name: got[name] for name in touched}
    return got


def zero_on(task: dict, text: str, touched: set[str]) -> None:
    """The careless reply scores zero on every check it touches and keeps
    full credit on every other program check."""
    got = scores(task, text)
    assert {name for name, score in got.items() if score == 0.0} == touched, got
    assert all(score == 1.0 for name, score in got.items() if name not in touched), got




# ═════════════════════════════════════════════════════════════════════════════
# launch-copy-pack
# ═════════════════════════════════════════════════════════════════════════════

LAUNCH = task_file("launch-copy-pack")
LAUNCH_REF = m.launch_reference_answer()
LAUNCH_CLEAN = m.launch_facts(LAUNCH_REF)
CHANNELS = ("search", "social", "email", "sms", "push")


def launch_doc(name: str) -> str:
    return (FIXTURES / "launch-copy-pack" / name).read_text()


def launch_row(asset_id: str) -> str:
    return next(line for line in LAUNCH_REF.splitlines() if line.startswith(asset_id + ","))


def with_asset(asset_id: str, text: str, base: str = LAUNCH_REF) -> str:
    out = io.StringIO()
    csv.writer(out, lineterminator="").writerow([asset_id, text])
    return swap(base, launch_row(asset_id), out.getvalue())


def with_assets(changes: dict[str, str], base: str = LAUNCH_REF) -> str:
    for asset_id, text in changes.items():
        base = with_asset(asset_id, text, base)
    return base


def launch_changed(text: str) -> dict:
    facts = m.launch_facts(text)
    return {name: facts[name] - LAUNCH_CLEAN[name] for name in facts if facts[name] != LAUNCH_CLEAN[name]}


def register_rows() -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(launch_doc("claims_register.csv"))))


def usable_from_file(product: str, channel: str) -> list[dict[str, str]]:
    """Register rows usable for a product's copy in a channel, read from the
    file by the voice rules' own words."""
    launch_day = "2027-02-24"
    assert "Feb 24, 2027" in launch_doc("voice_rules.md")
    return [row for row in register_rows()
            if row["status"] == "approved" and row["product"] in (product, "all")
            and (row["channels"] == "all" or channel in [c.strip() for c in row["channels"].split(";")])
            and (not row["valid_until"] or row["valid_until"] >= launch_day)]


def test_launch_files_are_generated_and_fit_one_call():
    the_files_are_generated("launch-copy-pack")
    assert 20_000 < sum(len(text) for text in m.launch_fixtures().values())
    assert len(LAUNCH_REF) < 8_000


def test_launch_reference_passes_and_a_blank_reply_earns_nothing():
    the_reference_passes_and_a_blank_reply_earns_nothing("launch-copy-pack")


def test_launch_values_in_the_task_file_come_from_the_files():
    placements = md_table(launch_doc("placements.md"), "code")
    codes = re.findall(r"`([A-Z]+)`", launch_doc("placements.md").split("Every product (")[1].split(")")[0])
    per_product = sum(int(row["assets per product"]) for row in placements)
    required = 0
    for row in placements:
        if row["must include"] in ("-", "see SMS below"):
            continue
        required += 1 if row["must include"].startswith("asset 01 only") else int(row["assets per product"])
    required *= len(codes)
    sms = next(row for row in placements if row["placement"] == "SMS")
    exclusions = sum(int(row["assets per product"]) for row in placements if row["must not include"] != "-")
    no_price = [row["placement"].lower() for row in placements if row["price allowed"] == "no"]
    unicode_limit = int(re.search(r"may\s+hold only (\d+) characters", launch_doc("placements.md")).group(1))
    criteria = by_id(LAUNCH)
    assert (codes, per_product) == (["MINI", "ONE", "MAX", "PET"], 18)
    assert f"Every one of the {per_product * len(codes)} assets" in criteria["every_asset_present"]["check"]
    assert required == 36 and f"{required} strings in all" in criteria["required_strings_present"]["check"]
    assert f"Each of the {int(sms['assets per product']) * len(codes)} SMS" in criteria["sms_format"]["check"]
    assert f"none of the {3 * len(codes)} parts" in criteria["sms_format"]["check"]
    assert f"{exclusions * len(codes)} assets in all" in criteria["placement_exclusions"]["check"]
    assert f"held to {unicode_limit}" in criteria["within_limits"]["check"]
    assert len(no_price) == 4 and all(name in criteria["price_rules"]["check"] for name in no_price)
    # The module applies the file's rules: its placements, its register and its links.
    assert [(p.code, p.channel, p.count, p.limit, p.price) for p in m.PLACEMENTS] == [
        (row["code"].strip("`"), row["channel"], int(row["assets per product"]), int(row["limit"]),
         row["price allowed"] == "yes") for row in placements]
    assert [(r.product, r.wording, r.status, r.channels, f"{r.valid_until:%Y-%m-%d}" if r.valid_until else "")
            for r in m.REGISTER] == [(row["product"], row["copy_wording"], row["status"], row["channels"],
                                      row["valid_until"]) for row in register_rows()]
    for product in m.LAUNCH_PRODUCTS:
        assert f"Its SMS link is `{product.link}`" in launch_doc("launch_brief.md")
        for channel in CHANNELS:
            assert m.usable_figures(product, channel) == {
                value for row in usable_from_file(product.name, channel) for value in numbers_in(row["copy_wording"])}


def test_launch_the_register_holds_the_planted_look_alikes():
    rows = register_rows()
    statuses = {row["status"] for row in rows}
    assert statuses == {"approved", "pending", "withdrawn", "internal"} and len(rows) >= 120
    expired = [row for row in rows if row["status"] == "approved" and row["valid_until"] and row["valid_until"] < "2027-02-24"]
    assert sorted(row["claim"] for row in expired) == ["Early-bird price"] * 4 + ["Filter subscription launch discount"]
    narrow = [row for row in rows if row["status"] == "approved" and row["channels"] != "all"
              and row["product"].startswith(("Halo", "all"))]
    assert len(narrow) >= 10
    # A figure approved for one product is pending or withdrawn for another.
    assert {r["copy_wording"] for r in rows if r["product"] == "Halo Pet" and r["status"] == "approved"} >= {"24 dB"}
    assert any(r["copy_wording"] == "24 dB" and r["product"] == "Halo Max" and r["status"] == "pending" for r in rows)
    # The spec sheet sits a little off the approved figures.
    spec = launch_doc("spec_sheet.md")
    assert "| Recommended room, engineering estimate (sq ft) | 220 | 520 | 1,200 | 520 |" in spec


def test_launch_reference_obeys_the_files_read_by_separate_code():
    placements = {row["code"].strip("`"): row for row in md_table(launch_doc("placements.md"), "code")}
    names = {"MINI": "Halo Mini", "ONE": "Halo One", "MAX": "Halo Max", "PET": "Halo Pet"}
    links = {code: re.search(rf"code {code}\)\n\n.*?Its SMS link is `([^`]+)`", launch_doc("launch_brief.md"),
                             re.DOTALL).group(1) for code in names}
    phrases = {row["copy_wording"] for row in register_rows() if not re.search(r"\d", row["copy_wording"])}
    plain_sms = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,:;!?'\"-()/&%+=@#*$")
    rows = list(csv.reader(io.StringIO(LAUNCH_REF.split("```csv\n")[1].split("\n```")[0])))[1:]
    assert len(rows) == 72 and len({asset_id for asset_id, _ in rows}) == 72
    for asset_id, text in rows:
        code, placement_code, _n = asset_id.split("-")
        row = placements[placement_code]
        usable = usable_from_file(names[code], row["channel"])
        assert len(text) <= int(row["limit"]), asset_id
        assert set(numbers_in(text)) <= {v for r in usable for v in numbers_in(r["copy_wording"])}, asset_id
        lowered = " " + re.sub(r"[^a-z0-9]+", " ", text.lower()) + " "
        for phrase in phrases:
            if " " + re.sub(r"[^a-z0-9]+", " ", phrase.lower()).strip() + " " in lowered:
                assert phrase in {r["copy_wording"] for r in usable}, (asset_id, phrase)
        assert not any(other in text for other in names.values() if other != names[code]), asset_id
        assert not any(other in text for other in ("Breeze", "Drift", "Ember"))
        if row["price allowed"] == "no":
            assert "$" not in text, asset_id
        if placement_code == "SM":
            assert set(text) <= plain_sms and text.startswith("Larkspur:") and links[code] in text
            assert text.endswith("Reply STOP to opt out.")


# ── The careless readings, each scoring zero on its own check ────────────────

def test_launch_sms_written_to_160_before_the_opt_out_line():
    changes = {}
    for product in m.LAUNCH_PRODUCTS:
        asset_id = f"{product.code}-SM-01"
        body = m.LAUNCH_COPY[asset_id][: -len(" " + m.SMS_ENDING)]
        changes[asset_id] = (body + " Clean air, quiet nights, auto mode and sleep mode.")[:160] + " " + m.SMS_ENDING
    zero_on(LAUNCH, with_assets(changes), {"within_limits"})


def test_launch_sms_with_typographic_punctuation_is_unicode():
    changes = {f"{p.code}-SM-01": m.LAUNCH_COPY[f"{p.code}-SM-01"].replace(". ", " — ", 1) for p in m.LAUNCH_PRODUCTS}
    assert all(70 < len(text) <= 160 for text in changes.values())
    zero_on(LAUNCH, with_assets(changes), {"within_limits"})


def test_launch_figures_from_the_spec_sheet_or_another_product():
    zero_on(LAUNCH, with_assets({
        "ONE-SD-02": "Larkspur Halo One moves 260 CFM of air, with Wi-Fi and a washable pre-filter.",
        "MINI-FH-02": "Halo Mini cleans up to 220 sq ft",          # the engineering estimate, not the 200 approved
        "PET-SH-05": "Only 22 dB in Sleep Mode",                     # Halo One's figure
    }), {"only_usable_figures"})


def test_launch_figures_approved_for_other_channels_or_expired():
    zero_on(LAUNCH, with_assets({
        "MINI-FP-02": "Larkspur Halo Mini makes 5 air changes an hour in rooms up to 200 sq ft.",   # search and email
        "ONE-SH-05": "Available From Feb 24",                         # email and push only
        "ONE-EP-02": "Early birds pay $179, and the launch price runs until Mar 14.",               # expired Feb 20
    }), {"only_usable_figures"})
    # The 30-night trial is approved everywhere but SMS.
    trial = {f"{p.code}-SM-01": m.LAUNCH_COPY[f"{p.code}-SM-01"].replace(" is here.", " is here. 30-night trial.")
             for p in m.LAUNCH_PRODUCTS}
    zero_on(LAUNCH, with_assets(trial), {"only_usable_figures"})


def test_launch_claims_the_register_does_not_approve_for_the_asset():
    zero_on(LAUNCH, with_assets({
        "MAX-SH-04": "Helps Clear Wildfire Smoke",     # smoke: email only
        "PET-SH-04": "Catches Pet Hair Daily",          # pet hair: social and email only
        "MINI-FH-01": "Halo Mini, run from the app",   # the app is pending for the Mini
    }), {"only_usable_claims"})
    zero_on(LAUNCH, with_assets({
        "ONE-FH-02": "Halo One meets the HEPA standard",
        "PET-ES-02": "Relief from pet allergies",
        "MAX-PB-01": "Big rooms, cleaner air, Energy Star. $329 until Mar 21.",
    }), {"only_usable_claims"})


def test_launch_one_products_copy_borrowed_for_another():
    zero_on(LAUNCH, with_assets({
        "MINI-ES-02": "Like Halo One, sized for a desk",
        "PET-PT-01": "Halo Pet joins your Breeze",
        "MAX-FH-02": "Halo Max: Halo One, for big rooms",
    }), {"own_product_only"})


def test_launch_headlines_that_all_lead_with_the_product_name():
    changes = {}
    for product in m.LAUNCH_PRODUCTS:
        changes[f"{product.code}-SH-02"] = f"{product.full_name} Auto Mode"[:30]
        changes[f"{product.code}-SH-03"] = f"{product.full_name}: Quiet"[:30]
    zero_on(LAUNCH, with_assets(changes), {"headline_openings_distinct"})


def test_launch_prices_where_the_placement_allows_none_or_without_their_date():
    zero_on(LAUNCH, with_assets({
        "ONE-SH-04": "Now $199 Until Mar 14",
        "MAX-ES-02": "Halo Max is $329 for now",
        "MINI-PB-01": "Cleaner air for small rooms, now $99.",       # its date is missing
    }), {"price_rules"})
    # Another product's offer date is not this product's, and the regular price needs the launch price.
    zero_at_least(LAUNCH, with_assets({
        "MINI-SD-01": "Larkspur Halo Mini cleans rooms up to 200 sq ft. $99 until Mar 14, then $129.",
        "MAX-PB-01": "Big rooms, cleaner air: up to 1,100 sq ft. $329 until Mar 14.",
        "PET-EP-01": "Larkspur Halo Pet is $279. Available Feb 24.",
    }), {"price_rules"})


def test_launch_free_where_only_free_shipping_may_say_it():
    zero_on(LAUNCH, with_assets({
        "ONE-SD-02": "Larkspur Halo One has Wi-Fi and free filter reminders in the app.",
        "MAX-SD-02": "Larkspur Halo Max has a carbon filter, free returns and a 2-year warranty.",
        "PET-FP-02": "Larkspur Halo Pet captures 99.5% of particles as small as 0.3 microns, for dust-free rooms.",
    }), {"no_banned_words"})
    zero_on(LAUNCH, with_assets({f"{p.code}-ES-02": f"Free shipping on {p.name}" for p in m.LAUNCH_PRODUCTS}),
            {"placement_exclusions"})


# ── The edges of the rules ───────────────────────────────────────────────────

@pytest.mark.parametrize("text, values", [
    ("$1,199.00 today", [Decimal("1199.00")]),
    ("99.5% of particles", [Decimal("99.5")]),
    ("a 30-night trial and a 2-year warranty", [Decimal("30"), Decimal("2")]),
    ("3x more", [Decimal("3")]),
    ("code MIRA15", []),                     # a digit inside a word is not a figure
    ("480, quiet", [Decimal("480")]),
    ("1,100 sq ft", [Decimal("1100")]),
    ("24/7", [Decimal("24"), Decimal("7")]),
])
def test_figures_are_read_as_values(text, values):
    assert m.figures(text) == values


@pytest.mark.parametrize("text, limit", [
    ("Larkspur: plain text only. Reply STOP to opt out.", 160),
    ("Larkspur: Halo’s here. Reply STOP to opt out.", 70),
    ("Larkspur: quiet — clean. Reply STOP to opt out.", 70),
    ("Larkspur: café air. Reply STOP to opt out.", 70),
    ("Larkspur: Halo's here & it's $199. Reply STOP to opt out.", 160),
])
def test_an_sms_is_unicode_when_one_character_is_not_plain(text, limit):
    assert m.sms_limit(text) == limit


@pytest.mark.parametrize("text, count", [
    ("The best purifier", 1), ("Our bestseller", 0), ("Best-in-class air", 1), ("Medical grade filtration", 1),
    ("Free shipping on every order", 0), ("Free-shipping on every order", 0), ("Free returns", 1),
    ("Dust-free rooms", 1), ("Ships free", 1), ("Quiet air!", 1), ("Freely breathing", 0),
])
def test_the_edges_of_the_word_rules(text, count):
    assert m.banned_in(text) == count


@pytest.mark.parametrize("code, placement, text, errors", [
    ("ONE", "SH", "Halo One, now $199", 2),          # a price where none is allowed, and no end date
    ("ONE", "SH", "The launch price ends Mar 14", 0),
    ("ONE", "SD", "$199 until Mar 14, then $249", 0),
    ("ONE", "SD", "$199 until mar 14th", 0),          # the date's characters, any case
    ("ONE", "SD", "$199 until Mar. 14", 0),           # Mar 14, Mar. 14 and March 14 are one date
    ("ONE", "SD", "$199 until March 14", 0),
    ("ONE", "SD", "$199 until Mar 4", 1),             # another date
    ("PET", "SD", "$229 until Mar 1", 1),             # not Mar 14 cut short
    ("ONE", "SD", "Regular price $249", 1),
    ("MINI", "SD", "$99 until Mar 14", 1),            # Halo One's date
    ("PET", "SD", "$199 for early birds", 0),          # not this product's launch or regular price
    ("ONE", "PT", "Only 199 dollars", 2),
    ("MAX", "PT", "19 dB of quiet", 0),                # a figure that is another price is no price here
])
def test_the_edges_of_the_price_rules(code, placement, text, errors):
    assert m.price_rule_errors(m.LAUNCH_PRODUCT[code], m.PLACEMENT[placement], text) == errors


@pytest.mark.parametrize("first, second, clash", [
    ("Larkspur Halo Mini Purifier", "Larkspur Halo: Quiet Air", True),
    ("Larkspur's Halo", "Larkspurs Halo deal", True),
    ("2-Year Warranty", "2 Year Warranty Included", True),
    ("99.5% of Particles", "99.5% Capture, Lab Tested", False),   # a decimal and its % are one word
    ("Quiet & Clean in Sleep Mode", "Quiet, Clean Air at 22 dB", False),  # & is a word
    ("Quiet 22 dB Sleep", "Quiet Air at Night", False),
])
def test_the_edges_of_headline_openings(first, second, clash):
    assert (m.opening(first) == m.opening(second)) is clash


@pytest.mark.parametrize("code, channel, text, figures_wrong, claims_wrong", [
    ("MINI", "search", "5 air changes an hour", 0, 0),
    ("MINI", "social", "5 air changes an hour", 1, 0),
    ("ONE", "email", "From $179 for early birds", 1, 0),      # approved, expired before the launch day
    ("ONE", "push", "Available Feb 24", 0, 0),
    ("ONE", "search", "Available Feb 24", 1, 0),
    ("MAX", "email", "Helps clear smoke", 0, 0),
    ("MAX", "social", "Helps clear smoke", 0, 1),
    ("ONE", "social", "Set it from the app", 0, 0),
    ("MINI", "social", "Set it from the app", 0, 1),
    ("MINI", "social", "An apple-green night light", 0, 0),   # a whole word only
    ("PET", "search", "Wi-Fi and the app", 0, 0),
    ("MINI", "search", "Wi-Fi ready", 0, 1),
    ("PET", "social", "Catches pet hair", 0, 0),
    ("PET", "push", "Catches pet hair", 0, 1),
    ("MAX", "email", "Carbon filter for odor", 0, 1),          # odor is the Pet's claim
    ("MAX", "email", "Carbon filter for odors", 0, 1),         # a plural is the same claim
    ("MINI", "search", "No app needed.", 0, 0),                 # a negation claims nothing
    ("MINI", "social", "Halo Mini: no Wi-Fi, no setup", 0, 0),
    ("MINI", "social", "Works without the app", 0, 0),           # an article between
    ("MINI", "social", "Works with the app", 0, 1),
    ("MINI", "social", "Works without Wi-Fi", 0, 0),
])
def test_the_edges_of_the_register(code, channel, text, figures_wrong, claims_wrong):
    product = m.LAUNCH_PRODUCT[code]
    assert m.uncleared_figures(product, channel, text) == figures_wrong
    assert m.uncleared_claims(product, channel, text) == claims_wrong


@pytest.mark.parametrize("code, text, named", [
    ("MINI", "Drift off to cleaner air", 0),          # everyday words, not the products
    ("ONE", "Halo One: setup is a breeze", 0),
    ("PET", "Pairs with your Breeze", 1),
    ("MAX", "Works with the Larkspur Ember", 1),
    ("ONE", "Halo One or Halo Max", 1),
    ("ONE", "Halo One, the One for you", 0),
])
def test_the_edges_of_naming_another_product(code, text, named):
    assert m.other_products_named(m.LAUNCH_PRODUCT[code], text) == named


def test_launch_the_offer_date_reads_the_same_in_both_rules():
    preheader = m.PLACEMENT["EP"]
    one = m.LAUNCH_PRODUCT["ONE"]
    for text, missing in (("The launch price ends March 14.", 0), ("The launch price ends Mar. 14.", 0),
                          ("The launch price ends Mar 4.", 1)):
        assert m.missing_required("ONE-EP-02", one, preheader, text) == missing
        assert m.price_rule_errors(one, preheader, "$199. " + text) == missing


def test_launch_a_file_grouped_by_product_is_read_whole():
    """A run's reply wrote copy_pack.csv without a fence and with a blank line
    between products, every id as the placements file builds it. It was read
    as the first 18 rows of 72; it is now read as the reference is."""
    body = LAUNCH_REF.split("```csv\n")[1].split("\n```")[0].splitlines()
    groups = "\n".join(body[:1] + [line + ("\n" if line.startswith(f"{p.code}-PB-01") and p.code != "PET" else "")
                                   for line in body[1:] for p in m.LAUNCH_PRODUCTS if line.startswith(p.code + "-")])
    assert groups.count("\n\n") == 3
    assert launch_changed(f"### copy_pack.csv\n{groups}\n") == {}
    # The same rows as four fenced blocks, one per product, each with its header.
    blocks = "\n\n".join("```csv\nasset_id,text\n" + "\n".join(line for line in body[1:] if line.startswith(p.code + "-"))
                         + "\n```" for p in m.LAUNCH_PRODUCTS)
    assert launch_changed(f"### copy_pack.csv\n{blocks}\n") == {}
    # Prose after a blank line still ends the file, and rows after it are not read.
    prose = f"### copy_pack.csv\n{body[0]}\n" + "\n".join(body[1:19]) + "\n\nNext, the Halo One:\n" + "\n".join(body[19:])
    assert m.launch_facts(prose)["workflow_asset_coverage_error_count"] == 54


def test_launch_rows_are_read_however_the_csv_is_written():
    quoted = launch_row("MINI-SD-02")
    assert quoted.startswith('MINI-SD-02,"')
    assert launch_changed(swap(LAUNCH_REF, quoted, "MINI-SD-02," + m.LAUNCH_COPY["MINI-SD-02"])) == {}
    assert launch_changed(swap(LAUNCH_REF, "ONE-SH-01,Larkspur", "one-sh-1,Larkspur")) == {}
    lines = LAUNCH_REF.split("```csv\n")[1].split("\n```")[0].splitlines()
    table = "\n".join(["| asset_id | text |", "|---|---|"] + [
        "| " + " | ".join(next(csv.reader([line]))) + " |" for line in lines[1:]])
    assert launch_changed(f"### copy_pack.csv\n\n{table}\n") == {}
    prose = swap(LAUNCH_REF, launch_row("PET-PB-01"), launch_row("PET-PB-01") + "\nIn 12, words")
    assert launch_changed(prose) == {}


def test_launch_each_kind_of_wrong_answer_fails_its_own_check():
    assert launch_changed(with_asset("ONE-SH-03", "Quiet 22 dB Sleep Mode at Night")) == {"workflow_over_limit_count": 1}
    assert launch_changed(with_asset("MAX-SM-01", m.LAUNCH_COPY["MAX-SM-01"].replace("lrk.sp/max", "lrk.sp/one"))) == {
        "workflow_sms_format_error_count": 1}
    assert launch_changed(with_asset("PET-FH-02", "A carbon filter for odor")) == {
        "workflow_required_string_missing_count": 1}
    assert launch_changed(with_asset("ONE-PT-01", "Larkspur Halo One is here")) == {
        "workflow_placement_exclusion_count": 1}
    # Halo One's push body as Halo Pet's: the same copy, and $199 is only Pet's expired early-bird price.
    assert launch_changed(with_asset("PET-PB-01", m.LAUNCH_COPY["ONE-PB-01"])) == {
        "workflow_duplicate_copy_count": 1, "workflow_uncleared_figure_count": 1}
    assert launch_changed(with_asset("MAX-PB-01", m.LAUNCH_COPY["MAX-SD-01"].upper().replace(". ", ";  ")[:100])) == {
        "workflow_duplicate_copy_count": 1}
    missing = swap(LAUNCH_REF, launch_row("PET-PB-01") + "\n", "")
    assert launch_changed(missing) == {
        "workflow_asset_coverage_error_count": 1, "workflow_duplicate_asset_id_count": 1,
        "workflow_over_limit_count": 1, "workflow_banned_word_count": 1, "workflow_price_rule_error_count": 1,
        "workflow_uncleared_figure_count": 1, "workflow_uncleared_claim_count": 1,
        "workflow_other_product_named_count": 1, "workflow_duplicate_copy_count": 1}
    repeated = swap(LAUNCH_REF, launch_row("PET-PB-01"), launch_row("PET-PB-01") + "\n" + launch_row("PET-PB-01"))
    assert launch_changed(repeated) == {"workflow_duplicate_asset_id_count": 1}
    extra = swap(LAUNCH_REF, launch_row("PET-PB-01"), launch_row("PET-PB-01") + "\nPET-PB-02,Another push body")
    assert launch_changed(extra) == {"workflow_asset_coverage_error_count": 1}


# ═════════════════════════════════════════════════════════════════════════════
# catalog-descriptions
# ═════════════════════════════════════════════════════════════════════════════

CATALOG = task_file("catalog-descriptions")
CATALOG_REF = m.catalog_reference_answer()
CATALOG_CLEAN = m.catalog_facts(CATALOG_REF)


def catalog_doc(name: str) -> str:
    return (FIXTURES / "catalog-descriptions" / name).read_text()


def spec_rows() -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(catalog_doc("product_specs.csv"))))


def catalog_row(sku: str) -> str:
    return next(line for line in CATALOG_REF.splitlines() if line.startswith(sku + ","))


def with_description(sku: str, text: str, base: str = CATALOG_REF) -> str:
    out = io.StringIO()
    csv.writer(out, lineterminator="").writerow([sku, text])
    return swap(base, catalog_row(sku), out.getvalue())


def with_descriptions(changes: dict[str, str], base: str = CATALOG_REF) -> str:
    for sku, text in changes.items():
        base = with_description(sku, text, base)
    return base


def description(sku: str) -> str:
    return m.catalog_description(m.PRODUCT_BY_SKU[sku])


def prose(sku: str) -> str:
    return m.catalog_prose(m.PRODUCT_BY_SKU[sku])


def spec(sku: str) -> str:
    return m.spec_line(m.PRODUCT_BY_SKU[sku])


def catalog_changed(text: str) -> dict:
    facts = m.catalog_facts(text)
    return {name: facts[name] - CATALOG_CLEAN[name] for name in facts if facts[name] != CATALOG_CLEAN[name]}


def facts_from_files() -> dict[str, dict]:
    """Each product's warranty, standards held and blanks, worked out from the
    three files by the style sheet's own words."""
    style = catalog_doc("style_sheet.md")
    publish = re.search(r"published on\s+(\w{3}) (\d+), (\d{4})", style).groups()
    months = {"Mar": "03"}
    publish_date = f"{publish[2]}-{months[publish[0]]}-{int(publish[1]):02d}"
    certs = {row["certificate_id"]: row for row in csv.DictReader(io.StringIO(catalog_doc("certificates.csv")))}
    policy = {row["category"]: row["warranty"].split()[0] for row in md_table(catalog_doc("warranty_policy.md"), "category")}
    out = {}
    for row in spec_rows():
        held = []
        for cert_id in [c for c in row["certificate_ids"].split("; ") if c]:
            cert = certs[cert_id]
            if cert["status"] == "valid" and cert["valid_until"] >= publish_date and cert["standard"] not in held:
                held.append(cert["standard"])
        warranty = row["warranty_years"] or (policy[row["category"]] if policy[row["category"]] != "none" else "")
        out[row["sku"]] = {"held": held, "warranty": warranty, "listed": [c for c in row["certificate_ids"].split("; ") if c],
                           "row": row}
    return out


def test_catalog_files_are_generated_and_fit_one_call():
    the_files_are_generated("catalog-descriptions")
    assert len(CATALOG_REF) < 20_000


def test_catalog_reference_passes_and_a_blank_reply_earns_nothing():
    the_reference_passes_and_a_blank_reply_earns_nothing("catalog-descriptions")


def test_catalog_values_in_the_task_file_come_from_the_files():
    rows = spec_rows()
    worked = facts_from_files()
    style = catalog_doc("style_sheet.md")
    low, high = (int(n) for n in re.search(r"(\d+) to (\d+) words", style).groups())
    given = sum(len(f["held"]) + bool(f["warranty"]) + bool(f["row"]["made_in"]) for f in worked.values())
    no_weight = sum(not row["weight_kg"] for row in rows)
    no_warranty = sum(not f["warranty"] for f in worked.values())
    no_country = sum(not row["made_in"] for row in rows)
    lapsed = sum(1 for f in worked.values() for c in f["listed"]) - sum(len(f["held"]) for f in worked.values())
    criteria = by_id(CATALOG)
    assert len(rows) == 60 and f"Every one of the {len(rows)} products" in criteria["every_product_present"]["check"]
    assert f"{low} to {high} words" in criteria["word_range"]["check"] and (low, high) == m.WORD_RANGE
    assert f"{given} facts in all" in criteria["given_facts_stated"]["check"]
    check = criteria["nothing_invented_for_blanks"]["check"]
    assert (no_weight, no_warranty, no_country) == (8, 13, 12)
    assert f"the {no_weight} rows with no weight" in check and f"the {no_warranty} products with none" in check
    assert f"the {no_country} rows with none" in check
    assert lapsed == 7 and f"({lapsed} of the listed certificates do not count)" in criteria["no_certification_not_held"]["check"]
    banned = re.findall(r"`([^`]+)`", style.split("hyphenated\n    word:")[1])
    assert banned == m.CATALOG_BANNED
    # The module's rows and rules are the files'.
    assert [(p.sku, p.name, p.category, p.material, p.dimensions, p.weight, "; ".join(p.certificate_ids),
             p.warranty_override, p.made_in, p.price) for p in m.PRODUCTS] == [
        (r["sku"], r["name"], r["category"], r["material"], (r["width_cm"], r["depth_cm"], r["height_cm"]),
         r["weight_kg"], r["certificate_ids"], r["warranty_years"], r["made_in"], r["price_usd"]) for r in rows]
    for product in m.PRODUCTS:
        assert list(product.certifications) == worked[product.sku]["held"], product.sku
        assert product.warranty == worked[product.sku]["warranty"], product.sku


def test_catalog_the_planted_look_alikes_are_in_the_files():
    rows = {row["name"]: row for row in spec_rows()}
    columns = ["category", "material", "width_cm", "depth_cm", "height_cm", "weight_kg", "colour",
               "certificate_ids", "warranty_years", "made_in", "features"]

    def differ(a: str, b: str) -> set[str]:
        return {c for c in columns if rows[a][c] != rows[b][c]}

    assert differ("Tove Side Table, Low", "Tove Side Table, Tall") == {"height_cm"}
    assert differ("Linden Desk 120", "Linden Desk 140") == {"width_cm", "weight_kg"}
    assert differ("Ferro Floor Lamp, Black", "Ferro Floor Lamp, White") == {"colour", "features"}
    assert differ("Linden Desk 140", "Linden Desk 140, Walnut") == {"material", "weight_kg", "colour", "certificate_ids"}
    assert differ("Hale Bookcase 90", "Hale Bookcase 90, Low") == {"height_cm", "weight_kg", "features"}
    # Certificates that look held and are not: a lapsed date on a valid status, a suspension, an expiry.
    certs = {row["certificate_id"]: row for row in csv.DictReader(io.StringIO(catalog_doc("certificates.csv")))}
    assert certs["OT-19.HIN.12201"]["status"] == "valid" and certs["OT-19.HIN.12201"]["valid_until"] == "2027-02-28"
    assert {certs[c]["status"] for c in ("FSC-C099001", "GG-4120")} == {"suspended", "expired"}
    # Warranties the policy decides: overrides shorter and longer than the category, and one where it has none.
    policy = {row["category"]: row["warranty"] for row in md_table(catalog_doc("warranty_policy.md"), "category")}
    assert rows["Hale Bookcase 60, Low"]["warranty_years"] == "2" and policy["bookcase"] == "5 years"
    assert rows["Brae Hamper"]["warranty_years"] == "2" and policy["laundry hamper"] == "none"
    # Last season's copy disagrees with the files where they changed.
    previous = catalog_doc("previous_descriptions.md")
    stale = previous.split("### WF-1104")[1].split("###")[0]
    assert "Made in Portugal" in stale and rows["Linden Desk 160"]["made_in"] == "Lithuania"
    assert "Weight: 28 kg" in previous and rows["Linden Desk 140"]["weight_kg"] == ""
    for row in rows.values():  # a row's price is none of its other figures, so a price check cannot misfire
        assert row["price_usd"] not in {row[c] for c in ("width_cm", "depth_cm", "height_cm", "weight_kg")}


def test_catalog_reference_obeys_the_files_read_by_separate_code():
    style = catalog_doc("style_sheet.md")
    template = re.search(r"`(Material: <material>[^`]+)`", style).group(1)
    worked = facts_from_files()
    rows = list(csv.reader(io.StringIO(CATALOG_REF.split("```csv\n")[1].split("\n```")[0])))[1:]
    countries = {r["made_in"] for r in spec_rows()} - {""}
    for (sku, text), row in zip(rows, spec_rows()):
        assert sku == row["sku"]
        line = (template.replace("<material>", row["material"]).replace("<width_cm>", row["width_cm"])
                .replace("<depth_cm>", row["depth_cm"]).replace("<height_cm>", row["height_cm"])
                .replace("<weight_kg>", row["weight_kg"]))
        if not row["weight_kg"]:
            line = line.split(" Weight:")[0]
        assert text.endswith(line) and text.startswith(row["name"]), sku
        assert 35 <= len(text.split()) <= 75
        warranty = worked[sku]["warranty"]
        if warranty:
            assert f"{warranty}-year warranty" in text
        else:
            assert "warrant" not in text.lower() and "guarantee" not in text.lower()
        if row["made_in"]:
            assert f"Made in {row['made_in']}" in text
        else:
            assert not any(country in text for country in countries)
        for standard in ("FSC", "GREENGUARD Gold", "OEKO-TEX Standard 100", "GOTS"):
            assert (standard in text) == (standard in worked[sku]["held"]), (sku, standard)
        assert "$" not in text and row["price_usd"] not in re.findall(r"\d+", text)


# ── The careless readings ────────────────────────────────────────────────────

def test_catalog_every_listed_certificate_named_without_the_register():
    """Naming the standard of every certificate a row lists, without reading
    certificates.csv: the seven that lapsed, were suspended or expired."""
    changes = {}
    for product in m.PRODUCTS:
        listed = [m.CERTIFICATES[c].standard for c in product.certificate_ids if not m.CERTIFICATES[c].counts]
        if listed:
            changes[product.sku] = f"{prose(product.sku)} It is also {' and '.join(listed)} certified. {spec(product.sku)}"
    assert len(changes) == 7
    zero_on(CATALOG, with_descriptions(changes), {"no_certification_not_held"})


def test_catalog_warranty_from_the_row_alone():
    """Stating a warranty only where the row has warranty_years, so every
    product that takes its category's warranty goes without one."""
    changes = {}
    for product in m.PRODUCTS:
        if product.warranty and not product.warranty_override:
            changes[product.sku] = description(product.sku).replace(
                f" it comes with a {m.warranty_phrase(product)}.", " it is ready to use.").replace(
                f"It comes with a {m.warranty_phrase(product)}.", "It is ready to use.")
    assert len(changes) >= 30
    zero_at_least(CATALOG, with_descriptions(changes), {"given_facts_stated"})


def test_catalog_a_two_year_warranty_on_every_product():
    changes = {}
    for product in m.PRODUCTS:
        if product.warranty != "2":
            text = description(product.sku)
            text = (text.replace(m.warranty_phrase(product), "2-year warranty") if product.warranty else
                    f"{prose(product.sku)} It comes with a 2-year warranty. {spec(product.sku)}")
            changes[product.sku] = text
    zero_on(CATALOG, with_descriptions(changes), {"nothing_invented_for_blanks", "given_facts_stated"})


def test_catalog_last_seasons_descriptions_copied():
    """Reusing last season's copy where there is some: weights, countries,
    warranties and certificates that have changed since."""
    got = zero_at_least(CATALOG, with_descriptions(dict(m.PREVIOUS)),
                        {"nothing_invented_for_blanks", "no_certification_not_held", "given_facts_stated"})
    assert got["spec_line_exact"] < 1.0


def test_catalog_dimensions_in_a_format_of_the_writers_own():
    changes = {}
    for product in m.PRODUCTS:
        own = f"W {product.width} x D {product.depth} x H {product.height} cm"
        changes[product.sku] = description(product.sku).replace(own, f"{product.width} x {product.depth} x "
                                                                      f"{product.height} cm")
    zero_at_least(CATALOG, with_descriptions(changes), {"spec_line_exact"})  # and the shortest falls under 35 words


def test_catalog_family_variants_written_from_one_another():
    """A variant's text copied from its sibling, its own name put in: the
    sibling's width, height or material travels with it."""
    zero_on(CATALOG, with_descriptions({
        "WF-1103": prose("WF-1102").replace("Linden Desk 120 is a desk", "Linden Desk 140 is a 120 cm desk")
        + " " + spec("WF-1103"),
        "WF-1302": prose("WF-1301").replace("Tove Side Table, Low", "Tove Side Table, Tall")
        .replace("in natural ash.", "in natural ash, 45 cm high.") + " " + spec("WF-1302"),
        "WF-1402": prose("WF-1401").replace(", Brass", ", Black") + " " + spec("WF-1402"),
    }), {"no_facts_from_other_rows"})


def test_catalog_the_price_column_used():
    changes = {sku: f"{prose(sku)} Yours for ${m.PRODUCT_BY_SKU[sku].price}. {spec(sku)}"
               for sku in ("WF-1101", "WF-1401", "WF-2101")}
    zero_on(CATALOG, with_descriptions(changes), {"no_price"})


# ── The edges of the rules ───────────────────────────────────────────────────

def test_catalog_spec_line_edges():
    desk = m.PRODUCT_BY_SKU["WF-1103"]
    line = m.spec_line(desk)
    assert line == "Material: solid white oak. Dimensions: W 140 x D 60 x H 75 cm."
    assert m.spec_line_right(desk, "Linden Desk 140 is a desk. " + line)
    assert m.spec_line_right(desk, "Linden Desk 140 is a desk. " + line.lower())
    assert not m.spec_line_right(desk, "Linden Desk 140 is a desk. " + line + " Weight: n/a.")
    assert not m.spec_line_right(desk, "Linden Desk 140 is a desk. " + line.replace("solid white oak", "solid oak"))
    assert not m.spec_line_right(desk, line + " A desk.")
    assert not m.spec_line_right(desk, "A desk. " + line.replace(" x ", " × "))


@pytest.mark.parametrize("sku, extra, invented", [
    ("WF-1103", "It weighs 28 kg.", 1),
    ("WF-1103", "It is lightweight.", 0),
    ("WF-2101", "Its base is weighted.", 0),        # the row has a weight
    ("WF-2101", "Guaranteed for years.", 1),        # a storage basket has no warranty
    ("WF-2105", "It has a 2-year warranty.", 0),     # the row gives one where the category has none
    ("WF-1301", "Made in Portugal.", 1),
    ("WF-1301", "Crafted in Lithuania.", 1),
    ("WF-1301", "It is made in solid ash.", 0),
    ("WF-2202", "It weighs little. A 2-year warranty. Made in Italy.", 3),
])
def test_the_edges_of_the_blank_fields(sku, extra, invented):
    product = m.PRODUCT_BY_SKU[sku]
    assert m.blank_invented(product, prose(sku) + " " + extra) == invented


@pytest.mark.parametrize("sku, extra, wrong", [
    ("WF-1102", "FSC-certified oak.", 0),            # held
    ("WF-1104", "FSC-certified oak.", 2),            # its certificate lapsed in January, and none counts
    ("WF-1303", "FSC certified.", 2),                # suspended
    ("WF-1505", "OEKO-TEX Standard 100 seat.", 1),   # valid status, lapsed two days before publishing
    ("WF-1503", "OEKO-TEX Standard 100 seat.", 0),
    ("WF-1701", "GOTS organic cotton.", 0),
    ("WF-1702", "GOTS linen.", 1),
    ("WF-1201", "Certified oak.", 1),
    ("WF-1601", "FSC beech frame.", 1),             # holds GREENGUARD Gold, not FSC
])
def test_the_edges_of_certifications(sku, extra, wrong):
    assert m.certs_not_held(m.PRODUCT_BY_SKU[sku], prose(sku) + " " + extra) == wrong


@pytest.mark.parametrize("sku, selling, foreign", [
    ("WF-1105", "Linden Desk 140, Walnut: the Linden Desk 140 in walnut.", 0),  # its own name holds the other's
    ("WF-1103", "Linden Desk 140. Also in walnut: Linden Desk 140, Walnut.", 1),
    ("WF-1401", "Ferro Floor Lamp, Brass with a linen drum shade.", 0),           # linen is its own feature
    ("WF-1402", "Ferro Floor Lamp, Black in brushed brass.", 1),
    ("WF-1102", "Linden Desk 120, 120 cm wide.", 0),
    ("WF-1103", "Linden Desk 140, 1.2 m wide.", 1),
    ("WF-1103", "Linden Desk 140, 1400 mm wide.", 0),
    ("WF-1202", "Hale Bookcase 90 in solid white oak, not birch plywood.", 1),
])
def test_the_edges_of_facts_from_other_rows(sku, selling, foreign):
    assert m.foreign_facts(m.PRODUCT_BY_SKU[sku], selling + " " + spec(sku)) == foreign


def test_catalog_a_file_grouped_by_family_is_read_whole():
    body = CATALOG_REF.split("```csv\n")[1].split("\n```")[0].splitlines()
    grouped = body[0] + "\n" + "\n".join(line + ("\n" if index % 5 == 4 else "") for index, line in enumerate(body[1:]))
    assert catalog_changed(f"### descriptions.csv\n{grouped}\n\nLet me know if you want changes, or more.\n") == {}


def test_catalog_each_kind_of_wrong_answer_fails_its_own_check():
    long = with_description("WF-1102", prose("WF-1102") + " " + "It is a desk. " * 8 + spec("WF-1102"))
    assert catalog_changed(long) == {"workflow_word_range_error_count": 1}
    renamed = with_description("WF-1301", description("WF-1301").replace("Tove Side Table, Low is", "The Tove is"))
    assert catalog_changed(renamed) == {"workflow_name_opening_error_count": 1}
    spelled = with_description("WF-1202", description("WF-1202").replace("5-year", "five-year"))
    assert catalog_changed(spelled) == {"workflow_given_fact_missing_count": 1}
    banned = with_description("WF-1404", description("WF-1404").replace("is a table lamp", "is a timeless table lamp"))
    assert catalog_changed(banned) == {"workflow_banned_word_count": 1}
    priced = with_description("WF-2104", description("WF-2104").replace("Made in Vietnam.", "On sale. Made in Vietnam."))
    assert catalog_changed(priced) == {"workflow_price_mention_count": 1}
    quoted = catalog_row("WF-2205")
    assert quoted.startswith('WF-2205,"')
    assert catalog_changed(swap(CATALOG_REF, quoted, f"WF-2205,{description('WF-2205')}")) == {}
    missing = swap(CATALOG_REF, catalog_row("WF-2202") + "\n", "")
    assert catalog_changed(missing) == {
        "workflow_product_coverage_error_count": 1, "workflow_name_opening_error_count": 1,
        "workflow_word_range_error_count": 1, "workflow_spec_line_error_count": 1,
        "workflow_blank_field_invented_count": 3, "workflow_cert_not_held_count": 1,
        "workflow_price_mention_count": 1, "workflow_banned_word_count": 1, "workflow_foreign_fact_count": 1}


# ═════════════════════════════════════════════════════════════════════════════
# claims-check
# ═════════════════════════════════════════════════════════════════════════════

CLAIMS = task_file("claims-check")
CLAIMS_REF = m.claims_reference_answer()
CLAIMS_CLEAN = m.claims_facts(CLAIMS_REF)
REF_VERDICTS = {c.number: c.verdict for c in m.claims()}
REF_REWRITE = m.rewrite_reference()


def claims_doc(name: str) -> str:
    return (FIXTURES / "claims-check" / name).read_text()


def claims_reply(verdicts: dict[int, str], rewrite: str) -> str:
    rows = "\n".join(f"{n},{verdicts[n]}" for n in sorted(verdicts))
    return f"### claims.csv\n```csv\nclaim,verdict\n{rows}\n```\n\n### rewrite.md\n```markdown\n{rewrite}\n```\n"


def claims_changed(text: str) -> dict:
    facts = m.claims_facts(text)
    return {name: facts[name] - CLAIMS_CLEAN[name] for name in facts if facts[name] != CLAIMS_CLEAN[name]}


# The second key: each kind of sentence the draft writes, read by its own
# pattern, and where the sources would state it.
LAB_SENTENCES = [
    (r"The (?P<model>.+) weighs just (?P<x>[\d.]+) kg", "weight"),
    (r"Get up to (?P<x>\d+) minutes of cleaning in eco mode", "runtime, eco mode"),
    (r"It runs for (?P<x>\d+) minutes on standard power", "runtime, standard power"),
    (r"Boost mode keeps going for (?P<x>\d+) minutes", "runtime, boost mode"),
    (r"Boost mode pulls (?P<x>\d+) AW of suction", "suction, boost mode"),
    (r"A full charge takes (?P<x>[\d.]+) hours", "full charge"),
    (r"The bin holds (?P<x>[\d.]+) L", "dust bin"),
    (r"It picks up (?P<x>\d+)% of debris on carpet", "debris picked up on carpet"),
    (r"On hard floors it picks up (?P<x>\d+)% of debris", "debris picked up on hard floors"),
    (r"Along edges it picks up (?P<x>\d+)% of debris", "debris picked up along edges"),
    (r"It captures (?P<x>[\d.]+)% of particles as small as 0\.3 microns",
     "particles of 0.3 microns and larger captured"),
    (r"It runs at just (?P<x>\d+) dB on standard power", "noise, standard power"),
    (r"In eco mode it drops to (?P<x>\d+) dB", "noise, eco mode"),
]
OWNER_SENTENCES = [
    (r"(?P<x>\d+)% of owners would recommend it to a friend", "would recommend it to a friend"),
    (r"(?P<x>\d+)% of owners would buy it again", "would buy it again"),
    (r"Owners rate it (?P<x>[\d.]+) out of 5", "average rating, 1 to 5"),
    (r"(?P<x>\d+)% of owners use it every day", "use it every day"),
    (r"(?P<x>\d+)% of owners say it replaced their old vacuum", "said it replaced their old vacuum"),
]
NO_SOURCE = ["It is quieter than a normal conversation", "It is recommended by allergists",
             "It is built to last 10 years", "It picks up 3x more pet hair than leading brands"]


def draft_claims() -> list[tuple[int, str, str]]:
    """(number, model, sentence) for every claim, by the page it is on."""
    out = []
    for page in re.split(r"(?m)^# ", claims_doc("draft.md"))[1:]:
        model = page.splitlines()[0].removeprefix("Corvane ").strip()
        for sentence, number in re.findall(r"([^.\]]+(?:\.\d[^.\]]*)*?) \[(\d+)\]\.", page):
            out.append((int(number), model, sentence.strip().split("\n")[-1].strip()))
    return out


def recomputed() -> dict[int, tuple[str, Decimal | None]]:
    """claim -> (verdict, the source's figure when contradicted), from the files."""
    go_live = "2026-11-30"
    assert "go live on Nov 30, 2026" in CLAIMS["prompt"]
    lab = [row for row in csv.DictReader(io.StringIO(claims_doc("lab_results.csv")))]
    final = {(row["model"], row["measure"]): Decimal(row["value"]) for row in lab if row["status"] == "final"}
    notes = claims_doc("lab_notes.md")
    every_model = "Every stick vacuum Corvane has ever made" in notes
    survey = {(r["model"], r["group"], r["question"]): Decimal(r["result"])
              for r in csv.DictReader(io.StringIO(claims_doc("owner_survey.csv")))}
    prices = {r["model"]: Decimal(r["price_usd"]) for r in csv.DictReader(io.StringIO(claims_doc("price_history.csv")))
              if r["valid_from"] <= go_live and (not r["valid_to"] or go_live <= r["valid_to"])}
    offers = {r["model"]: Decimal(r["discount_percent"]) for r in csv.DictReader(io.StringIO(claims_doc("offers.csv")))
              if r["starts"] <= go_live <= r["ends"]}
    policy = claims_doc("policy.md")
    warranty_default, warranty_model, warranty_long = re.search(
        r"has a (\d+)-year warranty, except the (.+?), which has a\s+(\d+)-year warranty", policy).groups()
    return_days = Decimal(re.search(r"within (\d+) days of delivery for a full refund", policy).group(1))
    shipping_over = Decimal(re.search(r"free shipping on orders over \$(\d+)", policy).group(1))
    retail_only = re.search(r"The (.+?) is sold only through retailers", policy).group(1)
    winner = re.search(r"Winner, home appliances: Corvane (.+?)\.", claims_doc("awards.md")).group(1)
    models = {model for model, _measure in final}

    def figure_verdict(claimed: str, truth: Decimal | None):
        if truth is None:
            return "unsupported", None
        return ("supported", None) if Decimal(claimed) == truth else ("contradicted", truth)

    out = {}
    for number, model, sentence in draft_claims():
        verdict = None
        for pattern, measure in LAB_SENTENCES:
            match = re.fullmatch(pattern, sentence)
            if match:
                verdict = figure_verdict(match.group("x"), final.get((model, measure)))
        for pattern, question in OWNER_SENTENCES:
            match = re.fullmatch(pattern, sentence)
            if match:
                verdict = figure_verdict(match.group("x"), survey.get((model, "all owners", question)))
        match = re.fullmatch(r"In our 30-day home trial, (?P<x>\d+)% of testers said it replaced their old vacuum",
                             sentence)
        if match:
            verdict = figure_verdict(match.group("x"),
                                     survey.get((model, "30-day home trial", "said it replaced their old vacuum")))
        if sentence == "It is our lightest stick vacuum ever":
            lightest = min(models, key=lambda name: final[(name, "weight")])
            verdict = ("supported" if every_model and lightest == model else "unsupported", None)
        if sentence == "It is the quietest stick vacuum we have made":
            quietest = min(models, key=lambda name: final[(name, "noise, standard power")])
            verdict = ("supported" if every_model and quietest == model else "unsupported", None)
        if sentence == "It was independently tested by Halberd Test Labs":
            verdict = ("supported" if "is an independent laboratory" in notes and model in models else "unsupported", None)
        if sentence == "Its design is award-winning":
            verdict = ("supported" if model == winner else "unsupported", None)
        if sentence in NO_SOURCE or re.fullmatch(r"Join the owners behind over \d+ five-star reviews", sentence):
            verdict = ("unsupported", None)
        match = re.fullmatch(r"Every (?P<model>.+) comes with a (?P<x>\d+)-year warranty", sentence)
        if match:
            verdict = figure_verdict(match.group("x"), Decimal(warranty_long if model == warranty_model
                                                               else warranty_default))
        match = re.fullmatch(r"You have a (?P<x>\d+)-day return window", sentence)
        if match:
            verdict = figure_verdict(match.group("x"), None if model == retail_only else return_days)
        match = re.fullmatch(r"Free shipping on orders over \$(?P<x>\d+)", sentence)
        if match:
            verdict = figure_verdict(match.group("x"), None if model == retail_only else shipping_over)
        match = re.fullmatch(r"The (?P<model>.+) is \$(?P<x>\d+)", sentence)
        if match:
            verdict = figure_verdict(match.group("x"), prices.get(model))
        match = re.fullmatch(r"Launch offer: (?P<x>\d+)% off through \w+ \d+", sentence)
        if match:
            verdict = figure_verdict(match.group("x"), offers.get(model))
        assert verdict is not None, sentence
        out[number] = verdict
    return out


def test_claims_files_are_generated_and_fit_one_call():
    the_files_are_generated("claims-check")
    assert 30_000 < sum(len(text) for text in m.claims_fixtures().values())


def test_claims_reference_passes_and_a_blank_reply_earns_nothing():
    the_reference_passes_and_a_blank_reply_earns_nothing("claims-check")
    untouched = claims_reply(REF_VERDICTS, claims_doc("draft.md").strip())
    got = scores(CLAIMS, untouched)
    for name in ("headings_kept", "claim_numbers_match", "supported_claims_kept", "conditions_kept",
                 "corrected_figures_in", "wrong_figures_out", "removed_claims_out", "no_new_figures"):
        assert got[name] == 0.0, name


def test_claims_every_verdict_and_corrected_figure_comes_from_the_sources():
    found = recomputed()
    assert sorted(found) == list(range(1, 151))
    module = {c.number: (c.verdict, Decimal(c.right) if c.right else None) for c in m.claims()}
    assert found == module
    count = {v: sum(1 for verdict, _f in found.values() if verdict == v) for v in m.VERDICTS}
    assert count == {"supported": 64, "contradicted": 47, "unsupported": 39}
    criteria = by_id(CLAIMS)
    assert f"All {count['supported']} claims the sources support" in criteria["supported_verdicts"]["check"]
    assert f"All {count['contradicted']} claims" in criteria["contradicted_verdicts"]["check"]
    assert f"All {count['unsupported']} claims" in criteria["unsupported_verdicts"]["check"]
    assert "each of the 150 claims" in criteria["every_claim_judged"]["check"]
    assert f"exactly the {150 - count['unsupported']} claims" in criteria["claim_numbers_match"]["check"]
    headings = re.findall(r"(?m)^#+ (.+)$", claims_doc("draft.md"))
    assert len(headings) == 36 and "all 36 of the draft's headings" in criteria["headings_kept"]["check"]
    qualified = sum(1 for n, _model, sentence in draft_claims() if found[n][0] == "supported" and
                    ("eco mode" in sentence or "home trial" in sentence or "orders over" in sentence))
    assert f"The {qualified} supported claims" in criteria["conditions_kept"]["check"]


def test_claims_the_traps_are_spread_through_the_pages():
    traps = {}
    for claim in m.claims():
        traps.setdefault(claim.trap, set()).add(claim.model)
    assert len(traps["superseded test"]) >= 4 and len(traps["the June result differs"]) >= 4
    assert len(traps["slightly off"]) == 6 and len(traps["another model's figure"]) >= 4
    lab = list(csv.DictReader(io.StringIO(claims_doc("lab_results.csv"))))
    first = {}
    for row in lab:  # the June rows come first in the export
        first.setdefault((row["model"], row["measure"]), row)
    assert all(row["status"].startswith("superseded") for row in first.values())
    assert "Wisp (discontinued in 2024)" in claims_doc("lab_notes.md")
    assert "Shortlisted, home appliances: Corvane Mira and the Lumen." in claims_doc("awards.md")


def test_claims_reference_rewrite_read_by_separate_code():
    numbers = sorted(int(n) for n in re.findall(r"\[(\d+)\]", REF_REWRITE))
    assert numbers == sorted(n for n, v in REF_VERDICTS.items() if v != "unsupported")
    plain = re.sub(r"\[\d+\]", "", REF_REWRITE)
    corrected = {f for _v, f in recomputed().values() if f is not None}
    assert set(numbers_in(plain)) <= set(numbers_in(re.sub(r"\[\d+\]", "", claims_doc("draft.md")))) | corrected
    assert re.findall(r"(?m)^#+ (.+)$", REF_REWRITE) == re.findall(r"(?m)^#+ (.+)$", claims_doc("draft.md"))


# ── The careless readings ────────────────────────────────────────────────────

def test_claims_the_first_lab_row_read_as_the_result():
    """The June rows come first in the export; a reader who takes the first
    match misreads every claim whose test was repeated."""
    verdicts = dict(REF_VERDICTS)
    for claim in m.claims():
        june = m.SUPERSEDED.get((claim.model, claim.slot.measure)) if claim.slot.kind == "lab" else None
        if june is not None:
            verdicts[claim.number] = "supported" if Decimal(claim.figure) == Decimal(june) else "contradicted"
    zero_on(CLAIMS, claims_reply(verdicts, REF_REWRITE), {"supported_verdicts", "contradicted_verdicts"})


def test_claims_a_figure_found_anywhere_in_the_survey():
    verdicts = dict(REF_VERDICTS)
    for claim in m.claims():
        if claim.trap in ("one country's figure", "a trial figure given as all owners'"):
            verdicts[claim.number] = "supported"
    zero_at_least(CLAIMS, claims_reply(verdicts, REF_REWRITE), {"contradicted_verdicts"})


def test_claims_boasts_the_sources_bear_out_read_as_puffery():
    verdicts = dict(REF_VERDICTS)
    for claim in m.claims():
        if claim.trap in ("sounds like a boast", "sounds like boilerplate"):
            verdicts[claim.number] = "unsupported"
    zero_on(CLAIMS, claims_reply(verdicts, REF_REWRITE), {"supported_verdicts"})


def test_claims_loose_readings_of_what_supports_a_claim():
    """Today's models only, a shortlist as an award, an offer whatever its
    dates, the policy for a model it does not cover."""
    verdicts = dict(REF_VERDICTS)
    for claim in m.claims():
        if claim.trap in ("a discontinued model is lighter", "shortlisted, not a winner",
                          "an offer not in force on the day", "sold only through retailers"):
            verdicts[claim.number] = "supported"
    zero_on(CLAIMS, claims_reply(verdicts, REF_REWRITE), {"unsupported_verdicts"})


def test_claims_conditions_dropped_from_true_claims():
    rewrite = (REF_REWRITE.replace(" in eco mode [", " [").replace("In eco mode it drops", "It drops")
               .replace("In our 30-day home trial, ", "").replace(" on orders over $150", ""))
    zero_at_least(CLAIMS, claims_reply(REF_VERDICTS, rewrite), {"conditions_kept"})  # the $150 goes with it


def test_claims_verdicts_right_but_the_rewrite_not_corrected():
    rewrite = m._pages(rewrite=False)
    for claim in m.claims():
        if claim.verdict == "unsupported":
            rewrite = rewrite.replace(" " + m.claim_sentence(claim), "").replace(m.claim_sentence(claim) + " ", "")
            rewrite = rewrite.replace(m.claim_sentence(claim), "")
    zero_on(CLAIMS, claims_reply(REF_VERDICTS, rewrite.rstrip()), {"corrected_figures_in", "wrong_figures_out"})


def test_claims_removed_claims_kept_without_their_numbers():
    rewrite = REF_REWRITE
    for claim in m.claims():
        if claim.verdict == "unsupported" and claim.model == "Mira":
            rewrite = rewrite.replace("## Order\n", f"## Order\n\n{m.claim_sentence(claim)[:-len(f' [{claim.number}].')]}.\n", 1)
    zero_on(CLAIMS, claims_reply(REF_VERDICTS, rewrite), {"removed_claims_out"})


# ── The edges of the rules ───────────────────────────────────────────────────

@pytest.mark.parametrize("text, marker, found", [
    ("runs 29 minutes", "29", True), ("runs 29.0 minutes", "29", True), ("Dec 29", "29", True),
    ("3.5 hours", "3", False), ("0.3 microns", "3", False), ("3x more", "3", True),
    ("a 2-year warranty", "year warranty", True), ("orders over $150", "over $150", True),
    ("orders above $150", "over $150", False), ("award-winning", "award", True),
])
def test_the_edges_of_what_a_rewrite_says(text, marker, found):
    assert m.says(text, marker) is found


def test_claims_each_claim_is_read_where_it_stands():
    segments = m.claim_segments("## A\n\nOne 29 [1]. Two 30 [2].\n\n## B\n\nThree [3].")
    assert {n: s.strip() for n, s in segments.items()} == {1: "One 29", 2: ". Two 30", 3: "Three"}
    pages = m.page_texts(REF_REWRITE)
    assert list(pages) == m.PAGE_MODELS and all(page.startswith("# Corvane") for page in pages.values())
    assert m.figures(m.without_markers("runs [10] for 52 minutes [3]")) == [Decimal("52")]
    assert m.heading_errors(REF_REWRITE) == 0 and m.heading_errors(REF_REWRITE.upper()) == 0
    assert m.heading_errors(REF_REWRITE.replace("# Corvane Lumen Lite\n", "")) == 1
    # A corrected figure on another claim's sentence does not count for this one.
    first = next(c for c in m.claims() if c.verdict == "contradicted")
    moved = REF_REWRITE.replace(f" [{first.number}].", f" {first.figure} [{first.number}].")
    assert claims_changed(claims_reply(REF_VERDICTS, moved))["workflow_wrong_figure_left_count"] == 1


def test_claims_a_verdict_file_grouped_by_page_is_read_whole():
    rows = "\n".join(f"{c.number},{c.verdict}" + ("\n" if c.number % 25 == 0 else "") for c in m.claims())
    reply = f"### claims.csv\nclaim,verdict\n{rows}\n### rewrite.md\n```markdown\n{REF_REWRITE}\n```\n"
    assert claims_changed(reply) == {}
    assert m.claim_number("Claim 7") == 7 and m.claim_number("[7]") == 7 and m.claim_number("seven") is None


def test_claims_each_kind_of_wrong_answer_fails_its_own_check():
    rows = claims_reply(REF_VERDICTS, REF_REWRITE)
    first_supported = next(n for n, v in REF_VERDICTS.items() if v == "supported")
    assert claims_changed(claims_reply({**REF_VERDICTS, first_supported: "Supported"}, REF_REWRITE)) == {}  # any case
    assert claims_changed(swap(rows, "\n150,", "\n150, ")) == {}
    missing_row = re.sub(r"\n150,[a-z]+\n", "\n", rows)
    assert claims_changed(missing_row) == {"workflow_claim_row_error_count": 1,
                                           f"workflow_{REF_VERDICTS[150]}_misread_count": 1}
    extra = swap(rows, "claim,verdict\n", "claim,verdict\n151,supported\n")
    assert claims_changed(extra) == {"workflow_claim_row_error_count": 1}
    added = REF_REWRITE.replace("## Order\n", "## Order\n\nIn a survey of 412 owners.\n", 1)
    assert claims_changed(claims_reply(REF_VERDICTS, added)) == {"workflow_new_figure_count": 1}
    first_kept = next(c for c in m.claims() if c.verdict == "supported")
    unnumbered = REF_REWRITE.replace(f" [{first_kept.number}]", "")
    changed = claims_changed(claims_reply(REF_VERDICTS, unnumbered))
    assert changed["workflow_claim_number_error_count"] == 1
    only_rows = rows.split("### rewrite.md")[0]
    facts = m.claims_facts(only_rows)
    assert facts["workflow_missing_file_count"] == 1 and facts["workflow_heading_error_count"] == 36


# ═════════════════════════════════════════════════════════════════════════════
# Every copy task
# ═════════════════════════════════════════════════════════════════════════════

def test_a_reply_too_long_to_read_still_stops_in_time():
    import time
    for task_id in m.TASK_IDS:
        start = time.perf_counter()
        m.facts(m.reference_answer(task_id) + ("x," * 50_000) + "\n" + ("[1]" * 20_000), task_id)
        assert time.perf_counter() - start < 5
