"""The Claude Code plugin the server writes to the data folder. See architecture/agent-mode.md, The plugin."""

import json
import sys

from kedami_server.agent import plugin
from kedami_server.config import MODEL_ROLES
from kedami_server.generation import prompts


def frontmatter(text):
    head = text.split("---\n")[1]
    return {key: json.loads(value) for key, value in (line.split(": ", 1) for line in head.strip().splitlines())}


def test_writes_every_file(tmp_path):
    root = plugin.write(tmp_path)
    assert root == tmp_path / "agent-plugin"
    files = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
    assert files == [
        ".claude-plugin/plugin.json",
        ".mcp.json",
        "agents/hint-checker.md",
        "agents/verifier.md",
        "skills/lesson/SKILL.md",
        "skills/simulation/SKILL.md",
        "skills/solution/SKILL.md",
    ]
    assert json.loads((root / ".claude-plugin/plugin.json").read_text())["name"] == "kedami"


def test_the_mcp_server_runs_on_this_python_and_gets_the_token_by_name_only(tmp_path):
    config = json.loads((plugin.write(tmp_path) / ".mcp.json").read_text())["mcpServers"]["kedami"]
    assert config["command"] == sys.executable
    assert config["args"] == ["-m", "kedami_server.mcp"]
    assert config["env"]["KEDAMI_PORT"] == "${KEDAMI_PORT}"
    assert config["env"]["KEDAMI_TOKEN"] == "${KEDAMI_TOKEN}"
    assert (plugin.SERVER_DIR / "kedami_server" / "mcp.py").exists()
    assert config["env"]["PYTHONPATH"] == str(plugin.SERVER_DIR)


def test_skills_carry_the_pipelines_prompts(tmp_path):
    root = plugin.write(tmp_path)
    lesson = (root / "skills/lesson/SKILL.md").read_text()
    for rules in (prompts.TRANSCRIBE_SYSTEM, prompts.EXTRACT_SYSTEM, prompts.PLAN_SYSTEM, prompts.SECTION_SYSTEM,
                  prompts.HINTS_SYSTEM):
        assert rules in lesson
    solution = (root / "skills/solution/SKILL.md").read_text()
    assert all(prompts.steps_system(s) in solution for s in ("math", "physics", "general"))
    assert prompts.SIMULATION_SYSTEM in (root / "skills/simulation/SKILL.md").read_text()


def test_skills_run_only_when_the_student_asks(tmp_path):
    root = plugin.write(tmp_path)
    for name in ("lesson", "solution", "simulation"):
        assert frontmatter((root / f"skills/{name}/SKILL.md").read_text())["disable-model-invocation"] is True


def test_subagents_take_their_models_from_config_and_only_the_tools_they_need(tmp_path):
    root = plugin.write(tmp_path)
    verifier = frontmatter((root / "agents/verifier.md").read_text())
    assert verifier["model"] == MODEL_ROLES["second_solve"].model
    assert verifier["tools"] == (
        "Read, mcp__plugin_kedami_kedami__get_questions, mcp__plugin_kedami_kedami__save_verification"
    )
    checker = frontmatter((root / "agents/hint-checker.md").read_text())
    assert (checker["model"], checker["tools"]) == (MODEL_ROLES["small_check"].model, "Read")
    assert prompts.SOLVE_SYSTEM in (root / "agents/verifier.md").read_text()


def test_rewriting_removes_stale_files(tmp_path):
    root = plugin.write(tmp_path)
    (root / "skills/old").mkdir()
    (root / "skills/old/SKILL.md").write_text("stale")
    plugin.write(tmp_path)
    assert not (root / "skills/old").exists()
