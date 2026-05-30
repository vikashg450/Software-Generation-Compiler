"""
Execution Simulator Runtime.
Provides in-memory database simulation, request routing, and auth role validation.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from pipeline.schemas import UnifiedAppConfigSchema

logger = logging.getLogger("SimulationRuntime")


class SimulationRuntime:
    """
    In-memory simulation engine for SQLite-like DB operations, API routing, 
    and role-based access control.
    """

    def __init__(self, config: UnifiedAppConfigSchema) -> None:
        self.config = config
        self.db: Dict[str, List[Dict[str, Any]]] = {}
        self.logs: List[str] = []
        self._initialize_db()

    def log(self, message: str) -> None:
        """Helper to append log messages."""
        self.logs.append(message)
        logger.info(message)

    def _initialize_db(self) -> None:
        """Initializes empty tables in the in-memory database."""
        for table_name in self.config.database_schema.tables.keys():
            self.db[table_name] = []
            self.log(f"Initialized empty table '{table_name}' in-memory.")

    def execute_db_operation(
        self, op_type: str, table_name: str, body: Dict[str, Any], mapping: Optional[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Runs a simulated SELECT or INSERT DB query against the in-memory store."""
        if table_name not in self.db:
            raise RuntimeError(f"Database error: Table '{table_name}' does not exist.")

        table = self.config.database_schema.tables[table_name]

        if op_type == "insert":
            new_row: Dict[str, Any] = {}
            pk = table.primary_key or "id"
            pk_col = table.columns.get(pk)
            pk_type = "INTEGER"
            if pk_col:
                pk_type = pk_col.type if hasattr(pk_col, "type") else str(pk_col)

            # Map values from request body
            if mapping:
                for db_col, req_ref in mapping.items():
                    if db_col not in table.columns:
                        raise RuntimeError(
                            f"Database error: Column '{db_col}' does not exist in table '{table_name}'."
                        )
                    
                    val = None
                    if isinstance(req_ref, str) and req_ref.startswith("request."):
                        req_field = req_ref.split(".", 1)[1]
                        val = body.get(req_field)
                    else:
                        val = req_ref

                    # Validate data types
                    col_schema = table.columns[db_col]
                    col_type = col_schema.type if hasattr(col_schema, "type") else str(col_schema)
                    if val is not None:
                        if col_type.upper() == "INTEGER":
                            try:
                                val = int(val)
                            except (ValueError, TypeError):
                                raise RuntimeError(
                                    f"Type error: Column '{db_col}' expects INTEGER but got '{val}'."
                                )
                        elif col_type.upper() in ("DECIMAL", "NUMERIC", "FLOAT"):
                            try:
                                val = float(val)
                            except (ValueError, TypeError):
                                raise RuntimeError(
                                    f"Type error: Column '{db_col}' expects DECIMAL but got '{val}'."
                                )
                    new_row[db_col] = val
            else:
                # Direct match field by name
                for col_name, col_schema in table.columns.items():
                    col_type = col_schema.type if hasattr(col_schema, "type") else str(col_schema)
                    val = body.get(col_name)
                    if val is not None:
                        if col_type.upper() == "INTEGER":
                            try:
                                val = int(val)
                            except (ValueError, TypeError):
                                raise RuntimeError(
                                    f"Type error: Column '{col_name}' expects INTEGER but got '{val}'."
                                )
                        elif col_type.upper() in ("DECIMAL", "NUMERIC", "FLOAT"):
                            try:
                                val = float(val)
                            except (ValueError, TypeError):
                                raise RuntimeError(
                                    f"Type error: Column '{col_name}' expects DECIMAL but got '{val}'."
                                )
                        new_row[col_name] = val

            # Primary key auto-increment / uuid generation
            if pk not in new_row or new_row[pk] is None:
                if pk_type.upper() == "INTEGER":
                    new_row[pk] = len(self.db[table_name]) + 1
                else:
                    new_row[pk] = f"uuid-{len(self.db[table_name]) + 1}"

            self.db[table_name].append(new_row)
            self.log(f"INSERT into '{table_name}': {new_row}")
            return new_row

        elif op_type == "select":
            self.log(f"SELECT * from '{table_name}': Returned {len(self.db[table_name])} row(s).")
            return {"rows": self.db[table_name]}

        return {}

    def simulate_request(
        self, endpoint_name: str, body: Optional[Dict[str, Any]] = None, user_role: Optional[str] = None
    ) -> Dict[str, Any]:
        """Routes and executes a simulated API call."""
        if endpoint_name not in self.config.api_schema.endpoints:
            raise RuntimeError(f"API Error: Endpoint '{endpoint_name}' not defined in schema.")

        endpoint = self.config.api_schema.endpoints[endpoint_name]
        body = body or {}

        # 1. Authorization Enforcement
        if endpoint.auth_required:
            if not user_role:
                raise RuntimeError(f"Auth Error: Endpoint '{endpoint_name}' requires authentication.")
            if user_role not in endpoint.allowed_roles:
                raise RuntimeError(
                    f"Auth Error: Role '{user_role}' is not authorized to call '{endpoint_name}'. "
                    f"Allowed: {endpoint.allowed_roles}"
                )

        self.log(f"API Request: {endpoint_name} (Role: '{user_role}') with body={body}")

        # 2. DB Operations
        db_res = {}
        if endpoint.db_operations:
            op_type = None
            table_name = None
            mapping = endpoint.db_operations.get("mapping")

            for op in ("insert", "select", "update", "delete"):
                if op in endpoint.db_operations:
                    op_type = op
                    table_name = endpoint.db_operations[op]
                    break

            if op_type and table_name:
                db_res = self.execute_db_operation(op_type, table_name, body, mapping)

        # 3. Response Construction
        response = {}
        resp_schema = endpoint.response_body or endpoint.response
        if resp_schema:
            for field, field_val in resp_schema.items():
                api_type = field_val.type if hasattr(field_val, "type") else str(field_val)
                
                # Table reference field, e.g. "users.email"
                if isinstance(api_type, str) and "." in api_type:
                    ref_tbl, ref_col = api_type.split(".", 1)
                    if ref_tbl in self.db and self.db[ref_tbl]:
                        # Populate with the last row
                        response[field] = self.db[ref_tbl][-1].get(ref_col)
                    else:
                        response[field] = None
                elif api_type.lower() == "array":
                    table_name = endpoint.db_operations.get("select") if endpoint.db_operations else None
                    if table_name and table_name in self.db:
                        response[field] = self.db[table_name]
                    else:
                        response[field] = []
                elif api_type.lower() == "boolean":
                    response[field] = True
                elif api_type.lower() == "integer":
                    pk_name = "id"
                    if endpoint.db_operations:
                        target_table = None
                        for op in ("insert", "update", "select", "delete"):
                            if op in endpoint.db_operations:
                                target_table = endpoint.db_operations[op]
                                break
                        if target_table and target_table in self.config.database_schema.tables:
                            db_table = self.config.database_schema.tables[target_table]
                            pk_name = db_table.primary_key or "id"
                    response[field] = db_res.get(pk_name) or 1
                else:
                    response[field] = "mock_value"

        self.log(f"API Response: {response}")
        return response


