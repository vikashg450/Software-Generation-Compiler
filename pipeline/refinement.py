"""
Refinement & Alignment Agent.
Runs cross-layer refinement to align naming conventions, references, and roles.
"""

import json
from typing import Dict, Any, Optional
from pydantic import ValidationError

from pipeline.base import BaseAgent, LLMClient
from pipeline.schemas import UnifiedAppConfigSchema


SYSTEM_INSTRUCTION = """
You are the Refinement Agent. Your job is to analyze a completed Unified Application Configuration,
identify any inconsistent naming conventions, mismatched data types, or invalid references across layers
(UI, API, DB, and Auth), and produce a refined, perfectly aligned configuration.

Ensure that:
1. UI components refer to actual API endpoints.
2. API endpoints map to existing DB tables and columns.
3. Page roles and API roles align with the Roles defined in Auth.
4. Naming conventions are clean and consistent.

You must output a single, refined JSON object matching the input Unified Schema structure.
Be precise. Do not include markdown wraps or conversational text. Just output pure JSON.
"""


class RefinementAgent(BaseAgent):
    """Agent that refines and aligns the unified application schema configuration."""

    def __init__(self, client: LLMClient) -> None:
        super().__init__(
            client=client,
            stage_name="refinement",
            system_instruction=SYSTEM_INSTRUCTION,
        )

    def refine_schema(self, config: UnifiedAppConfigSchema) -> UnifiedAppConfigSchema:
        """
        Refines the schema configuration using the LLM Client.
        Logs progress and handles parsing errors.
        """
        self.client.context.log(self.stage_name, "Starting refinement and alignment stage...")

        # Construct prompt passing the current configuration
        prompt = (
            f"Please review and refine the following application configuration. "
            f"Align naming conventions and cross-layer references:\n"
            f"{config.model_dump_json(by_alias=True, indent=2)}"
        )

        try:
            raw_response = self.execute(prompt, json_mode=True)
            self.client.context.log(self.stage_name, "Received response from LLM Client.")

            parsed = json.loads(raw_response)
            refined_config = UnifiedAppConfigSchema.model_validate(parsed)

            self.client.context.stage_outputs["refined"] = refined_config.model_dump(by_alias=True)
            self.client.context.log(
                self.stage_name,
                f"Successfully refined UnifiedAppConfigSchema for '{refined_config.app_metadata.app_name}'.",
            )
            return refined_config

        except ValidationError as val_err:
            err_msg = f"Refined schema validation failed: {val_err}"
            self.client.context.log(self.stage_name, err_msg, "ERROR")
            self.client.context.errors.append(err_msg)
            # Fallback to the unrefined config if refinement fails validation
            self.client.context.log(
                self.stage_name,
                "Validation of refined configuration failed. Falling back to original configuration.",
                "WARNING",
            )
            return config

        except Exception as e:
            err_msg = f"Failed to refine schemas: {e}"
            self.client.context.log(self.stage_name, err_msg, "ERROR")
            self.client.context.errors.append(err_msg)
            return config
