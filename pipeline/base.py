"""
Base components for the agentic compiler pipeline.
Defines ExecutionContext, LLMClient, and BaseAgent.
"""

import os
import time
import logging
import json
from typing import Dict, Any, List, Optional

from utils.cost_analyzer import CostAnalyzer

logger = logging.getLogger("PipelineBase")


class ExecutionContext:
    """
    Shared execution context representing a single compilation run.
    Stores process logs, intermediate agent outputs, errors, and tracks performance/costs.
    """

    def __init__(self) -> None:
        self.cost_analyzer = CostAnalyzer()
        self.logs: List[Dict[str, Any]] = []
        self.stage_outputs: Dict[str, Any] = {}
        self.errors: List[str] = []

    def log(self, stage: str, message: str, level: str = "INFO") -> None:
        """Logs a compiler progress step."""
        log_entry = {
            "stage": stage,
            "message": message,
            "level": level,
            "timestamp": time.time(),
        }
        self.logs.append(log_entry)

        log_msg = f"[{stage.upper()}] {message}"
        if level == "ERROR":
            logger.error(log_msg)
        elif level == "WARNING":
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

    def reset(self) -> None:
        """Resets the context for a clean compilation process."""
        self.cost_analyzer.reset()
        self.logs.clear()
        self.stage_outputs.clear()
        self.errors.clear()
        logger.info("ExecutionContext has been reset.")


