"""
Evaluation dataset of 20 prompts for testing the software compiler pipeline.
Contains 10 standard product prompts and 10 advanced edge cases.
"""

from typing import List, Dict, Any

DATASET: List[Dict[str, Any]] = [
    # ----------------------------------------------------
    # 10 Standard Product Prompts
    # ----------------------------------------------------
    {
        "id": "crm",
        "type": "product",
        "name": "Customer Relationship Manager",
        "prompt": "Create a CRM application for sales reps, managers, and admins to manage contacts and users. Include CRUD contacts with contact owner references.",
    },
    {
        "id": "ecommerce",
        "type": "product",
        "name": "E-Commerce System",
        "prompt": "Design an e-commerce platform for buyers and sellers to list and browse products. Include a public endpoint to view products.",
    },
    {
        "id": "inventory",
        "type": "product",
        "name": "Inventory Stock Manager",
        "prompt": "Create an inventory stock manager app where clerks can manage items and track suppliers with foreign key references.",
    },
    {
        "id": "blog",
        "type": "product",
        "name": "Blogging Platform",
        "prompt": "Build a blogging platform for authors and readers to write and read posts. Author role must be tracked in the users table.",
    },
    {
        "id": "lms",
        "type": "product",
        "name": "Learning Management System",
        "prompt": "Design a learning management system where teachers can build courses and student roles can view courses.",
    },
    {
        "id": "taskmanager",
        "type": "product",
        "name": "Task Manager Platform",
        "prompt": "Create a task manager platform for members to assign tasks with title and assignee_id fields.",
    },
    {
        "id": "eventplanner",
        "type": "product",
        "name": "Event Planner Hub",
        "prompt": "Build an event planner app for hosts to schedule events and guests to RSVP to events.",
    },
    {
        "id": "fitnesstracker",
        "type": "product",
        "name": "Fitness Tracker App",
        "prompt": "Design a fitness tracker app where users can track workouts and durations.",
    },
    {
        "id": "expensemanager",
        "type": "product",
        "name": "Corporate Expense Manager",
        "prompt": "Create a corporate expense manager for employees to submit expenses with amounts.",
    },
    {
        "id": "bookingsystem",
        "type": "product",
        "name": "Room Booking System",
        "prompt": "Build a room booking system for customers and admins to reserve rooms or cancel bookings.",
    },

    # ----------------------------------------------------
    # 10 Advanced Edge Cases
    # ----------------------------------------------------
    {
        "id": "admin_forbidden_login",
        "type": "edge_case",
        "name": "Admin Forbidden Login",
        "prompt": "Design an admin portal where admins are not allowed to log in directly via the normal flow. Admin forbidden login page setup.",
    },
    {
        "id": "conflicting_roles",
        "type": "edge_case",
        "name": "Conflicting Roles",
        "prompt": "Create a permissions portal with conflicting roles and circular permissions. Edit_records requires admin approval, but admin lacks approve permission.",
    },
    {
        "id": "negative_pricing",
        "type": "edge_case",
        "name": "Negative Pricing",
        "prompt": "Design a subscription billing system with a pricing tier where the monthly price is negative, e.g. -10 dollars.",
    },
    {
        "id": "no_database",
        "type": "edge_case",
        "name": "No Database",
        "prompt": "Create an in-memory streaming dashboard application that does not persist data and has no database tables.",
    },
    {
        "id": "api_referencing_missing_db",
        "type": "edge_case",
        "name": "API Referencing Missing DB Table",
        "prompt": "Build an API referencing a missing DB table. Endpoint GET orders queries orders table, but orders table is missing from DB.",
    },
    {
        "id": "incorrect_data_type",
        "type": "edge_case",
        "name": "Incorrect Data Type Mismatch",
        "prompt": "Design a registration system with incorrect data type mismatch. The registration body has email as an integer but DB column is TEXT.",
    },
    {
        "id": "empty_intent",
        "type": "edge_case",
        "name": "Empty Intent / No-Op Daemon",
        "prompt": "Design a no-op daemon application with an empty intent. Do absolutely nothing, defining no pages or APIs.",
    },
    {
        "id": "massive_scale",
        "type": "edge_case",
        "name": "Massive Scale Pages",
        "prompt": "Build an enterprise multi-tenant platform with massive scale, creating more than 100 UI pages for this tier.",
    },
    {
        "id": "ambiguous_flow",
        "type": "edge_case",
        "name": "Ambiguous Flow / Circular Routing",
        "prompt": "Create a checkout pipeline with ambiguous flow or circular routing between checkout and login pages.",
    },
    {
        "id": "gated_read",
        "type": "edge_case",
        "name": "Gated Read / Free Users Access Premium",
        "prompt": "Design a gated news publisher where free users are allowed to access a page that calls a premium content API.",
    },
]
