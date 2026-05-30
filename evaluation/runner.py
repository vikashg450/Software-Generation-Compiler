"""
Evaluation runner for executing prompts through the compilation pipeline.
Tracks metrics like latency, retries/repairs, token usage, cost, and success rate.
"""

import time
import logging
from typing import Dict, Any, List, Tuple
from pipeline.base import ExecutionContext, LLMClient
from pipeline.intent_extractor import IntentExtractorAgent
from pipeline.system_architect import SystemArchitectAgent
from pipeline.schema_generator import SchemaGeneratorAgent
from pipeline.refinement import RefinementAgent
from engine.validator import validate_config
from engine.repair import RepairAgent
from engine.runtime import run_simulation
from evaluation.dataset import DATASET

logger = logging.getLogger("EvaluationRunner")


class EvaluationRunner:
    """
    Orchestrates the entire compilation, validation, repair, and simulation pipeline
    for evaluation.
    """

    def __init__(self, mock: bool = True, model: str = "gemini-2.5-flash") -> None:
        self.mock = mock
        self.model = model

    def run_prompt(self, prompt: str, max_repairs: int = 3) -> Dict[str, Any]:
        """
        Runs a single prompt through the multi-stage pipeline, validation, repair, and simulation.
        Returns a dictionary of execution metrics and results.
        """
        context = ExecutionContext()
        client = LLMClient(context=context, mock=self.mock, model=self.model)
        
        # Ensure mock engine injects errors initially for edge cases to test repair loop
        if self.mock and client.mock_engine:
            client.mock_engine.reset_state()
            client.mock_engine.inject_errors = True

        start_time = time.time()
        retries = 0
        success = False
        final_errors: List[str] = []
        sim_logs: List[str] = []
        config = None

        try:
            # Stage 1: Intent Extraction
            extractor = IntentExtractorAgent(client)
            intent = extractor.extract_intent(prompt)
            if context.errors:
                raise RuntimeError(f"Intent extraction failed: {context.errors[-1]}")

            # Stage 2: System Architect Blueprint
            architect = SystemArchitectAgent(client)
            blueprint = architect.generate_blueprint(intent)
            if context.errors:
                raise RuntimeError(f"System architect blueprint generation failed: {context.errors[-1]}")

            # Stage 3: Schema Generation
            generator = SchemaGeneratorAgent(client)
            config = generator.generate_schemas(blueprint)
            if context.errors:
                raise RuntimeError(f"Schema generation failed: {context.errors[-1]}")

            # Stage 4: Refinement
            refinement = RefinementAgent(client)
            config = refinement.refine_schema(config)

            # Validation & Repair Loop (Up to max_repairs iterations)
            repair_agent = RepairAgent(client)
            for iteration in range(max_repairs + 1):
                # 1. Run validation check
                val_errors = validate_config(config)
                
                # 2. Run simulation check if validation passes
                sim_errors = []
                iter_sim_logs = []
                if not val_errors:
                    sim_errors, iter_sim_logs = run_simulation(config)
                    sim_logs.extend(iter_sim_logs)

                current_errors = val_errors + sim_errors

                if not current_errors:
                    # Clean compilation success!
                    success = True
                    final_errors = []
                    context.log("compiler", f"Configuration compiled successfully on iteration {iteration}!")
                    break

                if iteration < max_repairs:
                    retries += 1
                    context.log(
                        "compiler",
                        f"Compilation check failed on iteration {iteration} with {len(current_errors)} errors. "
                        f"Triggering repair...",
                        "WARNING",
                    )
                    # Trigger repair agent
                    config = repair_agent.repair_schema(config, current_errors)
                else:
                    final_errors = current_errors
                    context.log(
                        "compiler",
                        f"Compilation failed after maximum repair attempts ({max_repairs}).",
                        "ERROR",
                    )

        except Exception as e:
            err_msg = f"Uncaught pipeline exception: {e}"
            context.log("compiler", err_msg, "ERROR")
            final_errors.append(err_msg)

        total_latency = time.time() - start_time
        metrics = context.cost_analyzer.get_metrics()

        return {
            "success": success,
            "retries": retries,
            "latency": round(total_latency, 3),
            "cost": metrics.total_cost_usd,
            "input_tokens": metrics.total_input_tokens,
            "output_tokens": metrics.total_output_tokens,
            "total_tokens": metrics.total_tokens,
            "calls": metrics.total_calls,
            "errors": final_errors,
            "logs": [f"[{log['stage'].upper()}] {log['message']}" for log in context.logs],
            "sim_logs": sim_logs,
            "config": config.model_dump(by_alias=True) if config else None,
        }

    def evaluate_dataset(self, max_repairs: int = 3) -> List[Dict[str, Any]]:
        """
        Runs the full 20-prompt dataset and gathers metrics.
        """
        results = []
        for case in DATASET:
            logger.info(f"Running evaluation case: {case['name']} (Type: {case['type']})")
            res = self.run_prompt(case["prompt"], max_repairs=max_repairs)
            res.update({
                "id": case["id"],
                "name": case["name"],
                "type": case["type"],
                "prompt": case["prompt"],
            })
            results.append(res)
        return results
