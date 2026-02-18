"""
RLM Scaffold — Core Engine for Recursive Language Model Codebase Analysis.

This implements the RLM pattern:
1. Root model (Opus 4.6) receives metadata, NOT file contents
2. Root model writes Python code that executes in a controlled REPL
3. REPL has access to the codebase data + llm_query/llm_batch functions
4. Sub-LLM calls (MiniMax M2.5) happen inside the REPL code
5. Root model sees REPL output, writes more code, iterates
6. Terminates when answer["ready"] = True or max turns reached
"""

import io
import json
import re
import shutil
import sys
import time
import traceback
from contextlib import redirect_stdout, redirect_stderr

from .llm_clients import (
    DEFAULT_SUB_MODEL,
    RootModelClient,
    SubModelClient,
    TokenUsage,
    create_root_client,
)
from .codebase_loader import load_codebase, format_metadata_for_prompt
from .prompts import ROOT_SYSTEM_PROMPT, SUB_SYSTEM_PROMPT, ROOT_USER_PROMPT_TEMPLATE


MAX_OUTPUT_LENGTH = 8192  # Truncate REPL output to force model to use code
MAX_TURNS = 15            # Maximum REPL iterations
DEFAULT_MAX_CONCURRENT = 5  # Max parallel sub-LLM calls

EXECUTE_CODE_TOOL = {
    "name": "execute_python",
    "description": (
        "Execute Python code in the REPL environment. "
        "The code has access to: codebase (dict of filepath->content), "
        "file_tree (string), metadata (dict), llm_query(prompt) -> str, "
        "llm_batch(prompts) -> list[str], and set_answer(text) to submit "
        "the final analysis."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute. Must be valid Python. Do not use markdown fencing.",
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of what this code does and why (1-2 sentences).",
            },
        },
        "required": ["code"],
    },
}


