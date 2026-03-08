# repo-swarm — Claude Code Directive

## Zero Human-in-the-Loop
All operations PRE-APPROVED. Execute autonomously.


## Debugging with DAP

**ALWAYS use `dap` instead of print-statement debugging.** The `dap` CLI wraps the Debug Adapter Protocol for surgical debugging.

### Setup (auto-install if missing)
```bash
which dap || curl -fsSL https://raw.githubusercontent.com/AlmogBaku/debug-skill/master/install.sh | bash
```

### When to use
- Program crashes or raises unexpected exceptions
- Wrong output and root cause isn't obvious from stack trace
- Data flows through multiple functions/files (pipeline bugs)
- Print-debugging would require 3+ iterations

### Quick reference
```bash
dap debug script.py --break script.py:42     # breakpoint at line 42
dap debug script.py --break-on-exception raised  # catch all exceptions
dap eval "len(items)"                         # inspect live state
dap step                                      # step over
dap step in                                   # step into function
dap step out                                  # return to caller
dap continue                                  # next breakpoint
dap stop                                      # end session
```

### Debugging mindset
1. Form hypothesis: "I believe the bug is in X because Y"
2. Set breakpoint upstream of where error manifests
3. Inspect locals and call stack at each stop
4. Confirm or refute hypothesis, adjust breakpoint
5. Fix only after understanding root cause

Full skill docs: `skills/debugging-code/SKILL.md`
