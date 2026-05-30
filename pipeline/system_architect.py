"""
System Architect Agent.
Converts the structured Intent into a system architecture blueprint (DB tables, APIs, UI pages, Auth roles).
"""

import json
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from pipeline.base import BaseAgent, LLMClient
from pipeline.intent_extractor import Intent


class ArchitectureBlueprint(BaseModel):
    """Pydantic model representing the high-level system blueprint."""
    database: Dict[str, Any] = Field(default_factory=dict)
    api: Dict[str, Any] = Field(default_factory=dict)
    ui: Dict[str, Any] = Field(default_factory=dict)
    auth: Dict[str, Any] = Field(default_factory=dict)


SYSTEM_INSTRUCTION = """
You are the System Architect Agent. Your job is to convert a structured Application Intent into
a system architecture blueprint.

You must output a single JSON object matching the following structure:
{
  "database": {
    "tables": {
      "users": {
        "columns": {"id": "INTEGER", "name": "TEXT", "role": "TEXT"},
        "primary_key": "id"
      }
    }
  },
  "api": {
    "endpoints": {
      "GET /api/users": {
        "auth_required": true,
        "roles": ["admin"],
        "response": {"users": "array"}
      }
    }
  },
  "ui": {
    "pages": {
      "/dashboard": {
        "route": "/dashboard",
        "allowed_roles": ["admin"],
        "components": [
          {"type": "table", "data_source": "GET /api/users"}
        ]
      }
    }
  },
  "auth": {
    "roles": ["admin"],
    "permissions": {
      "admin": ["read", "write"]
    }
  }
}

Be precise. Do not include markdown wraps or conversational text. Just output pure JSON.
"""


class SystemArchitectAgent(BaseAgent):
    """Agent that converts intent to an architecture blueprint."""

    def __init__(self, client: LLMClient) -> None:
        super().__init__(
            client=client,
            stage_name="system_architect",
            system_instruction=SYSTEM_INSTRUCTION,
        )

    def generate_blueprint(self, intent: Intent) -> ArchitectureBlueprint:
        """
        Generates system blueprint from the given Intent model.
        Logs progress and handles failures gracefully.
        """
        self.client.context.log(self.stage_name, "Starting system architecture generation...")

        # Construct prompt containing the intent details
        prompt = f"Generate system blueprint for the following Intent:\n{intent.model_dump_json(indent=2)}"

        try:
            raw_response = self.execute(prompt, json_mode=True)
            self.client.context.log(self.stage_name, "Received response from LLM Client.")

            parsed = json.loads(raw_response)
            blueprint = ArchitectureBlueprint(**parsed)

            self.client.context.stage_outputs["architecture"] = blueprint.model_dump()
            self.client.context.log(
                self.stage_name,
                f"Successfully generated architecture blueprint with "
                f"{len(blueprint.database.get('tables', {}))} DB tables, "
                f"{len(blueprint.api.get('endpoints', {}))} API endpoints, and "
                f"{len(blueprint.ui.get('pages', {}))} UI pages.",
            )
            return blueprint

        except Exception as e:
            err_msg = f"Failed to generate architecture blueprint: {e}"
            self.client.context.log(self.stage_name, err_msg, "ERROR")
            self.client.context.errors.append(err_msg)

            # Fallback minimal blueprint on complete failure
            fallback = ArchitectureBlueprint(
                database={"tables": {}},
                api={"endpoints": {}},
                ui={"pages": {}},
                auth={"roles": intent.user_roles, "permissions": {r: ["read"] for r in intent.user_roles}},
            )
            self.client.context.stage_outputs["architecture"] = fallback.model_dump()
            return fallback