class RLMEngine:
    """
    The RLM execution engine.
    
    Manages the REPL loop, namespace, and communication between
    root model and sub-LLM workers.
    """

    def __init__(
        self,
        root_client: RootModelClient,
        sub_client: SubModelClient,
        usage: TokenUsage,
        max_turns: int = MAX_TURNS,
        max_output_length: int = MAX_OUTPUT_LENGTH,
        verbose: bool = True,
    ):
        self.root_client = root_client
        self.sub_client = sub_client
        self.usage = usage
        self.max_turns = max_turns
        self.max_output_length = max_output_length
        self.verbose = verbose

    def analyze(self, codebase_path: str) -> dict:
        """
        Run RLM analysis on a codebase.
        
        Args:
            codebase_path: Local path to the codebase
            
        Returns:
            {
                "analysis": str,          # The final analysis document
                "turns": int,             # Number of REPL turns taken
                "usage": TokenUsage,      # Token usage and cost tracking
                "trajectory": list[dict], # Full conversation trajectory
            }
        """
        # 1. Load codebase
        if self.verbose:
            print(f"Loading codebase from {codebase_path}...")
        data = load_codebase(codebase_path)
        codebase = data["codebase"]
        file_tree = data["file_tree"]
        metadata = data["metadata"]

        if self.verbose:
            print(f"Loaded {metadata['total_files']} files, {metadata['total_chars']:,} chars")

        # 2. Build the REPL namespace (what the root model's code can access)
        answer = {"content": "", "ready": False}
        repl_namespace = self._build_namespace(codebase, file_tree, metadata, answer)

        # 3. Format the initial prompt (metadata + file tree, NOT file contents)
        metadata_str = format_metadata_for_prompt(metadata)
        user_prompt = ROOT_USER_PROMPT_TEMPLATE.format(
            metadata_str=metadata_str,
            file_tree=file_tree,
        )

        # 4. Run the REPL loop
        messages = [{"role": "user", "content": user_prompt}]
        trajectory = []
        turn = 0

        while turn < self.max_turns:
            turn += 1
            if self.verbose:
                print(f"\n{'='*60}")
                print(f"REPL Turn {turn}/{self.max_turns}")
                print(f"{'='*60}")

            # Get root model's response with tool definition
            t0 = time.time()
            response = self.root_client.complete(
                messages=messages,
                system=ROOT_SYSTEM_PROMPT,
                tools=[EXECUTE_CODE_TOOL],
            )
            root_time = time.time() - t0

            # Extract code — prefer tool_use blocks, fall back to text parsing
            code_blocks, tool_use_info = self._extract_code_from_response(response)
            response_text = self._get_response_text(response)

            if self.verbose:
                print(f"Root model responded in {root_time:.1f}s ({len(response_text)} chars)")
                if tool_use_info:
                    print(f"  [tool_use] {len(tool_use_info)} execute_python call(s)")
                else:
                    print("  [text] Using legacy code extraction")

            if not code_blocks:
                if self.verbose:
                    print("No code blocks found in response. Checking if model is done...")
                if answer["ready"]:
                    break
                # Prompt model to use the tool
                self._append_assistant_message(messages, response)
                messages.append({
                    "role": "user",
                    "content": (
                        "Please use the execute_python tool to write and run Python code "
                        "to continue your analysis. Use the REPL to explore the codebase."
                    ),
                })
                continue

            # Execute each code block in the REPL
            all_output = []
            for i, code in enumerate(code_blocks):
                if self.verbose:
                    # Show first 200 chars of code
                    preview = code[:200] + ("..." if len(code) > 200 else "")
                    print(f"\nExecuting code block {i+1}/{len(code_blocks)}:")
                    print(f"  {preview}")

                output = self._execute_code(code, repl_namespace)
                all_output.append(output)

                if self.verbose:
                    preview = output[:300] + ("..." if len(output) > 300 else "")
                    print(f"  Output: {preview}")

            # Combine outputs
            combined_output = "\n".join(all_output)
            if len(combined_output) > self.max_output_length:
                combined_output = (
                    combined_output[:self.max_output_length]
                    + f"\n\n[OUTPUT TRUNCATED at {self.max_output_length} chars. "
                    f"Total was {len(combined_output)} chars. Use code to filter/search.]"
                )

            # Record trajectory
            trajectory.append({
                "turn": turn,
                "root_response": response_text,
                "code_blocks": code_blocks,
                "repl_output": combined_output,
                "answer_ready": answer["ready"],
                "root_latency_s": root_time,
                "used_tool_use": bool(tool_use_info),
            })

            # Check if answer is ready
            if answer["ready"]:
                if self.verbose:
                    print(f"\n✅ Answer marked as ready after turn {turn}")
                break

            # Feed REPL output back to root model
            if tool_use_info:
                # Tool_use path: send structured tool_result messages
                self._append_tool_result_messages(
                    messages, response, tool_use_info, all_output
                )
            else:
                # Text-only path: send as user message (legacy behavior)
                self._append_assistant_message(messages, response)
                messages.append({
                    "role": "user",
                    "content": (
                        f"REPL Output:\n```\n{combined_output}\n```\n\n"
                        "Continue your analysis. Remember to call set_answer(text) when done."
                    ),
                })

        # 5. Return results
        if not answer["ready"]:
            if self.verbose:
                print(f"\n⚠️ Max turns ({self.max_turns}) reached without answer[\"ready\"] = True")
            if answer["content"]:
                if self.verbose:
                    print("Using partial answer from answer[\"content\"]")
            else:
                answer["content"] = "[Analysis incomplete — max turns reached]"

        return {
            "analysis": answer["content"],
            "turns": turn,
            "usage": self.usage,
            "trajectory": trajectory,
        }

    def _build_namespace(
        self,
        codebase: dict,
        file_tree: str,
        metadata: dict,
        answer: dict,
    ) -> dict:
        """
        Build the Python namespace for the REPL.
        
        This is what the root model's code can access:
        - codebase, file_tree, metadata (data)
        - llm_query, llm_batch (sub-LLM functions)
        - answer (output variable)
        - Standard Python builtins
        """
        def llm_query(prompt: str) -> str:
            """Send a focused task to a sub-LLM worker."""
            return self.sub_client.query(prompt, system=SUB_SYSTEM_PROMPT)

        def llm_batch(prompts: list[str]) -> list[str]:
            """Send multiple tasks to sub-LLM workers in parallel."""
            return self.sub_client.batch(
                prompts,
                system=SUB_SYSTEM_PROMPT,
                max_concurrent=DEFAULT_MAX_CONCURRENT,
            )

        def set_answer(text: str) -> None:
            """Set the final analysis and mark it as ready.

            Use this instead of assigning to answer["content"] directly —
            it avoids string-escaping issues with triple-quoted markdown
            inside exec().
            """
            answer["content"] = text
            answer["ready"] = True

        namespace = {
            # Data (the codebase lives HERE, not in the model's context)
            "codebase": codebase,
            "file_tree": file_tree,
            "metadata": metadata,
            # Sub-LLM functions
            "llm_query": llm_query,
            "llm_batch": llm_batch,
            # Answer helper
            "set_answer": set_answer,
            # Answer variable (Prime Intellect pattern)
            "answer": answer,
            # Standard library modules the model might want
            "re": re,
            "os": __import__("os"),
            "json": __import__("json"),
            "collections": __import__("collections"),
        }
        # Add builtins
        namespace["__builtins__"] = __builtins__

        return namespace

    @staticmethod
    def _is_prose_line(line: str) -> bool:
        """Check if a line looks like English prose rather than Python code."""
        stripped = line.strip()
        if not stripped:
            return False
        # Common prose starters
        prose_starters = (
            "Let ", "Now ", "Here ", "The ", "This ", "That ",
            "I ", "We ", "It ", "Note ", "Next ", "First ",
            "Second ", "Finally ", "However ", "Also ",
        )
        if stripped.startswith(prose_starters):
            return True
        # Markdown list markers
        if re.match(r'^(\*\s+|- |\d+\.\s|> )', stripped):
            return True
        # General pattern: capitalized word followed by space (prose sentence)
        if re.match(r'^[A-Z][a-z]+ ', stripped):
            return True
        return False

    def _split_wrapped_blocks(self, blocks: list[str]) -> list[str]:
        """Handle blocks where the model wrapped prose + code in one fence.

        When the model produces a single fenced block that starts with
        English prose and contains inner ```python / ``` markers, extract
        only the inner fenced code sections.  Blocks that start with
        Python code are returned unchanged.
        """
        result: list[str] = []
        for block in blocks:
            # Skip empty / whitespace-only blocks
            if not block.strip():
                continue
            blines = block.split("\n")
            first_nonblank = next((l for l in blines if l.strip()), "")
            has_inner_fence = any(
                re.match(r'^```(?:python)?\s*$', l) for l in blines
            )
            if self._is_prose_line(first_nonblank) and has_inner_fence:
                # Re-parse: extract inner fenced sections
                inner = self._extract_inner_fences(blines)
                if inner:
                    result.extend(inner)
                # else: drop entirely (pure prose)
            else:
                result.append(block)
        return result

    def _extract_inner_fences(self, lines: list[str]) -> list[str]:
        """Extract code from inner ```python / ``` pairs within a block."""
        blocks: list[str] = []
        i = 0
        while i < len(lines):
            if re.match(r'^```(?:python)?\s*$', lines[i]):
                i += 1
                code_lines: list[str] = []
                while i < len(lines):
                    if re.match(r'^```\s*$', lines[i]):
                        break
                    code_lines.append(lines[i])
                    i += 1
                if code_lines:
                    blocks.append("\n".join(code_lines))
            i += 1
        return blocks

    def _extract_code(self, response: str) -> list[str]:
        """Extract Python code blocks from the model's response.

        Uses a line-by-line scanner instead of a single regex so that
        triple-backticks appearing *inside* Python string literals
        (e.g. f-strings that build sub-LLM prompts) are not mistaken
        for the closing fence of the code block.
        """
        blocks: list[str] = []
        lines = response.split("\n")
        i = 0

        while i < len(lines):
            # Look for an opening fence at column 0
            if re.match(r'^```(?:python)?\s*$', lines[i]):
                i += 1
                code_lines: list[str] = []
                # Collect lines until we find the *real* closing fence
                while i < len(lines):
                    if re.match(r'^```\s*$', lines[i]):
                        # Candidate closing fence — peek ahead to decide
                        next_idx = i + 1
                        # Skip blank lines when peeking
                        while next_idx < len(lines) and lines[next_idx].strip() == "":
                            next_idx += 1

                        is_real_close = True
                        if next_idx < len(lines):
                            peek = lines[next_idx]
                            # If the next non-empty line looks like continued
                            # Python code, this ``` is inside a string literal
                            if not (re.match(r'^```', peek)
                                    or self._is_prose_line(peek)):
                                is_real_close = False

                        # Even if peek-ahead says "real close", check for
                        # unbalanced triple quotes — that means we're still
                        # inside a multi-line string literal.
                        if is_real_close:
                            accumulated = "\n".join(code_lines)
                            if (accumulated.count('"""') % 2 == 1
                                    or accumulated.count("'''") % 2 == 1):
                                is_real_close = False

                        if is_real_close:
                            break  # accept this as the real closing fence
                        else:
                            # Inner fence (e.g. inside an f-string) — keep it
                            code_lines.append(lines[i])
                    else:
                        code_lines.append(lines[i])
                    i += 1

                if code_lines:
                    blocks.append("\n".join(code_lines))
            i += 1

        # Post-process: the model sometimes wraps prose + nested
        # ```python blocks inside a single outer fence.  When the
        # extracted block starts with prose, split it on inner fences.
        blocks = self._split_wrapped_blocks(blocks)

        if not blocks:
            # Fallback: try to find inline code that looks executable
            # (model might not use code fences)
            code_lines = []
            in_code = False
            for line in lines:
                stripped = line.strip()
                if stripped.startswith(("import ", "from ", "print(", "for ", "if ",
                                        "answer[", "result", "files", "prompts",
                                        "llm_query", "llm_batch")):
                    in_code = True
                    code_lines.append(line)
                elif in_code and (stripped.startswith((" ", "\t")) or stripped == ""):
                    code_lines.append(line)
                elif in_code and not stripped.startswith(("#", "```")):
                    in_code = False

            # Bug 2 fix: reject if the block looks like prose
            if code_lines:
                first_non_empty = next(
                    (l.strip() for l in code_lines if l.strip()), ""
                )
                if not self._is_prose_line(first_non_empty):
                    blocks = ["\n".join(code_lines)]

        return blocks

    def _extract_code_from_response(self, response) -> tuple[list[str], list[dict]]:
        """Extract code from tool_use blocks in the response.

        Returns:
            (code_blocks, tool_use_info) where:
            - code_blocks: list of Python code strings to execute
            - tool_use_info: list of dicts with 'id' key for each tool_use block
              (empty list if no tool_use found — means text-only response)
        """
        code_blocks: list[str] = []
        tool_use_info: list[dict] = []
        text_parts: list[str] = []

        if isinstance(response, str):
            return self._extract_code(response), []

        if hasattr(response, "content") and isinstance(response.content, list):
            # Anthropic response format
            for block in response.content:
                if block.type == "tool_use" and block.name == "execute_python":
                    block_input = block.input if isinstance(block.input, dict) else {}
                    code = block_input.get("code")
                    if isinstance(code, str):
                        code_blocks.append(code)
                        tool_use_info.append({"id": block.id})
                elif block.type == "text":
                    text_parts.append(block.text)
        elif hasattr(response, "choices"):
            # OpenAI/OpenRouter response format
            message = response.choices[0].message
            if message.tool_calls:
                for tc in message.tool_calls:
                    if tc.function.name != "execute_python":
                        continue
                    try:
                        args = json.loads(tc.function.arguments)
                    except (TypeError, json.JSONDecodeError):
                        args = {}
                    code = args.get("code")
                    if isinstance(code, str):
                        code_blocks.append(code)
                        tool_use_info.append({"id": tc.id})
            if message.content:
                text_parts.append(message.content)

        if code_blocks:
            return code_blocks, tool_use_info

        # Fallback: text-only response — use legacy parser
        full_text = "\n".join(text_parts)
        return self._extract_code(full_text), []

    def _get_response_text(self, response) -> str:
        """Extract text content from response for logging and trajectory."""
        if isinstance(response, str):
            return response
        if hasattr(response, "content") and isinstance(response.content, list):
            # Anthropic
            parts = []
            for block in response.content:
                if block.type == "text":
                    parts.append(block.text)
                elif block.type == "tool_use":
                    parts.append(f"[tool_use: {block.name}]")
            return "\n".join(parts)
        if hasattr(response, "choices"):
            # OpenAI
            msg = response.choices[0].message
            parts = []
            if msg.content:
                parts.append(msg.content)
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    parts.append(f"[tool_use: {tc.function.name}]")
            return "\n".join(parts)
        return str(response)

    def _append_assistant_message(self, messages: list[dict], response) -> None:
        """Append the assistant's response to the message list."""
        if isinstance(response, str):
            messages.append({"role": "assistant", "content": response})
            return

        if hasattr(response, "content") and isinstance(response.content, list):
            # Anthropic — serialize content blocks to dicts
            content_blocks = []
            for block in response.content:
                if hasattr(block, "model_dump"):
                    content_blocks.append(block.model_dump())
                else:
                    if block.type == "text":
                        content_blocks.append({"type": "text", "text": block.text})
                    elif block.type == "tool_use":
                        content_blocks.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
            messages.append({"role": "assistant", "content": content_blocks})
            return

        if hasattr(response, "choices"):
            # OpenAI — reconstruct the assistant message
            msg = response.choices[0].message
            entry: dict = {"role": "assistant", "content": msg.content or ""}
            if msg.tool_calls:
                tool_calls = []
                for tc in msg.tool_calls:
                    if hasattr(tc, "model_dump"):
                        tool_calls.append(tc.model_dump())
                    else:
                        tool_calls.append({
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        })
                entry["tool_calls"] = tool_calls
            messages.append(entry)
            return

        messages.append({"role": "assistant", "content": str(response)})

    def _append_tool_result_messages(
        self,
        messages: list[dict],
        response,
        tool_use_info: list[dict],
        outputs: list[str],
    ) -> None:
        """Append assistant message + tool_result messages after tool_use execution."""
        # First, append the assistant's response (includes tool_use blocks)
        self._append_assistant_message(messages, response)

        if hasattr(response, "content") and isinstance(response.content, list):
            # Anthropic format: tool_results go in a single user message
            tool_results = []
            for info, output in zip(tool_use_info, outputs):
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": info["id"],
                    "content": output,
                })
            messages.append({"role": "user", "content": tool_results})
        elif hasattr(response, "choices"):
            # OpenAI format: each tool_result is a separate "tool" role message
            for info, output in zip(tool_use_info, outputs):
                messages.append({
                    "role": "tool",
                    "tool_call_id": info["id"],
                    "content": output,
                })

    def _execute_code(self, code: str, namespace: dict) -> str:
        """
        Execute Python code in the controlled REPL namespace.
        
        Captures stdout and returns it as a string.
        Catches exceptions and returns the traceback.
        """
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exec(code, namespace)
        except Exception:
            # Capture the traceback
            tb = traceback.format_exc()
            stdout_capture.write(f"\n[EXECUTION ERROR]\n{tb}")

        output = stdout_capture.getvalue()
        stderr_output = stderr_capture.getvalue()

        if stderr_output:
            output += f"\n[STDERR]\n{stderr_output}"

        return output if output else "[No output]"


