"""The Claude Code plugin that builds lessons, written to the data folder on every server start.
See architecture/agent-mode.md, The plugin.

The skills carry the rules in generation/prompts.py, and the subagents take their models from
SUBAGENT_MODELS in config. No token is written: the MCP server gets KEDAMI_PORT and KEDAMI_TOKEN
through ${VAR} expansion from the session's environment.
"""

import json
import shutil
import sys
from pathlib import Path

from ..config import SUBAGENT_MODELS
from ..generation import prompts

NAME = "kedami"
SERVER = "kedami"
VERSION = "0.1.0"
# The server package's folder, so the MCP server can import kedami_server whatever the working directory.
SERVER_DIR = Path(__file__).resolve().parents[2]


# What Claude Code calls the plugin's MCP server. A background job loads the server under this name from
# job_mcp_path, so its tools keep the names the subagents list.
JOB_SERVER = f"plugin_{NAME}_{SERVER}"


def plugin_dir(data_dir: Path) -> Path:
    return data_dir / "agent-plugin"


def job_mcp_path(data_dir: Path) -> Path:
    """The only MCP config a background job loads. See architecture/agent-mode.md, Background jobs."""
    return data_dir / "jobs" / "mcp.json"


def tool(name: str) -> str:
    """A tool's full name, as Claude Code gives it to the plugin's MCP server's tools."""
    return f"mcp__{JOB_SERVER}__{name}"


def write(data_dir: Path) -> Path:
    """Write the plugin, replacing whatever was there."""
    root = plugin_dir(data_dir)
    shutil.rmtree(root, ignore_errors=True)
    files = {
        ".claude-plugin/plugin.json": json.dumps(
            {
                "name": NAME,
                "version": VERSION,
                "description": "Build Kedami lessons with Claude Code.",
                "author": {"name": "Joseph Melesse"},
            }, indent=2
        ),
        ".mcp.json": json.dumps(_mcp_config(), indent=2),
        "skills/lesson/SKILL.md": LESSON_SKILL,
        "skills/solution/SKILL.md": SOLUTION_SKILL,
        "skills/simulation/SKILL.md": SIMULATION_SKILL,
        "agents/verifier.md": _verifier(),
        "agents/hint-checker.md": _hint_checker(),
    }
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text.rstrip() + "\n")
    job_config = job_mcp_path(data_dir)
    job_config.parent.mkdir(parents=True, exist_ok=True)
    job_servers = {"mcpServers": {JOB_SERVER: _mcp_config()["mcpServers"][SERVER]}}
    job_config.write_text(json.dumps(job_servers, indent=2) + "\n")
    return root


def _mcp_config() -> dict:
    return {
        "mcpServers": {
            SERVER: {
                "command": sys.executable,
                "args": ["-m", "kedami_server.mcp"],
                "env": {
                    "PYTHONPATH": str(SERVER_DIR),
                    "KEDAMI_PORT": "${KEDAMI_PORT}",
                    "KEDAMI_TOKEN": "${KEDAMI_TOKEN}",
                },
            }
        }
    }


def _frontmatter(**fields: str | bool) -> str:
    # JSON strings are valid YAML, so values like "[lesson-id]" stay strings.
    lines = [f"{key.replace('_', '-')}: {json.dumps(value)}" for key, value in fields.items()]
    return "---\n" + "\n".join(lines) + "\n---\n\n"


NO_CODE = (
    "Never run code you write, and never write or edit files: everything you make goes to Kedami through its "
    "tools, which check it and store it."
)

