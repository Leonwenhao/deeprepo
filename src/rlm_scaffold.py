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
import re
import sys
import time
import traceback
from contextlib import redirect_stdout, redirect_stderr

from .llm_clients import RootModelClient, SubModelClient, TokenUsage, create_root_client
from .codebase_loader import load_codebase, format_metadata_for_prompt
from .prompts import ROOT_SYSTEM_PROMPT, SUB_SYSTEM_PROMPT, ROOT_USER_PROMPT_TEMPLATE


MAX_OUTPUT_LENGTH = 8192  # Truncate REPL output to force model to use code
MAX_TURNS = 15            # Maximum REPL iterations
DEFAULT_MAX_CONCURRENT = 5  # Max parallel sub-LLM calls


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

            # Get root model's response (should contain Python code)
            t0 = time.time()
            response_text = self.root_client.complete(
                messages=messages,
                system=ROOT_SYSTEM_PROMPT,
            )
            root_time = time.time() - t0

            if self.verbose:
                print(f"Root model responded in {root_time:.1f}s ({len(response_text)} chars)")

            # Extract code blocks from the response
            code_blocks = self._extract_code(response_text)

            if not code_blocks:
                if self.verbose:
                    print("No code blocks found in response. Checking if model is done...")
                # Model might have set the answer in a previous turn's code
                if answer["ready"]:
                    break
                # Prompt it to write code
                messages.append({"role": "assistant", "content": response_text})
                messages.append({
                    "role": "user",
                    "content": "Please write Python code in a ```python code block to continue your analysis. Use the REPL to explore the codebase."
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
            })

            # Check if answer is ready
            if answer["ready"]:
                if self.verbose:
                    print(f"\n✅ Answer marked as ready after turn {turn}")
                break

            # Feed REPL output back to root model
            messages.append({"role": "assistant", "content": response_text})
            messages.append({
                "role": "user",
                "content": f"REPL Output:\n```\n{combined_output}\n```\n\nContinue your analysis. Remember to set answer[\"ready\"] = True when done."
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

    def _extract_code(self, response: str) -> list[str]:
        """Extract Python code blocks from the model's response."""
        # Match ```python ... ``` blocks where fences are at line boundaries.
        # Using ^/$ with re.MULTILINE ensures we don't match ``` that
        # appears mid-line inside Python strings (the root cause of
        # premature code-block truncation).
        pattern = r'^```(?:python)?\s*\n(.*?)\n```\s*$'
        blocks = re.findall(pattern, response, re.DOTALL | re.MULTILINE)

        if not blocks:
            # Try to find inline code that looks executable
            # (model might not use code fences)
            lines = response.split("\n")
            code_lines = []
            in_code = False
            for line in lines:
                # Heuristic: lines that look like Python code
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

            if code_lines:
                blocks = ["\n".join(code_lines)]

        return blocks

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
) -> dict:
    """
    Convenience function to run a full RLM analysis.

    Args:
        codebase_path: Local path to the codebase (or git URL)
        verbose: Print progress to stderr
        max_turns: Maximum REPL iterations
        root_model: Model string for root LLM (e.g. "claude-opus-4-6", "claude-sonnet-4-5-20250929")

    Returns:
        dict with analysis, turns, usage, trajectory
    """
    # Validate path for local directories
    actual_path = codebase_path
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
        if verbose:
            print(f"Cloned to {actual_path}")

    # Set up clients
    usage = TokenUsage()
    usage.set_root_pricing(root_model)
    root_client = create_root_client(usage=usage, model=root_model)
    sub_client = SubModelClient(usage=usage)

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
