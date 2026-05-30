"""
Pydantic models representing the compiled application configuration.
Serves as the schema contract and type safety layer for UI, API, DB, and Auth configurations.
"""

from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field, model_validator, ConfigDict


class ColumnSchema(BaseModel):
    """Schema representing a single database column."""
    model_config = ConfigDict(populate_by_name=True)
    
    type: str
    primary_key: bool = Field(default=False)
    foreign_key_to: Optional[str] = Field(default=None)
    nullable: bool = Field(default=True)


class TableSchema(BaseModel):
    """Schema representing a database table containing columns and relationships."""
    model_config = ConfigDict(populate_by_name=True)
    
    columns: Dict[str, Union[ColumnSchema, str]]
    primary_key: Optional[str] = Field(default=None)
    foreign_keys: Optional[List[Dict[str, str]]] = Field(default=None)

    @model_validator(mode="after")
    def normalize_columns(self) -> "TableSchema":
        """Normalizes columns from string shorthand into rich ColumnSchema objects."""
        normalized = {}
        for col_name, col_val in self.columns.items():
            if isinstance(col_val, str):
                is_pk = (self.primary_key == col_name)
                fk_ref = None
                if self.foreign_keys:
                    for fk in self.foreign_keys:
                        if fk.get("column") == col_name:
                            fk_ref = fk.get("references")
                normalized[col_name] = ColumnSchema(
                    type=col_val,
                    primary_key=is_pk,
                    foreign_key_to=fk_ref,
                    nullable=not is_pk
                )
            else:
                if self.primary_key == col_name:
                    col_val.primary_key = True
                if self.foreign_keys:
                    for fk in self.foreign_keys:
                        if fk.get("column") == col_name and not col_val.foreign_key_to:
                            col_val.foreign_key_to = fk.get("references")
                normalized[col_name] = col_val
        self.columns = normalized
        return self


class DatabaseSchema(BaseModel):
    """Schema representing the database layer containing tables."""
    model_config = ConfigDict(populate_by_name=True)
    
    tables: Dict[str, TableSchema]


class APIFieldSchema(BaseModel):
    """Schema representing an input/output field in an API payload."""
    model_config = ConfigDict(populate_by_name=True)
    
    type: str
    required: bool = Field(default=True)


class APIEndpointSchema(BaseModel):
    """Schema representing a single API endpoint with auth and mapping requirements."""
    model_config = ConfigDict(populate_by_name=True)
    
    request_body: Optional[Dict[str, Union[APIFieldSchema, str]]] = Field(default=None)
    response_body: Optional[Dict[str, Union[APIFieldSchema, str]]] = Field(default=None)
    response: Optional[Dict[str, Union[APIFieldSchema, str]]] = Field(default=None)
    auth_required: bool = Field(default=False)
    allowed_roles: List[str] = Field(default_factory=list, alias="roles")
    roles: Optional[List[str]] = Field(default=None)
    db_operations: Optional[Dict[str, Any]] = Field(default=None)

    @model_validator(mode="after")
    def normalize_api_endpoint(self) -> "APIEndpointSchema":
        """Normalizes API roles and response payload representations."""
        # Align allowed_roles and roles
        if self.roles is not None and not self.allowed_roles:
            self.allowed_roles = self.roles
        if self.allowed_roles and not self.roles:
            self.roles = self.allowed_roles
        
        # Align response and response_body
        if self.response is not None and self.response_body is None:
            self.response_body = self.response
        if self.response_body is not None and self.response is None:
            self.response = self.response_body

        # Normalize request fields
        if self.request_body:
            normalized_req = {}
            for k, v in self.request_body.items():
                if isinstance(v, str):
                    normalized_req[k] = APIFieldSchema(type=v)
                else:
                    normalized_req[k] = v
            self.request_body = normalized_req

        # Normalize response fields
        if self.response_body:
            normalized_resp = {}
            for k, v in self.response_body.items():
                if isinstance(v, str):
                    normalized_resp[k] = APIFieldSchema(type=v)
                else:
                    normalized_resp[k] = v
            self.response_body = normalized_resp
            self.response = normalized_resp

        return self