LESSON_SKILL = (
    _frontmatter(
        description="Build a Kedami lesson from the course files the student uploaded.",
        disable_model_invocation=True,
        argument_hint="[lesson-id]",
    )
    + f"""# Build a Kedami lesson

You build one lesson for Kedami, a study app, from the course files the student uploaded. The lesson teaches the
ideas the student's problem set needs, in order, with each homework problem placed after what it needs. Kedami's
server checks and stores everything you send through the kedami tools. When a tool refuses something it says why:
fix that and send it again.

{NO_CODE}

## Steps

1. **Pick the lesson.** If a lesson ID was given ($ARGUMENTS), use it. Otherwise call `list_waiting_lessons`: use
   the one lesson waiting, ask the student which if there are several, and if there are none, tell them to upload
   files on Kedami's Upload screen with Claude Code as the builder. Call `start_lesson`. Its `done` field lists the
   steps an earlier session finished; skip those.
2. **Pages (stage 1).** Read every file `start_lesson` lists with the Read tool, PDFs and images included, page by
   page. Transcribe each page by the transcription rules below. Call `save_pages` with every file and its pages in
   order.
3. **Extraction (stage 2).** From the problem set's pages and the reference pages, extract by the extraction rules
   and call `save_extraction`.
4. **Plan (stage 3).** Plan by the plan rules and call `save_plan`. It returns the sections, numbered from 1, with
   the problems Kedami placed in each.
5. **Sections (stage 4).** Write each section by the section rules, in order, and call `save_section` with its
   number. The section's `problems` from `save_plan` are its homework problems, and its `simulation` is its
   simulation brief. For a general lesson, the general rules apply too.
6. **Hints.** `save_section` returns the section's targets. Write up to 3 hints for each by the hint rules. Give
   each target's question, its answer, and its hints to the `hint-checker` subagent. Rewrite each hint it says
   gives the answer away, once, and check the rewrites; drop any still failing. Call `save_hints`, and drop any
   hint it reports as dropped.
7. **Verification.** For each section, start the `verifier` subagent with the lesson ID and the section number,
   and nothing else. Never tell it an answer: it gets its questions from Kedami and solves them from the course
   material, so a mistake in your answers can be caught.
8. **Finish.** Call `finish_lesson` and tell the student the lesson is ready in Kedami.

If the lesson can't be built, such as when the problem set can't be read, call `fail_lesson` with the reason and
tell the student.

## Transcription rules

{prompts.TRANSCRIBE_SYSTEM}

Mark nothing between pages: Kedami labels each page with its file and number.

## Extraction rules

{prompts.EXTRACT_SYSTEM}

## Plan rules

{prompts.PLAN_SYSTEM}

## Section rules

{prompts.SECTION_SYSTEM}

## General lesson rules

Only for a lesson whose subject is general.
{prompts.GENERAL_SECTION_RULES}

## Hint rules

{prompts.HINTS_SYSTEM}
"""
)

SOLUTION_SKILL = (
    _frontmatter(
        description="Write the solution to one problem part of a Kedami lesson.",
        disable_model_invocation=True,
        argument_hint="<lesson-id> <block-id> <part-id>",
    )
    + f"""# Write a Kedami solution

The student asked for the solution to one part of a homework problem: lesson $0, problem $1, part $2.

{NO_CODE}

1. Call `get_solution_request`. Read the course material files it lists. It doesn't show the stored answer, so
   solve the part yourself.
2. Write the solution by the rules for the lesson's subject below, in that subject's shape:
   - math: `method`, `steps`, `final`
   - physics: `given`, `required`, `steps`, `final`
   - general: `steps`, `final`
3. Call `save_solution`. If it returns a disagreement, follow it: recheck the working and write the solution again,
   then save with `after_disagreement` true.
4. Tell the student the solution is ready in Kedami.

## Math

{prompts.steps_system("math")}

## Physics

{prompts.steps_system("physics")}

## General

{prompts.steps_system("general")}
"""
)

SIMULATION_SKILL = (
    _frontmatter(
        description="Write the code for one simulation in a Kedami lesson.",
        disable_model_invocation=True,
        argument_hint="<lesson-id> <block-id>",
    )
    + f"""# Write a Kedami simulation

The student asked for a simulation: lesson $0, block $1.

{NO_CODE} The simulation runs only in Kedami's sandboxed frame.

1. Call `get_simulation_request`. If it has a `failure`, the last version didn't work: write a new, simpler one.
2. Write the code by the rules below and call `save_simulation`.
3. Tell the student to open the simulation in Kedami.

## Rules

{prompts.SIMULATION_SYSTEM}
"""
)


def _verifier() -> str:
    return (
        _frontmatter(
            name="verifier",
            description="Solves one section of a Kedami lesson from scratch, so Kedami can check its stored answers.",
            model=SUBAGENT_MODELS["verifier"],
            tools=", ".join(["Read", tool("get_questions"), tool("save_verification")]),
        )
        + f"""You are given a Kedami lesson ID and a section number.

1. Call `get_questions`. Read the course material files it lists.
2. Solve every question from scratch by the rules below.
3. Call `save_verification` with your answers, then report how many Kedami marked verified.

You never see the stored answers, and nobody should tell you them. Don't ask for them.

{prompts.SOLVE_SYSTEM}"""
    )


def _hint_checker() -> str:
    return (
        _frontmatter(
            name="hint-checker",
            description="Judges whether hints for a Kedami lesson give the answer away.",
            model=SUBAGENT_MODELS["hint_checker"],
            tools="Read",
        )
        + f"""You are given questions, each with its answer and its hints.

{prompts.JUDGE_SYSTEM}

Reply with one line per hint: the target, the hint's position from 1, and "gives it away" or "fine"."""
    )