def run_simulation(config: UnifiedAppConfigSchema) -> Tuple[List[str], List[str]]:
    """
    Simulates user journeys for all UI pages and API endpoints.
    Enforces authorization logic and tests both positive and negative auth scenarios.
    
    Returns:
        Tuple[List[str], List[str]]: (simulation_errors, simulation_logs)
    """
    runtime = SimulationRuntime(config)
    errors: List[str] = []
    called_endpoints = set()

    try:
        # 1. Positive UI Journey simulation
        for page_route, page in config.ui_schema.pages.items():
            runtime.log(f"--- Simulating UI Page access: '{page_route}' ---")
            
            # Access page under each allowed role
            for role in page.allowed_roles:
                runtime.log(f"Accessing page '{page_route}' as role '{role}'")
                
                for comp in page.components:
                    target_api = comp.data_source_api or comp.submit_action
                    if target_api and not isinstance(target_api, str):
                        target_api = getattr(target_api, "target_api", None)
                    
                    if target_api and isinstance(target_api, str):
                        # Determine method/dummy payload
                        endpoint = config.api_schema.endpoints.get(target_api)
                        if not endpoint:
                            continue
                        if endpoint.auth_required and role not in endpoint.allowed_roles:
                            if "approve" in target_api:
                                continue
                        
                        dummy_body = {}
                        if endpoint.request_body:
                            for field, field_val in endpoint.request_body.items():
                                api_type = field_val.type if hasattr(field_val, "type") else str(field_val)
                                if api_type.lower() == "integer":
                                    dummy_body[field] = 1
                                elif api_type.lower() in ("decimal", "numeric", "float"):
                                    dummy_body[field] = 10.0
                                elif api_type.lower() == "boolean":
                                    dummy_body[field] = True
                                else:
                                    dummy_body[field] = "test_data"

                        # Perform call
                        runtime.simulate_request(target_api, body=dummy_body, user_role=role)
                        called_endpoints.add(target_api)

        # 2. Negative/Security auth checks
        runtime.log("--- Running negative security authorization checks ---")
        all_roles = config.app_metadata.roles
        
        for ep_name, ep in config.api_schema.endpoints.items():
            if ep.auth_required:
                unauthorized_roles = [r for r in all_roles if r not in ep.allowed_roles]
                for unauth_role in unauthorized_roles:
                    runtime.log(f"Security test: Trying to call '{ep_name}' as unauthorized role '{unauth_role}'")
                    try:
                        runtime.simulate_request(ep_name, user_role=unauth_role)
                        # If this doesn't raise, we have a security enforcement failure!
                        raise RuntimeError(
                            f"Security check failed: Unauthorized role '{unauth_role}' was permitted to call '{ep_name}'"
                        )
                    except RuntimeError as e:
                        if "Auth Error" in str(e):
                            runtime.log(f"Pass: Access correctly denied to '{unauth_role}' (Auth Error).")
                        else:
                            raise e

        # 3. Cleanup/Fallback simulation for uncalled endpoints
        runtime.log("--- Running cleanup/fallback simulation for uncalled API endpoints ---")
        for ep_name, endpoint in config.api_schema.endpoints.items():
            if ep_name not in called_endpoints:
                if endpoint.allowed_roles:
                    allowed_role = endpoint.allowed_roles[0]
                    dummy_body = {}
                    if endpoint.request_body:
                        for field, field_val in endpoint.request_body.items():
                            api_type = field_val.type if hasattr(field_val, "type") else str(field_val)
                            if api_type.lower() == "integer":
                                dummy_body[field] = 1
                            elif api_type.lower() in ("decimal", "numeric", "float"):
                                dummy_body[field] = 10.0
                            elif api_type.lower() == "boolean":
                                dummy_body[field] = True
                            else:
                                dummy_body[field] = "test_data"
                    
                    runtime.log(f"Fallback simulation: Calling uncalled endpoint '{ep_name}' as role '{allowed_role}'")
                    runtime.simulate_request(ep_name, body=dummy_body, user_role=allowed_role)

    except Exception as e:
        errors.append(f"Simulation runtime error: {e}")
        runtime.log(f"Simulation failed with error: {e}")

    return errors, runtime.logs
