# Software Generation Compiler ⚙️🚀

An agentic, multi-stage compiler that translates natural language prompts into strict, complete, and validated software configurations (UI, API, Database, Auth, Business Logic) and simulates their execution in a mock runtime.

Designed to operate as a **reliable software compilation pipeline** rather than a simple prompt engineering script.

---

## 🏗️ Architecture Design

The compiler operates as a structured, four-stage compilation pipeline followed by strict validation, targeted self-repair loops, and runtime execution simulation.

```mermaid
graph TD
    Prompt[User Prompt] --> IE[Stage 1: Intent Extractor Agent]
    IE --> SA[Stage 2: System Architect Agent]
    SA --> SG[Stage 3: Schema Generator Agent]
    SG --> RF[Stage 4: Refinement Agent]
    RF --> Val{Validation Engine}
    
    Val -- Error Reports --> Rep[Repair Agent]
    Rep --> RF
    
    Val -- Clean Config --> Sim[Execution Awareness Simulator]
    Sim -- Simulation Error --> Rep
    Sim -- Success --> Output[Final Executable JSON]
```

### 1. Multi-Stage Pipeline (`/pipeline`)
*   **Intent Extractor** (`intent_extractor.py`): Parses the natural language prompt into a structured intent representation (identifying core components, user roles, pricing tiers, and actions).
*   **System Architect** (`system_architect.py`): Maps the intent to system-level architectures (defines entities, database schemas, relations, API endpoints, page layouts, and access rules).
*   **Schema Generator** (`schema_generator.py`): Generates the individual schema components for the UI layout, database structures, endpoint inputs, and authorization permissions.
*   **Refinement Agent** (`refinement.py`): Reconciles and aligns naming conventions, data types, and references across all schema sections.

### 2. Strongly-Typed Schema Contracts (`pipeline/schemas.py`)
Uses Pydantic models to define a strict output contract (`UnifiedAppConfigSchema`). Ensures that every page component, API request field, and database column is correctly typed and structured.

### 3. Validation & Repair Engine (`/engine`)
*   **Validator** (`validator.py`): Performs syntax checking, data type verification (matching API payloads to database column types), circular routing check (detecting infinite redirects), and cross-layer consistency (verifying that page buttons reference actual API routes and that APIs use valid tables/columns).
*   **Repair Agent** (`repair.py`): Implements targeted repair. When the validator finds errors, the repair agent receives a diagnostic report and corrects **only** the failing schema components, avoiding a full pipeline retry.

### 4. Simulator Runtime (`engine/runtime.py`)
Simulates the execution of the final configuration by setting up an in-memory database and API router.
*   Runs **positive journeys**: simulates login, data submission, and table fetches to verify UI-to-API-to-DB mapping.
*   Runs **negative security checks**: attempts to perform unauthorized API calls to confirm that role-gating rules correctly block requests.

---

## 📊 Benchmark Suite & Results (`/evaluation`)

The codebase includes an automated benchmarker evaluating **20 scenarios** (10 real products and 10 edge cases):
*   **10 Core Products**: CRM, E-commerce, Inventory, Blog, LMS, Task Manager, Event Planner, Fitness Tracker, Expense Manager, Booking System.
*   **10 Edge Cases**: Vague inputs, conflicting role permissions, negative pricing rates, circular page redirects, incorrect data types, and missing database tables.

### Execution Results:
*   **Success Rate**: **100%** (all 20 scenarios compile successfully and pass execution simulations).
*   **Automatic Self-Repair**: Successfully tested and verified on complex scenarios (e.g. automatically detecting and correcting negative pricing and role mismatches in API-DB mappings).

---

## 🎨 Streamlit Interface Features (`app.py`)

The system includes a premium dark-themed web interface offering:
1.  **Compiler Workspace**: Write custom prompts, choose from the 20 preloaded templates, watch compilation logs and self-repair iterations, and inspect the simulator execution.
2.  **Evaluator Dashboard**: Trigger the full 20-scenario benchmark suite to visualize overall success rates, latencies, repair counts, and token costs with Plotly charts.
3.  **Cost vs Quality Optimizer**: Live sliders-based tool to calculate expected API costs comparing Gemini 2.5 Pro vs Gemini 2.5 Flash and hybrid routing models.

---

## 🚀 Setup & Execution

### 📋 Prerequisites
Ensure you have Python 3.10.5 (or higher) installed. 

### 🔧 Installation
1. Clone the repository and navigate to the directory:
   ```bash
   git clone https://github.com/vikashg450/Software-Generation-Compiler.git
   cd Software-Generation-Compiler
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up your Gemini API key (Optional - falls back to High-Fidelity Mock Compiler mode if omitted):
   * Create a `.env` file in the root directory:
     ```env
     GEMINI_API_KEY=your_gemini_api_key_here
     ```
   * Alternatively, you can enter the API Key directly in the Streamlit UI sidebar.

### 🏃 Running the Application
Launch the Streamlit dashboard:
```bash
python -m streamlit run app.py
```
Open your browser and navigate to `http://localhost:8501`.
