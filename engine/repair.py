"""
Repair Agent.
Analyzes validation/runtime errors and repairs the schema configuration.
"""

import json
import logging
from typing import List, Optional
from pydantic import ValidationError

from pipeline.base import BaseAgent, LLMClient
from pipeline.schemas import UnifiedAppConfigSchema

logger = logging.getLogger("RepairAgent")


SYSTEM_INSTRUCTION = """
You are the Repair Agent. Your job is to analyze a Unified Application Configuration that failed validation,
read the detailed validation error report, and correct ONLY the erroneous parts of the configuration
to resolve the failures while maintaining the rest of the application structure unchanged.

You must output a single, corrected JSON object matching the input Unified Schema structure.
Be precise. Do not include markdown wraps or conversational text. Just output pure JSON.
"""


class RepairAgent(BaseAgent):
    """Agent that performs isolated repairs on faulty schema configurations."""

    def __init__(self, client: LLMClient) -> None:
        super().__init__(
            client=client,
            stage_name="repair",
            system_instruction=SYSTEM_INSTRUCTION,
        )

    def repair_schema(
        self, config: UnifiedAppConfigSchema, errors: List[str]
    ) -> UnifiedAppConfigSchema:
        """
        Executes a repair iteration by feeding the errors and config back to the LLM.
        """
        self.client.context.log(self.stage_name, f"Starting repair process for {len(errors)} error(s)...")

        # Format the prompt to include the error messages and current config
        errors_str = "\n".join(f"- {err}" for err in errors)
        prompt = (
            f"The following application configuration failed validation:\n"
            f"{config.model_dump_json(by_alias=True, indent=2)}\n\n"
            f"Validation Errors:\n"
            f"{errors_str}\n\n"
            f"Please repair the configuration to resolve all validation errors and return the complete corrected JSON."
        )

        try:
            raw_response = self.execute(prompt, json_mode=True)
            self.client.context.log(self.stage_name, "Received repaired response from LLM Client.")

            parsed = json.loads(raw_response)
            repaired_config = UnifiedAppConfigSchema.model_validate(parsed)

            self.client.context.log(
                self.stage_name,
                f"Successfully repaired configuration for '{repaired_config.app_metadata.app_name}'.",
            )
            return repaired_config

        except ValidationError as val_err:
            err_msg = f"Repaired configuration failed Pydantic validation: {val_err}"
            self.client.context.log(self.stage_name, err_msg, "ERROR")
            self.client.context.errors.append(err_msg)
            return config

        except Exception as e:
            err_msg = f"Failed during repair execution: {e}"
            self.client.context.log(self.stage_name, err_msg, "ERROR")
            self.client.context.errors.append(err_msg)
            return config
