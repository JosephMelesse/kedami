"""Agent mode's MCP server: Kedami's tools for Claude Code. See architecture/agent-mode.md.

Claude Code starts it from the plugin's .mcp.json. Each tool is one call to an /agent/ route on the
running Kedami server, which it finds through KEDAMI_PORT and KEDAMI_TOKEN in its environment. It
holds no state and touches no files: the server checks and stores everything.
"""

import json
import os

import httpx2
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from .agent.routes import FilePages, TargetHints
from .generation.schemas import Plan, ProblemsAndConcepts, SectionDraft, Solution

# A save may wait on SymPy checks or a diagram layout check, so allow more than the default.
TIMEOUT_S = 120

NOT_CONNECTED = (
    "Kedami isn't connected: KEDAMI_PORT and KEDAMI_TOKEN aren't set. Start Claude Code from Kedami's Terminal "
    "screen, or set both to match a Kedami server started by hand."
)

server = MCPServer(
    "kedami",
    instructions="Tools for building Kedami lessons. Use them as the /kedami:lesson, /kedami:solution, and "
    "/kedami:simulation skills describe.",
)


def client() -> httpx2.Client:
    """A client for the running Kedami server. Tests replace it with one bound to the app."""
    port, token = os.environ.get("KEDAMI_PORT", ""), os.environ.get("KEDAMI_TOKEN", "")
    # An unset variable reaches us unexpanded, as "${KEDAMI_PORT}".
    if not port.isdigit() or not token or token.startswith("${"):
        raise ToolError(NOT_CONNECTED)
    return httpx2.Client(
        base_url=f"http://127.0.0.1:{port}", headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT_S
    )


def call(method: str, path: str, body: dict | None = None) -> dict:
    """One agent route. A refusal becomes a tool error carrying the server's reason, for the agent to act on."""
    try:
        with client() as http:
            response = http.request(method, f"/agent{path}", json=body)
    except httpx2.HTTPError as error:
        raise ToolError(f"Kedami isn't reachable: {error}. Is the app still running?") from error
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = response.text
        if not isinstance(detail, str):
            detail = json.dumps(detail, ensure_ascii=False)
        raise ToolError(f"Kedami refused this ({response.status_code}): {detail}")
    return response.json()


def lesson(lesson_id: str) -> str:
    return f"/lessons/{lesson_id}"


@server.tool()
def list_waiting_lessons() -> dict:
    """Lessons the student uploaded with Claude Code as the builder, still waiting for a session to build them."""
    return call("GET", "/lessons")


@server.tool()
def start_lesson(lesson_id: str) -> dict:
    """Claim a waiting lesson, or resume one started earlier. Returns its subject, the path and role of each
    uploaded file to read, and which steps are already done."""
    return call("POST", f"{lesson(lesson_id)}/start")


@server.tool()
def save_pages(lesson_id: str, files: list[FilePages]) -> dict:
    """Stage 1: every uploaded file, each with its pages transcribed to Markdown with LaTeX, in order.
    Saving pages again deletes every later step."""
    return call("POST", f"{lesson(lesson_id)}/pages", {"files": [f.model_dump() for f in files]})


@server.tool()
def save_extraction(lesson_id: str, extraction: ProblemsAndConcepts) -> dict:
    """Stage 2: every problem with its parts and options, the concepts, and which concepts each problem needs.
    Saving it again deletes the plan and sections."""
    return call("POST", f"{lesson(lesson_id)}/extraction", extraction.model_dump(mode="json"))


@server.tool()
def save_plan(lesson_id: str, plan: Plan) -> dict:
    """Stage 3: the lesson title and the sections in order, each with the concepts it introduces. Kedami places
    each problem and returns the sections, numbered from 1, with their problems. Saving it again deletes the sections."""
    return call("POST", f"{lesson(lesson_id)}/plan", plan.model_dump(mode="json"))


@server.tool()
def save_section(lesson_id: str, number: int, section: SectionDraft) -> dict:
    """Stage 4: one section's blocks, by its number from save_plan. Returns the section's hint targets, or every
    reason it was rejected. Saving a section again replaces it and clears its hints and verification."""
    return call("POST", f"{lesson(lesson_id)}/sections/{number}", section.model_dump(mode="json"))


@server.tool()
def save_hints(lesson_id: str, number: int, items: list[TargetHints]) -> dict:
    """Hints for some of a section's targets, replacing theirs. Kedami keeps the first 3 per target and drops any
    that contain the answer, returning those it dropped and why."""
    return call("POST", f"{lesson(lesson_id)}/sections/{number}/hints", {"items": [i.model_dump() for i in items]})


@server.tool()
def get_questions(lesson_id: str, number: int) -> dict:
    """For the verifier: a section's questions with the form each answer takes, never the stored answers, and the
    course material files to solve them from."""
    return call("GET", f"{lesson(lesson_id)}/sections/{number}/questions")


@server.tool()
def save_verification(lesson_id: str, number: int, solutions: list[Solution]) -> dict:
    """For the verifier: its own answer to each question. Kedami compares them with the stored answers and marks
    the ones that agree verified."""
    body = {"solutions": [s.model_dump(mode="json") for s in solutions]}
    return call("POST", f"{lesson(lesson_id)}/sections/{number}/verification", body)


@server.tool()
def finish_lesson(lesson_id: str) -> dict:
    """Write the finished lesson and open it to the student. Every section must be saved."""
    return call("POST", f"{lesson(lesson_id)}/finish")


@server.tool()
def fail_lesson(lesson_id: str, reason: str) -> dict:
    """End the build because it can't be done, with a reason the student will see."""
    return call("POST", f"{lesson(lesson_id)}/fail", {"reason": reason})


@server.tool()
def get_solution_request(lesson_id: str, block_id: str, part_id: str) -> dict:
    """What a solution writer may see for one problem part: the whole problem, the part, the form of its answer,
    and the course material files. Never the stored answer."""
    return call("GET", f"{lesson(lesson_id)}/blocks/{block_id}/solution-request?part_id={part_id}")


@server.tool()
def save_solution(lesson_id: str, block_id: str, part_id: str, steps: dict, after_disagreement: bool = False) -> dict:
    """Store a part's solution. `steps` has the subject's shape: math {method, steps, final}, physics {given,
    required, steps, final}, general {steps, final}. If its final answer disagrees with the stored one, the first
    save returns the disagreement unsaved; write it again and save with after_disagreement true."""
    body = {"part_id": part_id, "steps": steps, "after_disagreement": after_disagreement}
    return call("POST", f"{lesson(lesson_id)}/blocks/{block_id}/solution", body)


@server.tool()
def get_simulation_request(lesson_id: str, block_id: str) -> dict:
    """A simulation's brief, caption, the section's teaching, and the error from the last version if it failed."""
    return call("GET", f"{lesson(lesson_id)}/blocks/{block_id}/simulation-request")


@server.tool()
def save_simulation(lesson_id: str, block_id: str, code: str) -> dict:
    """Store a simulation's code: the body of simulation(root, canvas, tokens, ready), which must call ready()."""
    return call("POST", f"{lesson(lesson_id)}/blocks/{block_id}/simulation", {"code": code})


if __name__ == "__main__":
    server.run()