def run_analysis(
    codebase_path: str,
    verbose: bool = True,
    max_turns: int = MAX_TURNS,
    root_model: str = "claude-opus-4-6",
    sub_model: str = DEFAULT_SUB_MODEL,
) -> dict:
    """
    Convenience function to run a full RLM analysis.

    Args:
        codebase_path: Local path to the codebase (or git URL)
        verbose: Print progress to stderr
        max_turns: Maximum REPL iterations
        root_model: Model string for root LLM (e.g. "claude-opus-4-6", "claude-sonnet-4-5-20250929")
        sub_model: OpenRouter model string for sub-LLM file analysis workers

    Returns:
        dict with analysis, turns, usage, trajectory
    """
    # Validate path for local directories
    actual_path = codebase_path
    is_temp = False
    if not codebase_path.startswith(("http://", "https://", "git@")):
        from pathlib import Path
        p = Path(codebase_path)
        if not p.exists():
            raise FileNotFoundError(f"Path not found: {codebase_path}")
        if not p.is_dir():
            raise ValueError(f"Path is not a directory: {codebase_path}")

    # Handle git URLs
    if codebase_path.startswith(("http://", "https://", "git@")):
        from .codebase_loader import clone_repo
        if verbose:
            print(f"Cloning {codebase_path}...")
        actual_path = clone_repo(codebase_path)
        is_temp = True
        if verbose:
            print(f"Cloned to {actual_path}")

    try:
        # Set up clients
        usage = TokenUsage()
        usage.set_root_pricing(root_model)
        root_client = create_root_client(usage=usage, model=root_model)
        sub_client = SubModelClient(usage=usage, model=sub_model)

        # Run the engine
        engine = RLMEngine(
            root_client=root_client,
            sub_client=sub_client,
            usage=usage,
            max_turns=max_turns,
            verbose=verbose,
        )

        result = engine.analyze(actual_path)

        if verbose:
            print(f"\n{usage.summary()}")

        return result
    finally:
        if is_temp:
            shutil.rmtree(actual_path, ignore_errors=True)
