# ecc-opencode-agent-complete

**Complete the ECC → OpenCode agent conversion offline: every agent in `agents/` becomes a runnable OpenCode subagent, and every emitted install path resolves.**

Upstream: https://github.com/affaan-m/ECC

## Why this exists now

ECC ships **72 agent definitions** in `agents/`, but its OpenCode conversion only registers **27** of them in `.opencode/opencode.json`. Commands that name the other 46 silently run without those agents (issue [#4027](https://github.com/affaan-m/ECC/issues/4027): `/review-pr` can only start `code-reviewer` on OpenCode; 46 of 72 agents are never installed). A second, independent report shows the same closure failure on the install side: the installed `opencode.json` points at `AGENTS.md` and `CONTRIBUTING.md` that the home install never writes, and older profiles reference skills that are not installed (issue [#4029](https://github.com/affaan-m/ECC/issues/4029)).

`ecc doctor` reports OK in both cases. The gap is not a broken file — it is a **two-sided closure** problem: repository agents are not mapped into the target registry, and registry references are not checked against the installed tree.

## What this tool does

It works only on public upstream files; it never edits the checkout.

- `check` — diffs `agents/*.md` against `.opencode/opencode.json`, reports unregistered agents, stale registrations, missing prompt files, command bodies that name unregistered agents, and instructions that do not resolve relative to the config.
- `emit` — writes a **self-contained install directory**: a complete `opencode.json` with all missing agents registered, converted prompt files under `prompts/agents/`, plus copies of already-referenced prompts and resolvable instruction files. Existing entries are preserved byte-for-byte in meaning.
- `verify-install` — checks an installed `opencode.json`: every `{file:...}` prompt and every `instructions` entry must exist.

### Real result on `affaan-m/ECC` @ `main` (2026-11-19)

```
$ ./bin/ecc-opencode-agent-complete check --repo /path/to/ECC --json
repo_agents=72  registered_agents=27  missing_agent_count=46
commands_affected=10
missing_instructions=13

$ ./bin/ecc-opencode-agent-complete emit --repo /path/to/ECC --out /tmp/ecc-out
emitted 46 agents, 46 prompt files

$ ./bin/ecc-opencode-agent-complete verify-install --install /tmp/ecc-out
missing agent prompts: 0
```

Numbers above are from real runs on a sparse checkout of upstream (commit fetched 2026-11-19). The 46 names are in `check --json`; 10 commands are affected, including `review-pr`, `feature-dev`, `react-review`, `vue-review`, `fastapi-review`, `gan-build`, `hookify`, `marketing-campaign`, `orch-fix-defect`, `react-test`. Instruction count depends on checkout completeness: 12 skill paths were absent from the sparse checkout used for the measurement, so the tool reported them rather than pretending they resolved.

## Install

Python 3.9+, standard library only. No network, no packages.

```bash
git clone <this repo>
cd ecc-opencode-agent-complete
./bin/ecc-opencode-agent-complete --help
```

## Usage

```bash
# 1. Report the gap (exit 1 when anything is unclosed)
./bin/ecc-opencode-agent-complete check --repo /path/to/ECC --json

# 2. Build a complete drop-in install tree
./bin/ecc-opencode-agent-complete emit --repo /path/to/ECC --out /tmp/ecc-out

# 3. Verify the tree before copying it into ~/.config/opencode
./bin/ecc-opencode-agent-complete verify-install --install /tmp/ecc-out --json
```

Copy the emitted tree into your OpenCode config directory yourself:

```bash
cp -a /tmp/ecc-out/. ~/.config/opencode/
```

### `--json` output example

`examples/in/repo` is a miniature upstream checkout. Running `check --json` produces `examples/out/check.json`:

```json
{
  "missing_agents": ["code-simplifier", "comment-analyzer"],
  "commands_with_missing_agents": {"review-pr": ["code-simplifier", "comment-analyzer"]},
  "missing_instructions": ["AGENTS.md", "skills/tdd-workflow/SKILL.md"],
  "ok": false
}
```

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | closure complete / emit succeeded / install verified |
| `1` | real gap found (unregistered agent, missing prompt, unresolved instruction) |
| `2` | usage or input error (bad path, unreadable JSON) |

## Tests

```bash
python3 -m unittest discover -s tests -v
```

18 tests, 15 behavior tests (exit codes + JSON assertions), 0.8 s, offline.

## What this tool does not do

- It does not run OpenCode or execute agents; it verifies the static conversion and install closure.
- It does not decide which agents a profile *should* install. It treats `agents/*.md` as the source of truth and preserves existing registry entries.
- It does not fetch missing instruction files. If a referenced file is absent from the checkout, it reports it instead of inventing content.
- It does not modify upstream or open pull requests.

## 本轮创新

First tool to close the **two-sided** ECC/OpenCode conversion gap as one operation: it maps all 72 repository agents into the target registry and, in the same pass, makes the emitted install tree self-consistent (`emit` then `verify-install` = 0 missing prompts). Prior work audits one side (repo registry or installed config); this one generates the missing 46 prompt files, copies the 26 existing ones, and proves the result resolves. The ledger has no ECC/OpenCode conversion entry.

## License

MIT. Test fixtures are synthetic, modeled on upstream file shapes; no upstream source is vendored.