class APISchema(BaseModel):
    """Schema representing the backend API layer."""
    model_config = ConfigDict(populate_by_name=True)
    
    endpoints: Dict[str, APIEndpointSchema]


class UIComponentActionSchema(BaseModel):
    """Schema representing an action (like a submit or redirect) triggered by a UI component."""
    model_config = ConfigDict(populate_by_name=True)
    
    action_type: str = Field(default="submit")
    target_api: Optional[str] = Field(default=None)
    redirect_to: Optional[str] = Field(default=None)


class UIComponentSchema(BaseModel):
    """Schema representing a UI widget/component inside a page."""
    model_config = ConfigDict(populate_by_name=True)
    
    type: str
    data_source_api: Optional[str] = Field(default=None, alias="data_source")
    data_source: Optional[str] = Field(default=None)
    submit_action: Optional[Union[UIComponentActionSchema, str]] = Field(default=None)
    action: Optional[Union[UIComponentActionSchema, str]] = Field(default=None)
    fields: Optional[List[str]] = Field(default=None)
    label: Optional[str] = Field(default=None)

    @model_validator(mode="after")
    def normalize_ui_component(self) -> "UIComponentSchema":
        """Maps fields and actions to consistent internal field representations."""
        if self.data_source is not None and self.data_source_api is None:
            self.data_source_api = self.data_source
        if self.data_source_api is not None and self.data_source is None:
            self.data_source = self.data_source_api
        if self.action is not None and self.submit_action is None:
            self.submit_action = self.action
        if self.submit_action is not None and self.action is None:
            self.action = self.submit_action
        return self


class UIPageSchema(BaseModel):
    """Schema representing an individual application page containing components."""
    model_config = ConfigDict(populate_by_name=True)
    
    route: str
    allowed_roles: List[str] = Field(default_factory=list)
    layout: Optional[str] = Field(default="grid")
    components: List[UIComponentSchema] = Field(default_factory=list)
    post_login_redirect: Optional[str] = Field(default=None)
    post_checkout_redirect: Optional[str] = Field(default=None)


class UISchema(BaseModel):
    """Schema representing the application UI layer."""
    model_config = ConfigDict(populate_by_name=True)
    
    pages: Dict[str, UIPageSchema]


class AuthRoleSchema(BaseModel):
    """Schema representing permissions and boundaries for a specific role."""
    model_config = ConfigDict(populate_by_name=True)
    
    permissions: List[str] = Field(default_factory=list)
    gated_pages: List[str] = Field(default_factory=list)
    gated_apis: List[str] = Field(default_factory=list)


class AuthSchema(BaseModel):
    """Schema representing the overall auth layer mapping roles to permissions."""
    model_config = ConfigDict(populate_by_name=True)
    
    roles: Dict[str, AuthRoleSchema] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def parse_auth_schema(cls, data: Any) -> Any:
        """Parses various formats of roles and permissions into a standard dictionary mapping."""
        if isinstance(data, dict):
            # If data has roles list and permissions dict:
            # {"roles": ["r1"], "permissions": {"r1": ["p1"]}}
            if "roles" in data and "permissions" in data:
                roles_list = data["roles"]
                permissions_dict = data["permissions"]
                roles_map = {}
                for role in roles_list:
                    perms = permissions_dict.get(role, [])
                    if isinstance(perms, list):
                        roles_map[role] = AuthRoleSchema(permissions=perms)
                    elif isinstance(perms, dict):
                        roles_map[role] = AuthRoleSchema(**perms)
                    else:
                        roles_map[role] = AuthRoleSchema(permissions=[str(perms)])
                
                # Check for optional gated sections
                gated_p = data.get("gated_pages", {})
                gated_a = data.get("gated_apis", {})
                for role, role_schema in roles_map.items():
                    if role in gated_p:
                        role_schema.gated_pages = gated_p[role]
                    if role in gated_a:
                        role_schema.gated_apis = gated_a[role]
                return {"roles": roles_map}
            
            # If the dict is not a direct role mapping but contains key roles
            if "roles" in data and isinstance(data["roles"], dict):
                return data
            
            # Direct mapping format: {"user": AuthRoleSchema, ...}
            if not any(k in data for k in ["roles", "permissions", "gated_pages", "gated_apis"]):
                return {"roles": data}
        return data


