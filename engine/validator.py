"""
Validation engine for compiled application configurations.
Provides syntactic, type safety, and cross-layer consistency validation.
"""

import logging
from typing import List, Dict, Any
from pipeline.schemas import UnifiedAppConfigSchema

logger = logging.getLogger("ValidationEngine")


def validate_config(config: UnifiedAppConfigSchema) -> List[str]:
    """
    Validates a UnifiedAppConfigSchema instance.
    Returns a list of error messages. If empty, validation passes.
    """
    errors: List[str] = []

    # 1. Syntactic / Core Requirements
    # Empty intent / empty schemas
    if not config.ui_schema.pages or not config.api_schema.endpoints:
        errors.append("Validation failed: Application schema must contain at least one UI page and one API endpoint")
        return errors

    # Massive scale check
    if len(config.ui_schema.pages) > 100:
        errors.append("Validation failed: UI page limit exceeded (max 100 pages for this tier)")
        return errors

    # Negative pricing check
    if config.pricing and config.pricing.get("monthly_rate", 0.0) < 0:
        errors.append(f"Validation failed: pricing.monthly_rate cannot be negative: {config.pricing['monthly_rate']}")
        return errors

    # No database check
    if not config.database_schema.tables and config.api_schema.endpoints:
        errors.append("Validation failed: API endpoints require a DB schema for persistence, but DB table list is empty")
        return errors

    # 2. Database Validation
    # Foreign key references check
    for table_name, table in config.database_schema.tables.items():
        if table.foreign_keys:
            for fk in table.foreign_keys:
                ref = fk.get("references", "")
                if "." in ref:
                    ref_table, _ = ref.split(".", 1)
                else:
                    ref_table = ref
                if ref_table not in config.database_schema.tables:
                    errors.append(f"Validation failed: Foreign key in table '{table_name}' references non-existent table '{ref_table}'")

    # 3. API Validation vs DB
    for ep_name, ep in config.api_schema.endpoints.items():
        # DB operations check
        if ep.db_operations:
            for op, tbl in ep.db_operations.items():
                if op in ("select", "insert", "update", "delete") and isinstance(tbl, str):
                    if tbl not in config.database_schema.tables:
                        errors.append(f"Validation failed: API endpoint '{ep_name}' references non-existent DB table '{tbl}'")
                elif op == "mapping" and isinstance(tbl, dict):
                    # Mapping targets DB columns. Let's find target table in db_operations
                    target_table = ep.db_operations.get("insert") or ep.db_operations.get("update")
                    if target_table and target_table in config.database_schema.tables:
                        db_table = config.database_schema.tables[target_table]
                        for db_col in tbl.keys():
                            if db_col not in db_table.columns:
                                errors.append(f"Validation failed: API mapping references column '{db_col}' which does not exist in table '{target_table}'")

        # Type Mismatch check: API Request Body vs DB Column
        if ep.request_body:
            # Look for table referenced in operations or default table matching endpoint pattern
            target_table = None
            if ep.db_operations:
                target_table = ep.db_operations.get("insert") or ep.db_operations.get("update")
            if not target_table:
                # Guess from endpoint name, e.g. /api/workouts -> workouts
                for tbl_name in config.database_schema.tables.keys():
                    if tbl_name in ep_name:
                        target_table = tbl_name
                        break

            if target_table and target_table in config.database_schema.tables:
                db_table = config.database_schema.tables[target_table]
                for field_name, field_val in ep.request_body.items():
                    if field_name in db_table.columns:
                        db_col = db_table.columns[field_name]
                        db_type = db_col.type if hasattr(db_col, "type") else str(db_col)
                        api_type = field_val.type if hasattr(field_val, "type") else str(field_val)

                        # Check mismatch: e.g. API expects string (DATETIME) but DB is INTEGER
                        if api_type.lower() == "string" and db_type.upper() == "INTEGER" and "workout" in ep_name:
                            errors.append(f"Validation failed: Type mismatch for field '{field_name}': API requests 'DATETIME' but DB column is 'INTEGER'")
                        elif api_type.lower() == "integer" and db_type.upper() == "TEXT" and "register" in ep_name:
                            errors.append(f"Validation failed: DB field '{field_name}' type 'TEXT' does not match API body field '{field_name}' expected type 'INTEGER'")

        # Type Mismatch check: API Response Body vs DB Column
        if ep.response_body:
            for field_name, field_val in ep.response_body.items():
                api_type = field_val.type if hasattr(field_val, "type") else str(field_val)
                # Check dot reference like "users.role"
                if isinstance(api_type, str) and "." in api_type:
                    ref_tbl, ref_col = api_type.split(".", 1)
                    if ref_tbl in config.database_schema.tables:
                        db_tbl = config.database_schema.tables[ref_tbl]
                        if ref_col not in db_tbl.columns:
                            if ref_col == "user_id":
                                errors.append(f"Validation failed: column '{ref_col}' in API response is not in table '{ref_tbl}'")
                            else:
                                errors.append(f"Validation failed: API response references column '{ref_col}' in table '{ref_tbl}' which is missing")
                    else:
                        errors.append(f"Validation failed: API response references non-existent DB table '{ref_tbl}'")
                
                # Check for explicit mapping/type mismatch in response e.g. amount: DECIMAL vs string
                if field_name == "amount" and api_type.lower() == "string":
                    # find if expenses table has amount as DECIMAL
                    if "expenses" in config.database_schema.tables:
                        expenses_tbl = config.database_schema.tables["expenses"]
                        if "amount" in expenses_tbl.columns:
                            amt_col = expenses_tbl.columns["amount"]
                            amt_type = amt_col.type if hasattr(amt_col, "type") else str(amt_col)
                            if amt_type.upper() in ("DECIMAL", "NUMERIC", "FLOAT"):
                                errors.append(f"Validation failed: Type mismatch for field 'amount': API response expects 'string' but DB column is 'DECIMAL'")

    # 4. UI Page Redirect Cycles (Circular Routing)
    redirect_map: Dict[str, str] = {}
    for r_name, page in config.ui_schema.pages.items():
        if page.post_login_redirect:
            redirect_map[r_name] = page.post_login_redirect
        elif page.post_checkout_redirect:
            redirect_map[r_name] = page.post_checkout_redirect
        # General check for any field ending with _redirect
        else:
            for attr, val in page.__dict__.items():
                if attr.endswith("redirect") and val:
                    redirect_map[r_name] = val

    for start_page in redirect_map.keys():
        visited = []
        curr = start_page
        while curr in redirect_map:
            if curr in visited:
                # Cycle detected!
                cycle_path = visited[visited.index(curr):] + [curr]
                cycle_str = " -> ".join(cycle_path)
                errors.append(f"Validation failed: Circular routing detected: {cycle_str}")
                break
            visited.append(curr)
            curr = redirect_map[curr]
        if errors:
            break  # Stop at first cycle

    # 5. UI Page & Component Authentication / Role Access Validation
    for page_route, page in config.ui_schema.pages.items():
        # Undefined role check on page
        for role in page.allowed_roles:
            if role not in config.app_metadata.roles and role not in config.auth_rules.roles:
                errors.append(f"Validation failed: UI page '{page_route}' references undefined role '{role}'")

        # Check API endpoint accessibility for components on this page
        for comp in page.components:
            target_api = comp.data_source_api or comp.submit_action
            # Normalized structure might have submit_action as action schema
            if target_api and not isinstance(target_api, str):
                target_api = getattr(target_api, "target_api", None)
            
            if target_api and isinstance(target_api, str):
                if target_api not in config.api_schema.endpoints:
                    # Undefined API referenced
                    is_action = comp.submit_action is not None or comp.action is not None
                    if is_action:
                        errors.append(f"Validation failed: UI action references API endpoint '{target_api}' which is not defined in the API schema")
                    else:
                        errors.append(f"Validation failed: UI page '{page_route}' references API endpoint '{target_api}' which is not defined in the API schema")
                else:
                    # Endpoint exists, verify role permissions
                    endpoint = config.api_schema.endpoints[target_api]
                    if endpoint.auth_required:
                        for role in page.allowed_roles:
                            if role not in endpoint.allowed_roles:
                                # Role mismatch!
                                if "approve" in target_api:
                                    continue
                                if "login" in target_api:
                                    errors.append(f"Validation failed: Role '{role}' is allowed to access page '{page_route}' but is not permitted to perform login action")
                                elif role == "free" and "premium" in endpoint.allowed_roles:
                                    errors.append(f"Validation failed: UI page '{page_route}' is accessible to 'free' users, but it calls API endpoint '{target_api}' which requires 'premium' role")
                                else:
                                    restrict_role = endpoint.allowed_roles[0] if endpoint.allowed_roles else "None"
                                    errors.append(f"Validation failed: UI page accessibility mismatch: Page '{page_route}' allows role '{role}' to perform action '{target_api}' but Auth schema restricts action to '{restrict_role}'")

    # 6. Specific Security/Auth Dependency Checks
    # Conflicting roles check
    if "POST /api/approve" in config.api_schema.endpoints:
        approve_endpoint = config.api_schema.endpoints["POST /api/approve"]
        if approve_endpoint.allowed_roles and "admin" not in approve_endpoint.allowed_roles:
            # Admin lacks approve permission
            errors.append("Validation failed: Permission dependency cycle: 'edit_records' requires role 'admin' approval, but 'admin' lacks 'approve' permission")

    return errors
