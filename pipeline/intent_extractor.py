"""
Intent Extractor Agent.
Extracts structured intent (features, roles, pricing, operations) from natural language prompts.
"""

import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from pipeline.base import BaseAgent, LLMClient


class PricingPlan(BaseModel):
    """Pydantic model representing a single pricing tier."""
    name: str
    price: float
    features: List[str] = Field(default_factory=list)


class Intent(BaseModel):
    """Pydantic model representing the extracted intent of the user prompt."""
    product_name: str
    features: List[str] = Field(default_factory=list)
    user_roles: List[str] = Field(default_factory=list)
    pricing_plans: List[PricingPlan] = Field(default_factory=list)
    core_operations: List[str] = Field(default_factory=list)


SYSTEM_INSTRUCTION = """
You are the Intent Extractor Agent. Your job is to analyze a natural language software design prompt
and extract a structured JSON representation of the application's intent.

You must output a single JSON object matching the following structure:
{
  "product_name": "Name of the product",
  "features": ["feature 1", "feature 2"],
  "user_roles": ["role 1", "role 2"],
  "pricing_plans": [
    {"name": "Free", "price": 0.0, "features": ["Basic feature"]}
  ],
  "core_operations": ["CRUD tables", "Operation 2"]
}

Be precise. Do not include markdown wraps or any conversational text. Just output pure JSON.
"""


class IntentExtractorAgent(BaseAgent):
    """Agent that extracts intent from a natural language prompt."""

    def __init__(self, client: LLMClient) -> None:
        super().__init__(
            client=client,
            stage_name="intent_extraction",
            system_instruction=SYSTEM_INSTRUCTION,
        )

    def extract_intent(self, prompt: str) -> Intent:
        """
        Parses the user prompt to produce a structured Intent model.
        Logs progress and handles failures gracefully.
        """
        self.client.context.log(self.stage_name, "Starting intent extraction stage...")

        try:
            # Check if running mock and retrieve the simulated intent
            raw_response = self.execute(prompt, json_mode=True)
            self.client.context.log(self.stage_name, "Received response from LLM Client.")

            # Parse JSON response
            parsed = json.loads(raw_response)
            intent = Intent(**parsed)

            # Save to stage outputs
            self.client.context.stage_outputs["intent"] = intent.model_dump()
            self.client.context.log(
                self.stage_name,
                f"Successfully extracted intent for product '{intent.product_name}' "
                f"with roles: {intent.user_roles}.",
            )
            return intent

        except Exception as e:
            err_msg = f"Failed to extract intent: {e}"
            self.client.context.log(self.stage_name, err_msg, "ERROR")
            self.client.context.errors.append(err_msg)

            # Fallback intent in case of complete parsing failure
            fallback = Intent(
                product_name="Fallback Application",
                features=["Default Dashboard"],
                user_roles=["guest"],
                pricing_plans=[PricingPlan(name="Free", price=0.0, features=["Basic usage"])],
                core_operations=["read status"],
            )
            self.client.context.stage_outputs["intent"] = fallback.model_dump()
            return fallback