class BusinessRuleSchema(BaseModel):
    """Schema representing a single business logic rule."""
    model_config = ConfigDict(populate_by_name=True)
    
    rule_id: str
    description: str
    condition: Optional[str] = Field(default=None)
    action: Optional[str] = Field(default=None)


class BusinessLogicSchema(BaseModel):
    """Schema representing business logic and workflow constraints."""
    model_config = ConfigDict(populate_by_name=True)
    
    rules: List[BusinessRuleSchema] = Field(default_factory=list)
    workflows: Optional[Dict[str, Any]] = Field(default_factory=dict)


class AppMetadata(BaseModel):
    """Metadata describing the application name, description, roles, and pricing."""
    model_config = ConfigDict(populate_by_name=True)
    
    app_name: str = Field(alias="product_name", default="My App")
    description: Optional[str] = Field(default="")
    roles: List[str] = Field(default_factory=list, alias="user_roles")
    pricing_plans: Optional[List[Dict[str, Any]]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def parse_metadata(cls, data: Any) -> Any:
        """Parses intent structure into metadata representation."""
        if isinstance(data, dict):
            if "product_name" in data and "app_name" not in data:
                data["app_name"] = data["product_name"]
            if "user_roles" in data and "roles" not in data:
                data["roles"] = data["user_roles"]
        return data


class UnifiedAppConfigSchema(BaseModel):
    """Unified application configuration schema combining metadata, database, API, UI, Auth, and Business Logic."""
    model_config = ConfigDict(populate_by_name=True)
    
    app_metadata: AppMetadata
    database_schema: DatabaseSchema = Field(alias="db")
    api_schema: APISchema = Field(alias="api")
    ui_schema: UISchema = Field(alias="ui")
    auth_rules: AuthSchema = Field(alias="auth")
    business_logic: Optional[BusinessLogicSchema] = Field(default_factory=BusinessLogicSchema)
    pricing: Optional[Dict[str, Any]] = Field(default=None)

    # Step 3 exact contract fields for absolute compatibility
    intent: Optional[Dict[str, Any]] = Field(default=None)
    entities: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    db_schema: Optional[DatabaseSchema] = Field(default=None)
    auth: Optional[AuthSchema] = Field(default=None)
    assumptions: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def parse_unified_config(cls, data: Any) -> Any:
        """Handles cross-layer schema mappings and extracts metadata configurations."""
        if isinstance(data, dict):
            # Map Step 3 variables to internal fields
            if "db_schema" in data and "db" not in data and "database_schema" not in data:
                data["database_schema"] = data["db_schema"]
                data["db"] = data["db_schema"]
            if "auth" in data and "auth_rules" not in data:
                data["auth_rules"] = data["auth"]
            
            # Map existing fields to Step 3 variables
            if "db" in data and "database_schema" not in data:
                data["database_schema"] = data["db"]
            if "database_schema" in data and "db_schema" not in data:
                data["db_schema"] = data["database_schema"]
            if "api" in data and "api_schema" not in data:
                data["api_schema"] = data["api"]
            if "ui" in data and "ui_schema" not in data:
                data["ui_schema"] = data["ui"]
            if "auth_rules" in data and "auth" not in data:
                data["auth"] = data["auth_rules"]
            if "app_metadata" in data and "intent" not in data:
                data["intent"] = data["app_metadata"]

            if "app_metadata" not in data:
                if "intent" in data:
                    data["app_metadata"] = data["intent"]
                else:
                    metadata_data = {
                        "app_name": data.get("product_name") or data.get("app_name") or "Application",
                        "description": data.get("description") or "",
                        "roles": data.get("user_roles") or data.get("roles") or [],
                        "pricing_plans": data.get("pricing_plans") or []
                    }
                    data["app_metadata"] = metadata_data
                    data["intent"] = metadata_data
        return data

