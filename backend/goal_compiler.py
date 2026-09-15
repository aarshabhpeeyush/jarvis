"""Meta-Prompt Engine — compiles natural language objectives into /goal blocks."""
import os
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

COMPILER_SYSTEM = """You are the J.A.R.V.I.S. Goal Compiler. Your sole purpose is to transform
a natural language objective into a structured /goal block for Claude Code.

Output ONLY the following structure — no preamble, no explanation:

```
/goal [Primary Objective — one crisp sentence]

Stack: [comma-separated technologies]

Files:
  - [filename or path]: [what to create/modify and why]
  - [filename or path]: [what to create/modify and why]

Acceptance Rules:
  - [Testable, specific criterion]
  - [Testable, specific criterion]

Logging Hooks:
  - on_file_write: log filename and byte count
  - on_tool_exec: log tool name, inputs, and outputs
  - on_complete: log final status and summary
```

Be comprehensive. List every file that needs to be touched. Acceptance rules must be specific and verifiable."""


async def compile_goal(objective: str) -> str:
    """Compile an objective string into a structured /goal block."""
    response = client.messages.create(
        model="claude-opus-5",
        max_tokens=2048,
        system=COMPILER_SYSTEM,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": f"Compile this objective into a /goal block:\n\n{objective}"}],
    )

    # Extract text from response
    text_blocks = [b.text for b in response.content if hasattr(b, "text")]
    return "\n".join(text_blocks)
