"""The copy tasks: launch-copy-pack.

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
# Every copy task
# ═════════════════════════════════════════════════════════════════════════════

def test_a_reply_too_long_to_read_still_stops_in_time():
    import time
    for task_id in m.TASK_IDS:
        start = time.perf_counter()
        m.facts(m.reference_answer(task_id) + ("x," * 50_000) + "\n" + ("[1]" * 20_000), task_id)
        assert time.perf_counter() - start < 5
