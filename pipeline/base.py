"""
Base components for the agentic compiler pipeline.
Defines ExecutionContext, LLMClient, and BaseAgent.
"""

import os
import time
import logging
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
    Client wrapper that routes prompt calls to either Google GenAI SDK or the local High-Fidelity Mock.
    Tracks token usage, costs, and latency inside the shared ExecutionContext.
    """

    def __init__(
        self,
        context: Optional[ExecutionContext] = None,
        mock: bool = False,
        model: str = "gemini-2.5-flash",
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
            logger.warning("dotenv not installed, skipping load_dotenv.")

        # Accept GEMINI_API_KEY or GOOGLE_API_KEY
        self.api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

        if self.api_key and not self.mock:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                self.context.log("setup", "Successfully initialized Google GenAI Client with API key.")
            except ImportError:
                self.context.log(
                    "setup",
                    "google-genai package is not installed. Falling back to High-Fidelity Mock.",
                    "WARNING",
                )
                self.mock = True
            except Exception as e:
                self.context.log(
                    "setup",
                    f"Failed to initialize Google GenAI SDK client: {e}. Falling back to Mock.",
                    "WARNING",
                )
                self.mock = True
        else:
            if not self.api_key and not self.mock:
                self.context.log(
                    "setup", "No GEMINI_API_KEY found. Falling back to High-Fidelity Mock.", "INFO"
                )
            self.mock = True

        if self.mock:
            from utils.mock_llm import MockLLM
            self.mock_engine = MockLLM()
            self.context.log("setup", "Initialized High-Fidelity Mock LLM Engine.")

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
        """
        target_model = model or self.model
        start_time = time.time()

        # Calculate estimated input tokens
        input_tokens = self.context.cost_analyzer.estimate_tokens(prompt)
        if system_instruction:
            input_tokens += self.context.cost_analyzer.estimate_tokens(system_instruction)

        response_text = ""
        output_tokens = 0

        self.context.log(stage, f"Invoking model '{target_model}' (mock={self.mock}) for stage '{stage}'...")

        if self.mock:
            try:
                # Simulating network latency based on model tier
                import random
                if "pro" in target_model.lower():
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
                from google.genai import types

                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json" if json_mode else "text/plain",
                    temperature=0.0,  # Ensure highly deterministic compiler responses
                )

                response = self.client.models.generate_content(
                    model=target_model,
                    contents=prompt,
                    config=config,
                )
                response_text = response.text or ""

                if response.usage_metadata:
                    input_tokens = response.usage_metadata.prompt_token_count
                    output_tokens = response.usage_metadata.candidates_token_count
                else:
                    output_tokens = self.context.cost_analyzer.estimate_tokens(response_text)
            except Exception as e:
                err_msg = f"Google GenAI SDK call failure: {e}"
                self.context.log(stage, err_msg, "ERROR")
                raise RuntimeError(err_msg) from e

        latency = time.time() - start_time
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
