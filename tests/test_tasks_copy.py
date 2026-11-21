"""The copy tasks: launch-copy-pack and catalog-descriptions.

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
    assert task["split"] == "development" and (task["prompt_version"], task["rubric_version"]) == (1, 1)
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
    ("ONE", "SD", "$199 until Mar. 14", 1),           # not the date as the register writes it
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
])
def test_the_edges_of_the_register(code, channel, text, figures_wrong, claims_wrong):
    product = m.LAUNCH_PRODUCT[code]
    assert m.uncleared_figures(product, channel, text) == figures_wrong
    assert m.uncleared_claims(product, channel, text) == claims_wrong


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
# Every copy task
# ═════════════════════════════════════════════════════════════════════════════

def test_a_reply_too_long_to_read_still_stops_in_time():
    import time
    for task_id in m.TASK_IDS:
        start = time.perf_counter()
        m.facts(m.reference_answer(task_id) + ("x," * 50_000) + "\n" + ("[1]" * 20_000), task_id)
        assert time.perf_counter() - start < 5
