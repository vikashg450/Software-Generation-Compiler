"""
High-fidelity mock LLM engine.
Provides structured JSON responses for different pipeline stages based on keywords
in the user prompts. Supports error injection and intelligent repairs based on error diagnostics.
"""

import json
import logging
from typing import Dict, Any, Set, Tuple

logger = logging.getLogger("MockLLM")


class MockLLM:
    """
    Simulates LLM responses for Intent Extraction, System Architect, Schema Generation,
    Refinement, and Repair stages. Integrates mock templates for 10 products and 10 edge cases.
    """

    def __init__(self, inject_errors: bool = True) -> None:
        self.inject_errors = inject_errors
        # Tracks which case IDs have had errors injected during this lifecycle
        self.injected_cases: Set[str] = set()
        # Initialize package repository
        self.packages = self._initialize_packages()

    def reset_state(self) -> None:
        """Resets the error injection tracking state."""
        self.injected_cases.clear()
        logger.info("MockLLM state reset.")

    def _initialize_packages(self) -> Dict[str, Dict[str, Any]]:
        """Initializes the mock packages dictionary with all 20 scenarios."""
        pkgs = {}

        # ----------------------------------------------------
        # Helper to create schema and its erroneous variant
        # ----------------------------------------------------
        def create_pkg(
            name: str,
            tables: Dict[str, Any],
            endpoints: Dict[str, Any],
            pages: Dict[str, Any],
            roles: list,
            error_msg: str,
            err_tables: Dict[str, Any] = None,
            err_endpoints: Dict[str, Any] = None,
            err_pages: Dict[str, Any] = None,
            err_roles: list = None,
            pricing: list = None,
        ) -> Dict[str, Any]:
            
            pricing_data = pricing or [
                {"name": "Free", "price": 0.0, "features": ["Basic usage"]},
                {"name": "Premium", "price": 19.99, "features": ["All features"]},
            ]

            ent_list = list(tables.keys())
            if len(ent_list) < 2:
                if "users" not in ent_list:
                    ent_list.append("users")
                else:
                    ent_list.append("items")

            intent = {
                "product_name": name,
                "features": [f"Manage {k}" for k in tables.keys()] + ["User Auth", "Dashboard"],
                "user_roles": roles,
                "pricing_plans": pricing_data,
                "core_operations": [f"CRUD {k}" for k in tables.keys()],
                "entities": ent_list,
                "status": "success",
                "questions": [],
            }

            architecture = {
                "database": {"tables": tables},
                "api": {"endpoints": endpoints},
                "ui": {"pages": pages},
                "auth": {
                    "roles": roles,
                    "permissions": {r: ["read", "write"] for r in roles},
                },
            }

            clean_schema = {
                "app_metadata": intent,
                "db": {"tables": tables},
                "api": {"endpoints": endpoints},
                "ui": {"pages": pages},
                "auth": {
                    "roles": roles,
                    "permissions": {r: ["read", "write"] for r in roles},
                },
            }

            err_schema = {
                "app_metadata": intent,
                "db": {"tables": err_tables if err_tables is not None else tables},
                "api": {"endpoints": err_endpoints if err_endpoints is not None else endpoints},
                "ui": {"pages": err_pages if err_pages is not None else pages},
                "auth": {
                    "roles": err_roles if err_roles is not None else roles,
                    "permissions": {r: ["read", "write"] for r in (roles if err_roles is None else err_roles)},
                },
            }

            return {
                "intent": intent,
                "architecture": architecture,
                "schema": clean_schema,
                "refined": clean_schema,
                "error_schema": err_schema,
                "error_message": error_msg,
                "corrected_schema": clean_schema,
            }

        # ----------------------------------------------------
        # 1. CRM
        # ----------------------------------------------------
        pkgs["crm"] = create_pkg(
            name="Customer Relationship Manager",
            tables={
                "users": {
                    "columns": {"id": "INTEGER", "name": "TEXT", "email": "TEXT", "role": "TEXT"},
                    "primary_key": "id",
                },
                "contacts": {
                    "columns": {"id": "INTEGER", "name": "TEXT", "email": "TEXT", "owner_id": "INTEGER"},
                    "primary_key": "id",
                    "foreign_keys": [{"column": "owner_id", "references": "users.id"}],
                },
            },
            endpoints={
                "GET /api/contacts": {
                    "auth_required": True,
                    "roles": ["sales_rep", "manager", "admin"],
                    "response": {"contacts": "array"},
                },
                "POST /api/contacts": {
                    "auth_required": True,
                    "roles": ["sales_rep", "manager", "admin"],
                    "request_body": {"name": "string", "email": "string", "owner_id": "integer"},
                    "response": {"success": "boolean"},
                    "db_operations": {
                        "insert": "contacts",
                        "mapping": {
                            "name": "request.name",
                            "email": "request.email",
                            "owner_id": "request.owner_id",
                        },
                    },
                },
            },
            pages={
                "/contacts": {
                    "route": "/contacts",
                    "allowed_roles": ["sales_rep", "manager", "admin"],
                    "components": [
                        {"type": "table", "data_source": "GET /api/contacts", "fields": ["id", "name", "email"]}
                    ],
                }
            },
            roles=["sales_rep", "manager", "admin"],
            error_msg="Validation failed: column 'user_id' in API response is not in table 'users'",
            # Inject error: API endpoint POST /api/contacts response references missing column 'user_id' in 'users'
            err_tables={
                "users": {
                    "columns": {"id": "INTEGER", "name": "TEXT", "email": "TEXT", "role": "TEXT"},
                    "primary_key": "id",
                },
                "contacts": {
                    "columns": {"id": "INTEGER", "name": "TEXT", "email": "TEXT", "owner_id": "INTEGER"},
                    "primary_key": "id",
                    "foreign_keys": [{"column": "owner_id", "references": "users.id"}],
                },
            },
            err_endpoints={
                "GET /api/contacts": {
                    "auth_required": True,
                    "roles": ["sales_rep", "manager", "admin"],
                    "response": {"contacts": "array", "user_id": "users.user_id"},  # missing column in users
                },
                "POST /api/contacts": {
                    "auth_required": True,
                    "roles": ["sales_rep", "manager", "admin"],
                    "request_body": {"name": "string", "email": "string", "owner_id": "integer"},
                    "response": {"success": "boolean"},
                    "db_operations": {
                        "insert": "contacts",
                        "mapping": {
                            "name": "request.name",
                            "email": "request.email",
                            "owner_id": "request.owner_id",
                        },
                    },
                },
            },
        )

        # ----------------------------------------------------
        # 2. E-commerce
        # ----------------------------------------------------
        pkgs["ecommerce"] = create_pkg(
            name="E-Commerce System",
            tables={
                "users": {"columns": {"id": "INTEGER", "username": "TEXT"}, "primary_key": "id"},
                "products": {"columns": {"id": "INTEGER", "name": "TEXT", "price": "DECIMAL"}, "primary_key": "id"},
            },
            endpoints={
                "GET /api/products": {
                    "auth_required": False,
                    "roles": ["buyer", "seller"],
                    "response": {"products": "array"},
                }
            },
            pages={
                "/products": {
                    "route": "/products",
                    "allowed_roles": ["buyer", "seller"],
                    "components": [{"type": "table", "data_source": "GET /api/products", "fields": ["id", "name"]}],
                }
            },
            roles=["buyer", "seller"],
            error_msg="Validation failed: UI page '/cart' references API endpoint 'GET /api/shopping_cart' which is not defined in the API schema",
            err_pages={
                "/products": {
                    "route": "/products",
                    "allowed_roles": ["buyer", "seller"],
                    "components": [{"type": "table", "data_source": "GET /api/products", "fields": ["id", "name"]}],
                },
                "/cart": {
                    "route": "/cart",
                    "allowed_roles": ["buyer"],
                    "components": [
                        {"type": "table", "data_source": "GET /api/shopping_cart"}  # undefined API
                    ],
                },
            },
        )

        # ----------------------------------------------------
        # 3. Inventory
        # ----------------------------------------------------
        pkgs["inventory"] = create_pkg(
            name="Inventory Stock Manager",
            tables={
                "suppliers": {"columns": {"id": "INTEGER", "name": "TEXT"}, "primary_key": "id"},
                "inventory_items": {
                    "columns": {"id": "INTEGER", "name": "TEXT", "supplier_id": "INTEGER"},
                    "primary_key": "id",
                    "foreign_keys": [{"column": "supplier_id", "references": "suppliers.id"}],
                },
            },
            endpoints={
                "GET /api/items": {
                    "auth_required": True,
                    "roles": ["clerk"],
                    "response": {"items": "array"},
                }
            },
            pages={
                "/items": {
                    "route": "/items",
                    "allowed_roles": ["clerk"],
                    "components": [{"type": "table", "data_source": "GET /api/items", "fields": ["name"]}],
                }
            },
            roles=["clerk"],
            error_msg="Validation failed: Foreign key in table 'inventory_items' references non-existent table 'suppliers'",
            err_tables={
                "inventory_items": {
                    "columns": {"id": "INTEGER", "name": "TEXT", "supplier_id": "INTEGER"},
                    "primary_key": "id",
                    # References suppliers, but we will omit suppliers table from db
                    "foreign_keys": [{"column": "supplier_id", "references": "suppliers.id"}],
                }
            },
        )

        # ----------------------------------------------------
        # 4. Blog
        # ----------------------------------------------------
        pkgs["blog"] = create_pkg(
            name="Blogging Platform",
            tables={
                "users": {"columns": {"id": "INTEGER", "name": "TEXT", "role": "TEXT"}, "primary_key": "id"},
                "posts": {"columns": {"id": "INTEGER", "title": "TEXT"}, "primary_key": "id"},
            },
            endpoints={
                "GET /api/posts": {
                    "auth_required": False,
                    "roles": ["author", "reader"],
                    "response": {"posts": "array"},
                }
            },
            pages={
                "/posts": {
                    "route": "/posts",
                    "allowed_roles": ["author", "reader"],
                    "components": [{"type": "list", "data_source": "GET /api/posts"}],
                }
            },
            roles=["author", "reader"],
            error_msg="Validation failed: API response references column 'role' in table 'users' which is missing",
            err_tables={
                "users": {
                    "columns": {"id": "INTEGER", "name": "TEXT"},  # role is missing
                    "primary_key": "id",
                },
                "posts": {"columns": {"id": "INTEGER", "title": "TEXT"}, "primary_key": "id"},
            },
            err_endpoints={
                "GET /api/posts": {
                    "auth_required": False,
                    "roles": ["author", "reader"],
                    "response": {"posts": "array", "author_role": "users.role"},  # References users.role
                }
            },
        )

        # ----------------------------------------------------
        # 5. LMS
        # ----------------------------------------------------
        pkgs["lms"] = create_pkg(
            name="Learning Management System",
            tables={"courses": {"columns": {"id": "INTEGER", "title": "TEXT"}, "primary_key": "id"}},
            endpoints={
                "GET /api/courses": {
                    "auth_required": True,
                    "roles": ["teacher", "student"],
                    "response": {"courses": "array"},
                }
            },
            pages={
                "/course-builder": {
                    "route": "/course-builder",
                    "allowed_roles": ["teacher"],
                    "components": [{"type": "form", "submit_action": "GET /api/courses"}],
                }
            },
            roles=["teacher", "student"],
            error_msg="Validation failed: UI page '/course-builder' references undefined role 'instructor'",
            err_pages={
                "/course-builder": {
                    "route": "/course-builder",
                    "allowed_roles": ["instructor"],  # 'instructor' is undefined role
                    "components": [{"type": "form", "submit_action": "GET /api/courses"}],
                }
            },
        )

        # ----------------------------------------------------
        # 6. Task Manager
        # ----------------------------------------------------
        pkgs["taskmanager"] = create_pkg(
            name="Task Manager Platform",
            tables={"tasks": {"columns": {"id": "INTEGER", "title": "TEXT", "assignee_id": "INTEGER"}, "primary_key": "id"}},
            endpoints={
                "POST /api/tasks": {
                    "auth_required": True,
                    "roles": ["member"],
                    "request_body": {"title": "string", "assignee_id": "integer"},
                    "response": {"success": "boolean"},
                    "db_operations": {
                        "insert": "tasks",
                        "mapping": {"title": "request.title", "assignee_id": "request.assignee_id"},
                    },
                }
            },
            pages={
                "/tasks": {
                    "route": "/tasks",
                    "allowed_roles": ["member"],
                    "components": [{"type": "form", "submit_action": "POST /api/tasks"}],
                }
            },
            roles=["member"],
            error_msg="Validation failed: API mapping references column 'assigned_user' which does not exist in table 'tasks'",
            err_endpoints={
                "POST /api/tasks": {
                    "auth_required": True,
                    "roles": ["member"],
                    "request_body": {"title": "string", "assignee_id": "integer"},
                    "response": {"success": "boolean"},
                    "db_operations": {
                        "insert": "tasks",
                        "mapping": {
                            "title": "request.title",
                            "assigned_user": "request.assignee_id",  # Invalid field name
                        },
                    },
                }
            },
        )

        # ----------------------------------------------------
        # 7. Event Planner
        # ----------------------------------------------------
        pkgs["eventplanner"] = create_pkg(
            name="Event Planner Hub",
            tables={"events": {"columns": {"id": "INTEGER", "title": "TEXT"}, "primary_key": "id"}},
            endpoints={
                "POST /api/create_event": {
                    "auth_required": True,
                    "roles": ["host"],
                    "request_body": {"title": "string"},
                    "response": {"id": "integer"},
                }
            },
            pages={
                "/events": {
                    "route": "/events",
                    "allowed_roles": ["host"],
                    "components": [{"type": "form", "submit_action": "POST /api/create_event"}],
                }
            },
            roles=["host", "guest"],
            error_msg="Validation failed: UI action references API endpoint 'POST /api/events' which is not defined in the API schema",
            err_pages={
                "/events": {
                    "route": "/events",
                    "allowed_roles": ["host"],
                    "components": [{"type": "form", "submit_action": "POST /api/events"}],  # missing POST /api/events
                }
            },
        )

        # ----------------------------------------------------
        # 8. Fitness Tracker
        # ----------------------------------------------------
        pkgs["fitnesstracker"] = create_pkg(
            name="Fitness Tracker App",
            tables={"workouts": {"columns": {"id": "INTEGER", "duration": "INTEGER"}, "primary_key": "id"}},
            endpoints={
                "POST /api/workouts": {
                    "auth_required": True,
                    "roles": ["user"],
                    "request_body": {"duration": "integer"},
                    "response": {"success": "boolean"},
                }
            },
            pages={
                "/workouts": {
                    "route": "/workouts",
                    "allowed_roles": ["user"],
                    "components": [{"type": "form", "submit_action": "POST /api/workouts"}],
                }
            },
            roles=["user"],
            error_msg="Validation failed: Type mismatch for field 'duration': API requests 'DATETIME' but DB column is 'INTEGER'",
            err_endpoints={
                "POST /api/workouts": {
                    "auth_required": True,
                    "roles": ["user"],
                    "request_body": {"duration": "string"},  # DATETIME string
                    "response": {"success": "boolean"},
                }
            },
        )

        # ----------------------------------------------------
        # 9. Expense Manager
        # ----------------------------------------------------
        pkgs["expensemanager"] = create_pkg(
            name="Corporate Expense Manager",
            tables={"expenses": {"columns": {"id": "INTEGER", "amount": "DECIMAL"}, "primary_key": "id"}},
            endpoints={
                "GET /api/expenses": {
                    "auth_required": True,
                    "roles": ["employee"],
                    "response": {"expenses": "array", "amount": "expenses.amount"},  # DECIMAL
                }
            },
            pages={
                "/expenses": {
                    "route": "/expenses",
                    "allowed_roles": ["employee"],
                    "components": [{"type": "table", "data_source": "GET /api/expenses"}],
                }
            },
            roles=["employee"],
            error_msg="Validation failed: Type mismatch for field 'amount': API response expects 'string' but DB column is 'DECIMAL'",
            err_endpoints={
                "GET /api/expenses": {
                    "auth_required": True,
                    "roles": ["employee"],
                    "response": {"expenses": "array", "amount": "string"},  # string mismatch
                }
            },
        )

        # ----------------------------------------------------
        # 10. Booking System
        # ----------------------------------------------------
        pkgs["bookingsystem"] = create_pkg(
            name="Room Booking System",
            tables={"bookings": {"columns": {"id": "INTEGER", "room": "TEXT"}, "primary_key": "id"}},
            endpoints={
                "POST /api/cancel_booking": {
                    "auth_required": True,
                    "roles": ["customer", "admin"],
                    "request_body": {"id": "integer"},
                    "response": {"success": "boolean"},
                }
            },
            pages={
                "/bookings": {
                    "route": "/bookings",
                    "allowed_roles": ["customer"],
                    "components": [{"type": "button", "action": "POST /api/cancel_booking"}],
                }
            },
            roles=["customer", "admin"],
            error_msg="Validation failed: UI page accessibility mismatch: Page '/bookings' allows role 'customer' to perform action 'POST /api/cancel_booking' but Auth schema restricts action to 'admin'",
            err_endpoints={
                "POST /api/cancel_booking": {
                    "auth_required": True,
                    "roles": ["admin"],  # Only admin can cancel in API
                    "request_body": {"id": "integer"},
                    "response": {"success": "boolean"},
                }
            },
        )

        # ----------------------------------------------------
        # 11. Admin Forbidden Login (Edge Case)
        # ----------------------------------------------------
        pkgs["admin_forbidden_login"] = create_pkg(
            name="System Admin Portal",
            tables={"logs": {"columns": {"id": "INTEGER", "event": "TEXT"}, "primary_key": "id"}},
            endpoints={
                "POST /api/login": {
                    "auth_required": False,
                    "roles": ["user", "admin"],  # Correct permits both
                    "request_body": {"user": "string"},
                    "response": {"token": "string"},
                }
            },
            pages={
                "/admin-dashboard": {
                    "route": "/admin-dashboard",
                    "allowed_roles": ["admin"],
                    "components": [{"type": "table", "data_source": "POST /api/login"}],
                }
            },
            roles=["user", "admin"],
            error_msg="Validation failed: Role 'admin' is allowed to access page '/admin-dashboard' but is not permitted to perform login action",
            err_endpoints={
                "POST /api/login": {
                    "auth_required": False,
                    "roles": ["user"],  # Error: Admin cannot perform login API
                    "request_body": {"user": "string"},
                    "response": {"token": "string"},
                }
            },
        )

        # ----------------------------------------------------
        # 12. Conflicting Roles (Edge Case)
        # ----------------------------------------------------
        pkgs["conflicting_roles"] = create_pkg(
            name="Conflicting Permissions Portal",
            tables={"records": {"columns": {"id": "INTEGER", "data": "TEXT"}, "primary_key": "id"}},
            endpoints={
                "POST /api/approve": {
                    "auth_required": True,
                    "roles": ["admin"],  # Admin has approve permission
                    "response": {"success": "boolean"},
                }
            },
            pages={
                "/edit": {
                    "route": "/edit",
                    "allowed_roles": ["user"],
                    "components": [{"type": "button", "action": "POST /api/approve"}],
                }
            },
            roles=["user", "admin"],
            error_msg="Validation failed: Permission dependency cycle: 'edit_records' requires role 'admin' approval, but 'admin' lacks 'approve' permission",
            err_endpoints={
                "POST /api/approve": {
                    "auth_required": True,
                    "roles": ["user"],  # Error: admin lacks permission to approve
                    "response": {"success": "boolean"},
                }
            },
        )

        # ----------------------------------------------------
        # 13. Negative Pricing (Edge Case)
        # ----------------------------------------------------
        pkgs["negative_pricing"] = create_pkg(
            name="Subscription Billing System",
            tables={"bills": {"columns": {"id": "INTEGER", "amount": "DECIMAL"}, "primary_key": "id"}},
            endpoints={"GET /api/bills": {"auth_required": True, "roles": ["user"], "response": {"bills": "array"}}},
            pages={
                "/billing": {
                    "route": "/billing",
                    "allowed_roles": ["user"],
                    "components": [{"type": "table", "data_source": "GET /api/bills"}],
                }
            },
            roles=["user"],
            error_msg="Validation failed: pricing.monthly_rate cannot be negative: -10.0",
            pricing=[{"name": "Standard", "price": 10.0, "features": ["Full usage"]}],
            # Erroneous version: Pricing rate is -10.0
            err_roles=["user"],
            err_tables={"bills": {"columns": {"id": "INTEGER", "amount": "DECIMAL"}, "primary_key": "id"}},
        )
        pkgs["negative_pricing"]["intent"]["pricing_plans"] = [{"name": "Standard", "price": 10.0}]
        pkgs["negative_pricing"]["schema"]["pricing"] = {"monthly_rate": 10.0}
        pkgs["negative_pricing"]["corrected_schema"]["pricing"] = {"monthly_rate": 10.0}
        # Override error package intent pricing
        pkgs["negative_pricing"]["error_schema"] = {
            "app_metadata": pkgs["negative_pricing"]["intent"],
            "db": {"tables": {"bills": {"columns": {"id": "INTEGER", "amount": "DECIMAL"}, "primary_key": "id"}}},
            "api": {"endpoints": {"GET /api/bills": {"auth_required": True, "roles": ["user"], "response": {"bills": "array"}}}},
            "ui": {
                "pages": {
                    "/billing": {
                        "route": "/billing",
                        "allowed_roles": ["user"],
                        "components": [{"type": "table", "data_source": "GET /api/bills"}],
                    }
                }
            },
            "auth": {"roles": ["user"], "permissions": {"user": ["read", "write"]}},
            "pricing": {"monthly_rate": -10.0},  # Trigger negative rate error
        }

        # ----------------------------------------------------
        # 14. No Database (Edge Case)
        # ----------------------------------------------------
        pkgs["no_database"] = create_pkg(
            name="In-Memory Streaming Dashboard",
            tables={"telemetry": {"columns": {"id": "INTEGER", "value": "TEXT"}, "primary_key": "id"}},
            endpoints={
                "GET /api/stream": {
                    "auth_required": False,
                    "roles": ["viewer"],
                    "response": {"data": "string"},
                }
            },
            pages={
                "/dashboard": {
                    "route": "/dashboard",
                    "allowed_roles": ["viewer"],
                    "components": [{"type": "stream", "data_source": "GET /api/stream"}],
                }
            },
            roles=["viewer"],
            error_msg="Validation failed: API endpoints require a DB schema for persistence, but DB table list is empty",
            err_tables={},  # Empty DB schema
        )

        # ----------------------------------------------------
        # 15. API Referencing Missing DB (Edge Case)
        # ----------------------------------------------------
        pkgs["api_referencing_missing_db"] = create_pkg(
            name="Legacy DB Adapter",
            tables={"orders": {"columns": {"id": "INTEGER", "status": "TEXT"}, "primary_key": "id"}},
            endpoints={
                "GET /api/orders": {
                    "auth_required": True,
                    "roles": ["customer"],
                    "response": {"orders": "array"},
                    "db_operations": {"select": "orders"},
                }
            },
            pages={
                "/orders": {
                    "route": "/orders",
                    "allowed_roles": ["customer"],
                    "components": [{"type": "table", "data_source": "GET /api/orders"}],
                }
            },
            roles=["customer"],
            error_msg="Validation failed: API endpoint 'GET /api/orders' references non-existent DB table 'orders'",
            err_tables={"purchases": {"columns": {"id": "INTEGER", "status": "TEXT"}, "primary_key": "id"}},  # Renamed table
        )

        # ----------------------------------------------------
        # 16. Incorrect Data Type (Edge Case)
        # ----------------------------------------------------
        pkgs["incorrect_data_type"] = create_pkg(
            name="User Registration System",
            tables={"users": {"columns": {"id": "INTEGER", "email": "TEXT"}, "primary_key": "id"}},
            endpoints={
                "POST /api/register": {
                    "auth_required": False,
                    "roles": ["guest"],
                    "request_body": {"email": "string"},
                    "response": {"success": "boolean"},
                }
            },
            pages={
                "/register": {
                    "route": "/register",
                    "allowed_roles": ["guest"],
                    "components": [{"type": "form", "submit_action": "POST /api/register"}],
                }
            },
            roles=["guest"],
            error_msg="Validation failed: DB field 'email' type 'TEXT' does not match API body field 'email' expected type 'INTEGER'",
            err_endpoints={
                "POST /api/register": {
                    "auth_required": False,
                    "roles": ["guest"],
                    "request_body": {"email": "integer"},  # Type mismatch
                    "response": {"success": "boolean"},
                }
            },
        )

        # ----------------------------------------------------
        # 17. Empty Intent (Edge Case)
        # ----------------------------------------------------
        pkgs["empty_intent"] = create_pkg(
            name="No-Op Daemon Application",
            tables={"status": {"columns": {"id": "INTEGER", "msg": "TEXT"}, "primary_key": "id"}},
            endpoints={
                "GET /api/status": {
                    "auth_required": False,
                    "roles": ["guest"],
                    "response": {"msg": "string"},
                }
            },
            pages={
                "/home": {
                    "route": "/home",
                    "allowed_roles": ["guest"],
                    "components": [{"type": "text", "data_source": "GET /api/status"}],
                }
            },
            roles=["guest"],
            error_msg="Validation failed: Application schema must contain at least one UI page and one API endpoint",
            # Erroneous schema is empty
            err_tables={},
            err_endpoints={},
            err_pages={},
            err_roles=[],
        )

        # ----------------------------------------------------
        # 18. Massive Scale (Edge Case)
        # ----------------------------------------------------
        pkgs["massive_scale"] = create_pkg(
            name="Enterprise Multi-tenant Platform",
            tables={"data": {"columns": {"id": "INTEGER", "payload": "TEXT"}, "primary_key": "id"}},
            endpoints={
                "GET /api/data": {"auth_required": True, "roles": ["operator"], "response": {"data": "array"}}
            },
            pages={
                "/dashboard": {
                    "route": "/dashboard",
                    "allowed_roles": ["operator"],
                    "components": [{"type": "grid", "data_source": "GET /api/data"}],
                }
            },
            roles=["operator"],
            error_msg="Validation failed: UI page limit exceeded (max 100 pages for this tier)",
            # Erroneous page definition simulates excessive routing paths
            err_pages={f"/page-{i}": {"route": f"/page-{i}", "allowed_roles": ["operator"], "components": []} for i in range(105)},
        )

        # ----------------------------------------------------
        # 19. Ambiguous Flow (Edge Case)
        # ----------------------------------------------------
        pkgs["ambiguous_flow"] = create_pkg(
            name="E-Commerce Checkout Pipeline",
            tables={"transactions": {"columns": {"id": "INTEGER", "total": "DECIMAL"}, "primary_key": "id"}},
            endpoints={
                "POST /api/pay": {
                    "auth_required": True,
                    "roles": ["buyer"],
                    "response": {"redirect_url": "string"},
                }
            },
            pages={
                "/checkout": {
                    "route": "/checkout",
                    "allowed_roles": ["buyer"],
                    "components": [{"type": "button", "action": "POST /api/pay"}],
                },
                "/login": {
                    "route": "/login",
                    "allowed_roles": ["buyer", "guest"],
                    "components": [],
                    "post_login_redirect": "/checkout",
                },
            },
            roles=["buyer", "guest"],
            error_msg="Validation failed: Circular routing detected: /checkout -> /login -> /checkout",
            # Erroneous page loop
            err_pages={
                "/checkout": {
                    "route": "/checkout",
                    "allowed_roles": ["buyer"],
                    "components": [{"type": "button", "action": "POST /api/pay"}],
                    "post_checkout_redirect": "/login",
                },
                "/login": {
                    "route": "/login",
                    "allowed_roles": ["buyer", "guest"],
                    "components": [],
                    "post_login_redirect": "/checkout",  # Circle: checkout -> login -> checkout
                },
            },
        )

        # ----------------------------------------------------
        # 20. Gated Read (Edge Case)
        # ----------------------------------------------------
        pkgs["gated_read"] = create_pkg(
            name="Premium News Publisher",
            tables={"articles": {"columns": {"id": "INTEGER", "premium": "BOOLEAN"}, "primary_key": "id"}},
            endpoints={
                "GET /api/analytics": {
                    "auth_required": True,
                    "roles": ["premium"],  # Restrict to premium in API
                    "response": {"analytics": "array"},
                }
            },
            pages={
                "/premium-analytics": {
                    "route": "/premium-analytics",
                    "allowed_roles": ["premium"],  # Correctly restricts page to premium
                    "components": [{"type": "chart", "data_source": "GET /api/analytics"}],
                }
            },
            roles=["free", "premium"],
            error_msg="Validation failed: UI page '/premium-analytics' is accessible to 'free' users, but it calls API endpoint 'GET /api/analytics' which requires 'premium' role",
            err_pages={
                "/premium-analytics": {
                    "route": "/premium-analytics",
                    "allowed_roles": ["free", "premium"],  # Error: exposes page to free users
                    "components": [{"type": "chart", "data_source": "GET /api/analytics"}],
                }
            },
        )

        return pkgs

    def _detect_case(self, prompt: str) -> str:
        """Determines the appropriate package case based on keywords in the prompt."""
        prompt_lower = prompt.lower()

        # 1. Check unique routes, tables, or fields that identify the context (runs across all pipeline stages)
        if "/admin-dashboard" in prompt_lower or "admin_forbidden_login" in prompt_lower:
            return "admin_forbidden_login"
        if "/edit" in prompt_lower or "edit_records" in prompt_lower or "conflicting_roles" in prompt_lower:
            return "conflicting_roles"
        if "/billing" in prompt_lower or "billing" in prompt_lower or "bills" in prompt_lower or "negative_pricing" in prompt_lower:
            return "negative_pricing"
        if "telemetry" in prompt_lower or "stream" in prompt_lower or "no_database" in prompt_lower:
            return "no_database"
        if "/orders" in prompt_lower or "purchases" in prompt_lower or "api_referencing_missing_db" in prompt_lower:
            return "api_referencing_missing_db"
        if "/register" in prompt_lower or "register" in prompt_lower or "incorrect_data_type" in prompt_lower:
            return "incorrect_data_type"
        if "/home" in prompt_lower or "empty_intent" in prompt_lower:
            return "empty_intent"
        if "page-1" in prompt_lower or "massive_scale" in prompt_lower:
            return "massive_scale"
        if "/checkout" in prompt_lower or "checkout pipeline" in prompt_lower or "ambiguous_flow" in prompt_lower:
            return "ambiguous_flow"
        if "/premium-analytics" in prompt_lower or "premium-analytics" in prompt_lower or "gated_read" in prompt_lower:
            return "gated_read"

        if "/contacts" in prompt_lower or "contacts" in prompt_lower:
            return "crm"
        if "/cart" in prompt_lower or "shopping_cart" in prompt_lower or "products" in prompt_lower:
            return "ecommerce"
        if "/items" in prompt_lower or "suppliers" in prompt_lower or "inventory_items" in prompt_lower:
            return "inventory"
        if "/posts" in prompt_lower or "posts" in prompt_lower or "blogging" in prompt_lower:
            return "blog"
        if "/course-builder" in prompt_lower or "course-builder" in prompt_lower or "courses" in prompt_lower:
            return "lms"
        if "/tasks" in prompt_lower or "tasks" in prompt_lower or "assignee_id" in prompt_lower:
            return "taskmanager"
        if "/events" in prompt_lower or "events" in prompt_lower or "rsvp" in prompt_lower:
            return "eventplanner"
        if "/workouts" in prompt_lower or "workouts" in prompt_lower:
            return "fitnesstracker"
        if "/expenses" in prompt_lower or "expenses" in prompt_lower or "expense" in prompt_lower:
            return "expensemanager"
        if "/bookings" in prompt_lower or "bookings" in prompt_lower or "cancel_booking" in prompt_lower:
            return "bookingsystem"

        # 2. First, check unique product/application names that appear in intermediate JSON configurations
        if "system admin portal" in prompt_lower:
            return "admin_forbidden_login"
        if "conflicting permissions" in prompt_lower:
            return "conflicting_roles"
        if "subscription billing" in prompt_lower:
            return "negative_pricing"
        if "in-memory streaming" in prompt_lower:
            return "no_database"
        if "legacy db adapter" in prompt_lower:
            return "api_referencing_missing_db"
        if "user registration" in prompt_lower:
            return "incorrect_data_type"
        if "no-op daemon" in prompt_lower:
            return "empty_intent"
        if "enterprise multi-tenant" in prompt_lower:
            return "massive_scale"
        if "e-commerce checkout" in prompt_lower:
            return "ambiguous_flow"
        if "premium news" in prompt_lower:
            return "gated_read"

        if "customer relationship" in prompt_lower:
            return "crm"
        if "e-commerce system" in prompt_lower:
            return "ecommerce"
        if "inventory stock" in prompt_lower:
            return "inventory"
        if "blogging platform" in prompt_lower:
            return "blog"
        if "learning management" in prompt_lower:
            return "lms"
        if "task manager platform" in prompt_lower:
            return "taskmanager"
        if "event planner hub" in prompt_lower:
            return "eventplanner"
        if "fitness tracker" in prompt_lower:
            return "fitnesstracker"
        if "corporate expense" in prompt_lower:
            return "expensemanager"
        if "room booking" in prompt_lower:
            return "bookingsystem"

        # 3. Check for validation/repair error strings to route correctly during repair loops
        if "permission dependency cycle" in prompt_lower:
            return "conflicting_roles"
        if "pricing.monthly_rate cannot be negative" in prompt_lower:
            return "negative_pricing"
        if "api endpoints require a db schema for persistence" in prompt_lower:
            return "no_database"
        if "references non-existent db table" in prompt_lower:
            return "api_referencing_missing_db"
        if "does not match api body field" in prompt_lower:
            return "incorrect_data_type"
        if "must contain at least one ui page and one api endpoint" in prompt_lower:
            return "empty_intent"
        if "ui page limit exceeded" in prompt_lower:
            return "massive_scale"
        if "circular routing detected" in prompt_lower:
            return "ambiguous_flow"
        if "is accessible to 'free' users" in prompt_lower:
            return "gated_read"
        if "login action" in prompt_lower:
            return "admin_forbidden_login"

        # 4. Fallback to raw keywords for the initial prompt (Stage 1)
        if "admins are not allowed to log in" in prompt_lower or "admin forbidden login" in prompt_lower:
            return "admin_forbidden_login"
        if "conflicting roles" in prompt_lower or "circular permissions" in prompt_lower:
            return "conflicting_roles"
        if "negative pricing" in prompt_lower or "pricing is negative" in prompt_lower or "-10" in prompt_lower:
            return "negative_pricing"
        if "no database" in prompt_lower or "no db tables" in prompt_lower or "does not persist data" in prompt_lower:
            return "no_database"
        if "api referencing missing db" in prompt_lower or "missing db table" in prompt_lower or "missing table" in prompt_lower:
            return "api_referencing_missing_db"
        if "incorrect data type" in prompt_lower or "type mismatch" in prompt_lower:
            return "incorrect_data_type"
        if "empty intent" in prompt_lower or "do nothing" in prompt_lower or "do absolutely nothing" in prompt_lower:
            return "empty_intent"
        if "massive scale" in prompt_lower or "thousands of roles" in prompt_lower:
            return "massive_scale"
        if "ambiguous flow" in prompt_lower or "loop back" in prompt_lower or "circular routing" in prompt_lower:
            return "ambiguous_flow"
        if "gated read" in prompt_lower or "premium content" in prompt_lower or "free users can access analytics" in prompt_lower:
            return "gated_read"

        if "crm" in prompt_lower or "customer relationship" in prompt_lower:
            return "crm"
        if "e-commerce" in prompt_lower or "ecommerce" in prompt_lower or "shopping" in prompt_lower or "cart" in prompt_lower:
            return "ecommerce"
        if "inventory" in prompt_lower or "stock" in prompt_lower:
            return "inventory"
        if "blog" in prompt_lower or "posts" in prompt_lower:
            return "blog"
        if "lms" in prompt_lower or "course" in prompt_lower or "learning" in prompt_lower:
            return "lms"
        if "task manager" in prompt_lower or "todo" in prompt_lower or "tasks" in prompt_lower:
            return "taskmanager"
        if "event planner" in prompt_lower or "event" in prompt_lower or "rsvp" in prompt_lower:
            return "eventplanner"
        if "fitness" in prompt_lower or "workout" in prompt_lower:
            return "fitnesstracker"
        if "expense" in prompt_lower or "budget" in prompt_lower:
            return "expensemanager"
        if "booking" in prompt_lower or "room" in prompt_lower or "reservation" in prompt_lower:
            return "bookingsystem"

        # Fallback to CRM
        return "crm"

    def generate_response(self, prompt: str, stage: str = "general") -> str:
        """
        Generates mock LLM output for the prompt and stage.
        Simulates error injection and repair loops.
        """
        # 1. Detect Case
        case_id = self._detect_case(prompt)
        pkg = self.packages[case_id]
        logger.info(f"MockLLM detected case: '{case_id}' for stage: '{stage}'")

        # 2. Check if this is a repair or error-handling context
        is_repair = (
            "validation failed" in prompt.lower()
            or "error" in prompt.lower()
            or "repair" in prompt.lower()
            or stage.lower() in ("repair", "refinement_repair")
        )

        if is_repair:
            # Look for matching error message in prompt to be high-fidelity
            for cid, candidate_pkg in self.packages.items():
                if candidate_pkg["error_message"].lower() in prompt.lower():
                    logger.info(f"MockLLM: Found matching error in prompt. Repairing '{cid}'.")
                    self.injected_cases.discard(cid)  # Mark as resolved
                    return json.dumps(candidate_pkg["corrected_schema"], indent=2)

            # Fallback repair behavior for the detected case
            logger.info(f"MockLLM: Repairing detected case '{case_id}'.")
            self.injected_cases.discard(case_id)
            return json.dumps(pkg["corrected_schema"], indent=2)

        # 3. Handle specific stages
        stage_norm = stage.lower()
        if stage_norm in ("intent", "intent_extraction", "intent extraction"):
            return json.dumps(pkg["intent"], indent=2)

        elif stage_norm in ("architect", "system_architect", "system architect"):
            return json.dumps(pkg["architecture"], indent=2)

        elif stage_norm in ("schema", "schema_generation", "schema generation"):
            # Inject error if first request and error injection mode is active
            if self.inject_errors and case_id not in self.injected_cases:
                logger.warning(f"MockLLM: Injecting error into '{case_id}' schema.")
                self.injected_cases.add(case_id)
                return json.dumps(pkg["error_schema"], indent=2)
            else:
                return json.dumps(pkg["schema"], indent=2)

        elif stage_norm in ("refinement", "align", "alignment"):
            # If we injected an error and it hasn't been repaired yet, we still return the erroneous schema
            if self.inject_errors and case_id in self.injected_cases:
                return json.dumps(pkg["error_schema"], indent=2)
            return json.dumps(pkg["refined"], indent=2)

        # General Fallback
        return json.dumps(pkg["schema"], indent=2)