class LLMClient:
    """
    Client wrapper that routes prompt calls to either Anthropic Claude API or the local High-Fidelity Mock.
    Tracks token usage, costs, and latency inside the shared ExecutionContext.
    """

    def __init__(
        self,
        context: Optional[ExecutionContext] = None,
        mock: bool = False,
        model: str = "claude-3-5-sonnet-20241022",
    ) -> None:
        self.context = context or ExecutionContext()
        self.mock = mock
        self.model = model
        self.client = None
        self.mock_engine = None

        # Load environment variables from .env
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

        # Check mock flag in environment
        env_mock = os.environ.get("MOCK_LLM", "false").lower() == "true"
        if env_mock:
            self.mock = True

        self.api_key = os.environ.get("ANTHROPIC_API_KEY")

        if self.api_key and not self.mock:
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=self.api_key)
                self.context.log("setup", "Successfully initialized Anthropic Claude Client with API key.")
            except ImportError:
                self.context.log(
                    "setup",
                    "anthropic package is not installed. Falling back to High-Fidelity Mock.",
                    "WARNING",
                )
                self.mock = True
            except Exception as e:
                self.context.log(
                    "setup",
                    f"Failed to initialize Anthropic client: {e}. Falling back to Mock.",
                    "WARNING",
                )
                self.mock = True
        else:
            if not self.mock and not self.api_key:
                self.context.log(
                    "setup", "No ANTHROPIC_API_KEY found. Falling back to High-Fidelity Mock.", "INFO"
                )
                self.mock = True

        if self.mock:
            from utils.mock_llm import MockLLM
            self.mock_engine = MockLLM()
            self.context.log("setup", "Initialized High-Fidelity Mock LLM Engine.")

    def _clean_json(self, text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return text

    def _execute_call(
        self,
        prompt: str,
        system_instruction: Optional[str],
        target_model: str,
        stage: str,
    ) -> tuple[str, int, int, float]:
        """Runs the actual call and returns (response_text, input_tokens, output_tokens, latency)"""
        start_time = time.time()
        input_tokens = self.context.cost_analyzer.estimate_tokens(prompt)
        if system_instruction:
            input_tokens += self.context.cost_analyzer.estimate_tokens(system_instruction)

        response_text = ""
        output_tokens = 0

        self.context.log(stage, f"Invoking model '{target_model}' (mock={self.mock}) for stage '{stage}'...")

        if self.mock:
            try:
                import random
                if "sonnet" in target_model.lower() or "pro" in target_model.lower():
                    sleep_time = random.uniform(0.8, 1.4)
                else:
                    sleep_time = random.uniform(0.2, 0.5)
                time.sleep(sleep_time)

                response_text = self.mock_engine.generate_response(prompt, stage=stage)
                output_tokens = self.context.cost_analyzer.estimate_tokens(response_text)
            except Exception as e:
                err_msg = f"Mock LLM failure: {e}"
                self.context.log(stage, err_msg, "ERROR")
                raise RuntimeError(err_msg) from e
        else:
            try:
                message = self.client.messages.create(
                    model=target_model,
                    max_tokens=8192,
                    temperature=0.0,  # Ensure highly deterministic compiler responses
                    system=system_instruction or "",
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                response_text = message.content[0].text
                input_tokens = message.usage.input_tokens
                output_tokens = message.usage.output_tokens
            except Exception as e:
                err_msg = f"Anthropic Claude API call failure: {e}"
                self.context.log(stage, err_msg, "ERROR")
                raise RuntimeError(err_msg) from e

        latency = time.time() - start_time
        return response_text, input_tokens, output_tokens, latency

    def call_llm(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        json_mode: bool = False,
        stage: str = "general",
        model: Optional[str] = None,
    ) -> str:
        """
        Executes a call to the LLM (real or mock).
        Tracks and records metrics (tokens, cost, latency) in the shared execution context.
        Contains JSON parse failure retry logic with markdown code block stripping.
        """
        # Map model names to Claude equivalents
        raw_model = model or self.model
        if "pro" in raw_model.lower() or "sonnet" in raw_model.lower():
            target_model = "claude-3-5-sonnet-20241022"
        elif "flash" in raw_model.lower() or "haiku" in raw_model.lower():
            target_model = "claude-3-5-haiku-20241022"
        else:
            target_model = "claude-3-5-sonnet-20241022"

        response_text, input_tokens, output_tokens, latency = self._execute_call(
            prompt, system_instruction, target_model, stage
        )

        if json_mode:
            cleaned = self._clean_json(response_text)
            try:
                # Validate parseability
                json.loads(cleaned)
                response_text = cleaned
            except Exception as parse_err:
                self.context.log(
                    stage,
                    f"JSON parsing failed initially: {parse_err}. Retrying once with explicit syntax warning...",
                    "WARNING",
                )
                # Build retry prompt
                retry_prompt = (
                    f"Your previous response was:\n{response_text}\n\n"
                    f"This response failed to parse as valid JSON. Please correct it and output ONLY the valid raw JSON object. "
                    f"Do not include any explanations, introductory text, or markdown code block fences."
                )
                # Retry once
                retry_response, r_in, r_out, r_lat = self._execute_call(
                    retry_prompt, system_instruction, target_model, stage
                )
                response_text = self._clean_json(retry_response)
                input_tokens += r_in
                output_tokens += r_out
                latency += r_lat

                try:
                    json.loads(response_text)
                    self.context.log(stage, "JSON successfully parsed on retry.")
                except Exception as retry_err:
                    self.context.log(
                        stage,
                        f"JSON parsing failed on retry attempt: {retry_err}. Proceeding with raw string.",
                        "ERROR",
                    )

        cost = self.context.cost_analyzer.track_call(
            model=target_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency=latency,
        )

        self.context.log(
            stage,
            f"Call finished in {latency:.2f}s. "
            f"Tokens: {input_tokens} in / {output_tokens} out. Cost: ${cost:.6f}",
        )

        return response_text


class BaseAgent:
    """
    Base class for all compiler agents.
    Provides shared interface and utilities for executing compiler pipeline stages.
    """

    def __init__(self, client: LLMClient, stage_name: str, system_instruction: Optional[str] = None) -> None:
        self.client = client
        self.stage_name = stage_name
        self.system_instruction = system_instruction

    def execute(self, prompt: str, json_mode: bool = True, **kwargs) -> str:
        """
        Executes the agent's instruction against the LLM Client.
        """
        return self.client.call_llm(
            prompt=prompt,
            system_instruction=self.system_instruction,
            json_mode=json_mode,
            stage=self.stage_name,
            **kwargs,
        )
