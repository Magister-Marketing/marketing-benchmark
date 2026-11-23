"""Every board task carries only skills vendored at the pin, each one once,
and no board task carries a skill the pack's catalog routes away from it."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "evals/fixtures/public/skills"

# Work the catalog places in one skill and not in its neighbour. The first
# skill is where the work belongs, the second must not stand in for it.
ROUTED = {
    "outbound-sequence": ("cold-email", "emails"),
    "marketing-plan": ("marketing-plan", "copywriting"),
    "attribution-sensitivity": ("attribution", "analytics"),
    "shopify-meta-capi": ("conversion-tracking", "analytics"),
    "seo-technical-triage": ("seo-audit", "site-architecture"),
    "landing-page": ("copywriting", "site-architecture"),
    "landing-page-repair": ("copywriting", "site-architecture"),
}


def board_tasks():
    board = json.loads((ROOT / "eval_runner/board.json").read_text())
    return [task for area in board["areas"] for task in area["tasks"]]


def skills_of(task_id):
    task = json.loads((ROOT / f"eval_runner/tasks/{task_id}.json").read_text())
    return [Path(path).parent.name for path in task["skills"]]


def test_every_board_task_carries_vendored_skills_once_each():
    vendored = {path.parent.name for path in SKILLS.glob("*/SKILL.md")}
    for task_id in board_tasks():
        skills = skills_of(task_id)
        assert skills, task_id
        assert len(skills) == len(set(skills)), task_id
        assert set(skills) <= vendored, (task_id, set(skills) - vendored)


def test_every_vendored_skill_is_listed_with_its_version_in_the_provenance():
    readme = (SKILLS / "README.md").read_text()
    for path in SKILLS.glob("*/SKILL.md"):
        version = next(
            line.split(":", 1)[1].strip()
            for line in path.read_text().splitlines()
            if line.strip().startswith("version:")
        )
        name = path.parent.name
        assert f"| `{name}/SKILL.md` | `skills/{name}/SKILL.md` | {version} |" in readme, name


def test_routed_work_carries_its_own_skill_and_not_the_neighbour():
    for task_id, (belongs, stands_in) in ROUTED.items():
        skills = skills_of(task_id)
        assert belongs in skills, task_id
        assert stands_in not in skills, task_id
