# CLAUDE.md — Film Scan Calibration

## Rule 1: spawn subagents via the CLI, never the `Agent` tool

`coder` and `Explore` MUST be launched as background CLI processes:

```
claude --bg "<prompt>" --agent coder --effort low --permission-mode auto
claude --bg "<prompt>" --agent Explore --permission-mode auto
```

- **`coder` always runs at `--effort low`.** Never omit the flag, never raise it.
- **`Explore` takes no `--effort` flag** — it runs on Haiku, which has no effort level.

### Collecting the result

`--bg` prints a short session id. The transcript is
`~/.claude/projects/<project-slug>/<session-id>.jsonl`. Wait for it, then read it:

```
# WAIT — poll STATUS, in the foreground, bounded. Works for both agents.
n=0; until [ "$(claude agents --json 2>/dev/null | jq -r '.[]
  | select(.id=="<id>") | .status')" = "idle" ] || [ $n -ge 90 ]; do
  sleep 5; n=$((n+1)); done

# READ
f=$(find ~/.claude/projects -name "<id>*.jsonl" | head -1)
jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="text") | .text' "$f"
grep -o '"model":"[^"]*"' "$f" | sort -u    # confirm which model actually ran
grep -o '"effort":"[^"]*"' "$f" | sort -u   # confirm coder actually ran low
```

Four traps, all hit in practice:

- **Wait on `status == "idle"`, not on transcript text.** `coder` narrates before it works
  ("I'll read the relevant code first"), so a poll for the first assistant text block
  returns during the run and you read a stub. Status is correct for both agents.
  (Plain `claude agents` needs a TTY and fails — always `--json`.)
- **Never poll for `"type":"result"`** — these background transcripts never write that
  record, so the loop just runs to timeout. While an agent is still working its only
  content blocks are `thinking` and `tool_use`.
- **Don't background the waiter.** A `run_in_background` poll outlives its usefulness and
  fires a spurious notification after you have already read the result. Foreground and
  bounded (`n -ge 90` ≈ 450 s).
- **Never `claude logs <id>`** — it replays the raw TUI, kilobytes of ANSI escapes for a
  400-word answer. That is the exact context bloat the delegation was meant to prevent.

**Locate the transcript with `find`, not a fixed path.** The project slug is derived from the
agent's cwd, so an agent that moved (e.g. into a worktree) writes to a *different*
`~/.claude/projects/<slug>/` directory and a fixed-path glob silently finds nothing.

**Check `git status` after every `coder` run** before verifying. `coder` is instructed to work
in place, but if edits ever land on a worktree branch instead, pull just its files across —
don't merge the branch, which would drag in unrelated auto-snapshot commits:

```
git checkout <worktree-branch> -- <file> [<file>...]
```

Why the CLI: `effort:` frontmatter is silently ignored when an agent is spawned via the
`Agent` tool ([claude-code#43083](https://github.com/anthropics/claude-code/issues/43083)) —
the subagent inherits the *session* effort instead. The explicit `--effort` flag is honoured.

## Rule 2: routing

| Task shape | Route |
|---|---|
| "Find / where / which files use X", structure sweeps; **and** extract/summarize from long data files, logs, script output, long docs | **`Explore`** |
| Substantial or repetitive codegen (multi-file, or large enough to bloat main context), verifiable by RUNNING | **`coder`**, then verify by running |
| One-file / small / judgment-heavy edit | **inline (main model)** |

**Highest-ROI habit: reflexively send searches and long-file reads to `Explore`.** That is
where main context silently bloats.

Delegation exists to keep big reads and token-heavy generation out of the main context
window. Two limits follow from that:

- **Don't delegate below the cold-start line.** Every spawn re-reads files and re-derives
  context you already hold. A small edit is cheaper inline.
- **Don't verify by re-reading.** If checking `coder`'s output means deeply reading its
  diff, the work was paid for twice. Verify objectively — compile, diff, run.

Batch related edits into ONE `coder` delegation to amortize its cold-start.

## Rule 3: verify by running, not by reading

The scripts self-report objective metrics (`node solve: residual …`, `LUT 33^3 RMSE …`,
`serialized … RMSE …`). After a `coder` edit, run the script and read the one-line metric.
`coder` does not test its own work — that check is yours, and it is not optional.

## The roster

Two project agents, in `.claude/agents/`. The roster stays at two.

- **`coder`** — `model: claude-opus-5`, spawned at `--effort low`. Implements; does not verify.
- **`Explore`** — `model: claude-haiku-4-5-20251001`, `tools: Read, Grep, Glob`. Read-only;
  **shadows the built-in `Explore` by name**.

Each agent's own file is the source of truth for *how it behaves*; this file governs *when
to reach for it*. Don't restate agent-body rules here.

## Editing `.claude/agents/*.md`

Broken YAML fails **silently** — the agent doesn't register and the built-in/default runs
in its place.

- The block needs BOTH an opening and a closing `---`; the body starts after the closing one.
- Keep `description:` a short plain one-liner with NO colon-space (`: `) inside it — an
  unquoted `: ` is invalid YAML and kills the whole file. Detailed guidance goes in the
  body, not the description.
- After ANY edit: run `python3 .claude/agents/check-frontmatter.py`, then confirm the live
  model on a test spawn with `grep -o '"model":"[^"]*"' <task output file>`.
- Tell that a shadow failed to load: the session-start agent list shows the *built-in's*
  description.

## Verified facts

- **Name-shadowing works**: `Explore` spawned with no model override ran
  `claude-haiku-4-5`, which could only come from `.claude/agents/Explore.md`. The registry
  hot-reloads mid-session — no fresh session needed.
- **`model:` overrides apply live**, including in background jobs.
- **To check what effort actually ran**, grep the task output file for `"effort":"..."`.
  Never ask the agent — effort is an inference-time parameter it cannot introspect and will
  hallucinate.
