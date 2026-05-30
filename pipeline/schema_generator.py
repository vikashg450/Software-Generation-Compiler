"""
Schema Generator Agent.
Generates structured schemas (DB, API, UI, Auth) from the architecture blueprint,
conforming to the strict Pydantic models in pipeline/schemas.py.
"""

import json
from typing import Dict, Any, Optional
from pydantic import ValidationError

from pipeline.base import BaseAgent, LLMClient
from pipeline.system_architect import ArchitectureBlueprint
from pipeline.schemas import UnifiedAppConfigSchema, AppMetadata


SYSTEM_INSTRUCTION = """
You are the Schema Generator Agent. Your job is to take an Architecture Blueprint and
produce a detailed, unified application configuration containing db, api, ui, auth, and optionally business_logic/pricing.

You must output a single JSON object conforming to the following structure:
{
  "app_metadata": {
    "product_name": "Product Name",
    "description": "App description",
    "user_roles": ["admin", "member"]
  },
  "db": {
    "tables": {
      "table_name": {
        "columns": {
          "id": "INTEGER",
          "name": "TEXT"
        },
        "primary_key": "id"
      }
    }
  },
  "api": {
    "endpoints": {
      "GET /api/data": {
        "auth_required": true,
        "roles": ["admin"],
        "response": {"data": "array"}
      }
    }
  },
  "ui": {
    "pages": {
      "/dashboard": {
        "route": "/dashboard",
        "allowed_roles": ["admin"],
        "components": [
          {"type": "table", "data_source": "GET /api/data"}
        ]
      }
    }
  },
  "auth": {
    "roles": ["admin", "member"],
    "permissions": {
      "admin": ["read", "write"],
      "member": ["read"]
    }
  }
}

Be precise. Do not include markdown wraps or conversational text. Just output pure JSON.
"""


class SchemaGeneratorAgent(BaseAgent):
    """Agent that generates unified schemas from a blueprint."""

    def __init__(self, client: LLMClient) -> None:
        super().__init__(
            client=client,
            stage_name="schema_generation",
            system_instruction=SYSTEM_INSTRUCTION,
        )

    def generate_schemas(self, blueprint: ArchitectureBlueprint) -> UnifiedAppConfigSchema:
        """
        Generates and validates schemas conforming to UnifiedAppConfigSchema.
        Logs progress and handles failures gracefully.
        """
        self.client.context.log(self.stage_name, "Starting schema generation...")

        # Construct prompt passing the architecture blueprint
        prompt = f"Generate unified schema configuration from the blueprint:\n{blueprint.model_dump_json(indent=2)}"

        try:
            raw_response = self.execute(prompt, json_mode=True)
            self.client.context.log(self.stage_name, "Received response from LLM Client.")

            parsed = json.loads(raw_response)
            
            # If the response doesn't wrap the schemas in 'db', 'api', etc. let's check
            # but standard mock LLM outputs the clean/error schema structure.
            config = UnifiedAppConfigSchema.model_validate(parsed)

            self.client.context.stage_outputs["schema"] = config.model_dump(by_alias=True)
            self.client.context.log(
                self.stage_name,
                f"Successfully generated and validated UnifiedAppConfigSchema for '{config.app_metadata.app_name}'.",
            )
            return config

        except ValidationError as val_err:
            err_msg = f"Schema validation failed: {val_err}"
            self.client.context.log(self.stage_name, err_msg, "ERROR")
            self.client.context.errors.append(err_msg)
            # Re-raise to let the compiler repair engine know about the failure
            raise RuntimeError(err_msg) from val_err

        except Exception as e:
            err_msg = f"Failed to generate schemas: {e}"
            self.client.context.log(self.stage_name, err_msg, "ERROR")
            self.client.context.errors.append(err_msg)
            raise RuntimeError(err_msg) from e
