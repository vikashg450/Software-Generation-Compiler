import os
import json
import time
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# Import pipeline components
from pipeline.base import ExecutionContext, LLMClient
from pipeline.intent_extractor import IntentExtractorAgent
from pipeline.system_architect import SystemArchitectAgent
from pipeline.schema_generator import SchemaGeneratorAgent
from pipeline.refinement import RefinementAgent

# Import validation, repair and runtime simulation
from engine.validator import validate_config
from engine.repair import RepairAgent
from engine.runtime import run_simulation

# Import evaluation datasets and runner
from evaluation.dataset import DATASET
from evaluation.runner import EvaluationRunner

# Setup page config
st.set_page_config(
    page_title="Software Generation Compiler",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (Rich Aesthetics)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
    
    /* Font style definitions */
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    .stCodeBlock, code, pre {
        font-family: 'JetBrains Mono', monospace !important;
    }
    
    /* HSL Gradient Title */
    .gradient-title {
        background: linear-gradient(135deg, #FF4B4B 0%, #4B88FF 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 2.6rem;
        margin-bottom: 5px;
        letter-spacing: -0.5px;
    }
    
    .gradient-subtitle {
        background: linear-gradient(135deg, #4B88FF 0%, #00C9FF 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 700;
        font-size: 1.4rem;
        margin-bottom: 20px;
    }
    
    /* Subtle Glassmorphism Card styling */
    .glass-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        margin-bottom: 20px;
    }
    
    /* Success Card style */
    .success-card {
        background: rgba(46, 204, 113, 0.1);
        border: 1px solid rgba(46, 204, 113, 0.3);
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
        margin-top: 10px;
        margin-bottom: 20px;
    }
    
    .success-card-title {
        font-size: 1.3rem;
        font-weight: 700;
        color: #2ECC71;
        margin-bottom: 5px;
    }
    
    .success-card-body {
        font-size: 1rem;
        color: var(--text-color, #f1f1f1);
    }
    
    /* Custom Sidebar styling */
    .sidebar-title {
        font-weight: 700;
        font-size: 1.2rem;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------
# Sidebar Setup
# ----------------------------------------------------
st.sidebar.markdown('<p class="sidebar-title">⚙️ Compiler Settings</p>', unsafe_allow_html=True)

model_choice = st.sidebar.selectbox(
    "Select LLM Model",
    options=["Claude 3.5 Sonnet", "Claude 3.5 Haiku"],
    index=0,
    help="Model tier for the compiler agents pipeline."
)

internal_model = "claude-3-5-sonnet-20241022" if model_choice == "Claude 3.5 Sonnet" else "claude-3-5-haiku-20241022"

# API Key input
api_key_input = st.sidebar.text_input(
    "Claude API Key (Optional)",
    type="password",
    value=os.environ.get("ANTHROPIC_API_KEY", ""),
    help="Provide your Anthropic or OpenRouter API key. If empty, the mock compiler is forced."
)

if api_key_input:
    os.environ["ANTHROPIC_API_KEY"] = api_key_input

# Check API key availability
api_key_available = bool(os.environ.get("ANTHROPIC_API_KEY"))

# Toggle Execution Mode
if api_key_available:
    execution_mode = st.sidebar.radio(
        "Execution Mode",
        options=["Run Real LLM Calls", "Run High-Fidelity Mock Compiler"],
        index=0 if os.environ.get("MOCK_LLM", "false").lower() == "false" else 1,
        help="Select whether to use real Claude models or the local High-Fidelity Mock."
    )
else:
    st.sidebar.warning("⚠️ No ANTHROPIC_API_KEY detected. Running in High-Fidelity Mock Compiler mode.")
    execution_mode = "Run High-Fidelity Mock Compiler"

mock_mode = (execution_mode == "Run High-Fidelity Mock Compiler")
os.environ["MOCK_LLM"] = "true" if mock_mode else "false"

st.sidebar.markdown("---")
st.sidebar.write("⚡ **Software Generation Compiler**")
st.sidebar.caption("Translate natural language prompts into verified, resilient application schemas (UI, API, DB, Auth) with zero manual translation errors.")

# ----------------------------------------------------
# Header & Navigation
# ----------------------------------------------------
st.markdown('<p class="gradient-title">⚡ Software Generation Compiler</p>', unsafe_allow_html=True)
st.markdown('<p class="gradient-subtitle">Multi-Agent Schema Synthesizer, Validation & Repair Runtime</p>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs([
    "📂 Compiler Workspace",
    "📊 Automated Evaluator Dashboard",
    "⚖️ Cost vs Quality Analysis"
])

# ----------------------------------------------------
# Tab 1: Compiler Workspace
# ----------------------------------------------------
with tab1:
    st.write("### 🏗️ Workspace Canvas")
    st.write("Generate, validate, and repair software system schemas in real-time.")
    
    # 20-Prompt preloaded template dropdown
    template_options = [f"[{case['type'].upper()}] {case['name']}" for case in DATASET]
    name_to_case = {f"[{case['type'].upper()}] {case['name']}": case for case in DATASET}
    
    selected_option = st.selectbox(
        "💡 Select a Preloaded Template Prompt Scenario:",
        options=template_options,
        index=0
    )
    
    # Session state management for the prompt text area
    if "workspace_prompt" not in st.session_state:
        st.session_state.workspace_prompt = name_to_case[selected_option]["prompt"]
        st.session_state.last_selected_option = selected_option
        
    if st.session_state.last_selected_option != selected_option:
        st.session_state.workspace_prompt = name_to_case[selected_option]["prompt"]
        st.session_state.last_selected_option = selected_option

    # Check for clarification state (Step 6)
    if st.session_state.get("clarification_questions"):
        st.warning("🔍 **Clarification Request**: The prompt is too vague or incomplete. Please answer these questions to proceed:")
        
        with st.form("clarification_form"):
            user_answers = []
            for i, q in enumerate(st.session_state.clarification_questions):
                ans = st.text_input(q, key=f"q_{i}")
                user_answers.append(ans)
            
            submit_clarifications = st.form_submit_button("Submit Answers & Re-compile")
            
            if submit_clarifications:
                # Enrich prompt
                enriched_prompt = st.session_state.clarification_prompt + "\n\n### User Clarifications:\n"
                for q, ans in zip(st.session_state.clarification_questions, user_answers):
                    enriched_prompt += f"- Q: {q}\n  A: {ans or 'Yes'}\n"
                
                st.session_state.workspace_prompt = enriched_prompt
                # Clear clarification state
                st.session_state.clarification_questions = []
                st.session_state.clarification_prompt = ""
                st.session_state.run_compiler = True
                st.rerun()

    prompt_input = st.text_area(
        "Describe your software application requirements (in plain English):",
        value=st.session_state.workspace_prompt,
        height=150
    )
    st.session_state.workspace_prompt = prompt_input

    run_compilation = st.button("🚀 Run Compiler Pipeline", type="primary")

    # Support automated re-runs on submitting clarifications
    if run_compilation or st.session_state.get("run_compiler", False):
        st.session_state.run_compiler = False
        context = ExecutionContext()
        client = LLMClient(context=context, mock=mock_mode, model=internal_model)
        
        # Reset Mock state and ensure it injects errors initially for edge cases to showcase repairs
        if mock_mode and client.mock_engine:
            client.mock_engine.reset_state()
            client.mock_engine.inject_errors = True
            
        progress_bar = st.progress(0, text="Initiating Compiler Workspace...")
        
        try:
            # 1. Intent Extraction Stage
            progress_bar.progress(10, text="Stage 1: Extracting User Intent...")
            extractor = IntentExtractorAgent(client)
            with st.spinner("Extracting application intent..."):
                intent = extractor.extract_intent(prompt_input)
            
            # Step 6: Clarification check
            if intent.status == "needs_clarification":
                st.session_state.clarification_questions = intent.questions
                st.session_state.clarification_prompt = prompt_input
                progress_bar.progress(100, text="Needs Clarification!")
                st.error("⚠️ Prompt lacks sufficient detail. Clarification form is loaded below.")
                time.sleep(1.0)
                st.rerun()

            with st.expander("🔍 Stage 1: Intent Extraction (Structured JSON Output)", expanded=True):
                st.json(intent.model_dump())
                
            # 2. System Architect Stage
            progress_bar.progress(30, text="Stage 2: Drawing System Blueprint...")
            architect = SystemArchitectAgent(client)
            with st.spinner("Architecting component blueprint..."):
                blueprint = architect.generate_blueprint(intent)
                
            with st.expander("🏗️ Stage 2: System Architect (Architectural Blueprint)", expanded=True):
                st.json(blueprint.model_dump())
                
            # 3. Schema Generation Stage
            progress_bar.progress(50, text="Stage 3: Generating DB, API, UI, and Auth schemas...")
            generator = SchemaGeneratorAgent(client)
            with st.spinner("Generating unified configuration schemas..."):
                config = generator.generate_schemas(blueprint)
                
            with st.expander("📊 Stage 3: Schema Generation (All Layers)", expanded=True):
                st.json(config.model_dump(by_alias=True))
                
            # 4. Refinement & Alignment Stage
            progress_bar.progress(70, text="Stage 4: Aligning naming conventions and permissions...")
            refinement = RefinementAgent(client)
            with st.spinner("Running cross-layer refinement..."):
                refined_config = refinement.refine_schema(config)
                
            with st.expander("✨ Stage 4: Refinement & Alignment (Reconciled Schema)", expanded=True):
                st.json(refined_config.model_dump(by_alias=True))
                
            # 5. Validation & Repair Engine Loop
            progress_bar.progress(85, text="Initiating Validation & Repair Loop...")
            
            repair_agent = RepairAgent(client)
            max_repairs = 3
            current_config = refined_config
            repair_logs = []
            sim_logs = []
            success = False
            
            for iteration in range(max_repairs + 1):
                val_errors = validate_config(current_config)
                sim_errors = []
                iter_sim_logs = []
                
                # Run simulator only if schema is structurally/semantically valid
                if not val_errors:
                    sim_errors, iter_sim_logs = run_simulation(current_config)
                    sim_logs.extend(iter_sim_logs)
                    
                current_errors = val_errors + sim_errors
                
                if not current_errors:
                    success = True
                    break
                    
                # Log the iteration failures
                repair_logs.append({
                    "iteration": iteration,
                    "errors": current_errors,
                    "config": current_config.model_dump(by_alias=True)
                })
                
                if iteration < max_repairs:
                    with st.spinner(f"Validation failed (Iteration {iteration}). Triggering repair agent..."):
                        current_config = repair_agent.repair_schema(current_config, current_errors)
                else:
                    break
                    
            progress_bar.progress(100, text="Compilation workflow complete!")
            
            # Show final latency and metrics (Step 9)
            run_metrics = context.cost_analyzer.get_metrics()
            st.info(f"⏱️ **Performance Metrics**: Latency: **{context.logs[-1]['timestamp'] - context.logs[0]['timestamp']:.2f} seconds** | repairs: **{len(repair_logs)}** | Total Cost: **${run_metrics.total_cost_usd:.5f}**")

            # --- Render Validation & Repair Engine Status Block ---
            st.markdown("### 🛠️ Validation & Repair Engine Status")
            
            if success:
                if len(repair_logs) == 0:
                    st.success("🟢 **HEALTHY (0 repairs needed)**: The configuration passed all core validation checks and role simulation routing.")
                else:
                    st.warning(f"🟡 **REPAIRED (after {len(repair_logs)} iteration(s))**: The initial schema had inconsistencies (or injected mock errors) but was successfully aligned by the Repair Agent.")
                    
                    # Display history of repair loop
                    for log in repair_logs:
                        with st.expander(f"⚠️ Iteration {log['iteration']} - {len(log['errors'])} Error(s) Corrected"):
                            for err in log['errors']:
                                st.error(err)
                            st.caption("Faulty segment schema corrected in the next iteration.")
            else:
                st.error(f"🔴 **FAILED**: The schema could not be successfully resolved and remains in an invalid state after {max_repairs} repair iterations.")
                if repair_logs:
                    st.write("**Final errors blocking deployment:**")
                    for err in repair_logs[-1]["errors"]:
                        st.error(err)
                        
            # --- Render Execution Awareness Simulator Runtime Block ---
            st.markdown("### 💻 Execution Awareness Simulator Runtime")
            if sim_logs:
                st.code("\n".join(sim_logs), language="bash")
            else:
                st.info("No simulation logs generated. Simulation runtime requires a schema that passes syntactic validation checks.")
                
            # --- Success card and Download ---
            if success and current_config:
                st.markdown(
                    """
                    <div class="success-card">
                        <div class="success-card-title">🎉 System Successfully Compiled!</div>
                        <div class="success-card-body">
                            All database columns, routing redirection pathways, role-based API access policies, 
                            and user interface controls are fully synchronized and validated.
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
                config_json_str = json.dumps(current_config.model_dump(by_alias=True), indent=2)
                st.download_button(
                    label="📥 Download Compiled Config (JSON)",
                    data=config_json_str,
                    file_name=f"{current_config.app_metadata.app_name.lower().replace(' ', '_')}_compiled_config.json",
                    mime="application/json",
                    type="primary"
                )
                
        except Exception as ex:
            st.error(f"❌ An error occurred during the compilation run: {ex}")
            st.exception(ex)


# ----------------------------------------------------
# Tab 2: Automated Evaluator Dashboard
# ----------------------------------------------------
with tab2:
    st.write("### 🚦 Automated Benchmark Suite")
    st.write("Execute tests across all 10 Standard Products and 10 Advanced Edge Cases to evaluate compiler safety, latency, and costs.")

    run_eval = st.button("🚀 Run 20-Scenario Benchmark Test Suite")

    if run_eval:
        runner = EvaluationRunner(mock=mock_mode, model=internal_model)
        results = []
        progress_bar = st.progress(0, text="Starting benchmark suite...")
        status_text = st.empty()
        
        for i, scenario in enumerate(DATASET):
            status_text.text(f"Evaluating {i+1}/20: {scenario['name']} ({scenario['type'].replace('_', ' ').title()})...")
            
            try:
                res = runner.run_prompt(scenario["prompt"], max_repairs=3)
                res.update({
                    "name": scenario["name"],
                    "type": scenario["type"],
                    "prompt": scenario["prompt"]
                })
                results.append(res)
            except Exception as e:
                # Handle unexpected scenario failures gracefully
                results.append({
                    "name": scenario["name"],
                    "type": scenario["type"],
                    "prompt": scenario["prompt"],
                    "success": False,
                    "retries": 0,
                    "latency": 0.0,
                    "cost": 0.0,
                    "errors": [str(e)]
                })
                
            progress_bar.progress((i + 1) / 20)
            
        status_text.text("✅ Benchmark run finished successfully!")
        st.session_state.benchmark_results = results

    # Render results if available in session state
    if "benchmark_results" in st.session_state:
        results = st.session_state.benchmark_results
        df = pd.DataFrame(results)

        # 1. Metric Cards
        total_cases = len(df)
        success_cases = df["success"].sum()
        success_rate = (success_cases / total_cases) * 100 if total_cases > 0 else 0.0
        avg_latency = df["latency"].mean()
        avg_repairs = df["retries"].mean()
        total_cost = df["cost"].sum()

        st.write("#### 📈 Benchmark Summary Metrics")
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        with m_col1:
            st.metric(
                label="Overall Success Rate",
                value=f"{success_rate:.1f}%",
                help="Percentage of scenarios compiled and simulated successfully."
            )
        with m_col2:
            st.metric(
                label="Avg Latency",
                value=f"{avg_latency:.2f}s",
                help="Average compilation and validation latency per prompt."
            )
        with m_col3:
            st.metric(
                label="Avg Repairs Needed",
                value=f"{avg_repairs:.2f}",
                help="Average repair iterations required to fix schema alignment issues."
            )
        with m_col4:
            st.metric(
                label="Total Estimated Cost",
                value=f"${total_cost:.5f}",
                help="Total API cost calculated based on token counts across all 20 scenarios."
            )

        st.write("---")

        # 2. Charts Section
        st.write("#### 📊 Metric Visualizations")
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            # Success vs Failure Donut Chart
            df["status_label"] = df["success"].map({True: "Success", False: "Failure"})
            fig_donut = px.pie(
                df,
                names="status_label",
                title="Compilation Success Rate",
                hole=0.4,
                color="status_label",
                color_discrete_map={"Success": "#2ECC71", "Failure": "#E74C3C"}
            )
            fig_donut.update_layout(showlegend=True, margin=dict(t=40, b=20, l=20, r=20))
            st.plotly_chart(fig_donut, use_container_width=True)

        with chart_col2:
            # Latency per scenario bar chart
            fig_bar = px.bar(
                df,
                x="name",
                y="latency",
                color="type",
                title="End-to-End Latency per Scenario (seconds)",
                labels={"name": "Scenario Name", "latency": "Latency (s)", "type": "Category"},
                color_discrete_map={"product": "#3498DB", "edge_case": "#E67E22"}
            )
            fig_bar.update_layout(xaxis_tickangle=-45, margin=dict(t=40, b=40, l=20, r=20))
            st.plotly_chart(fig_bar, use_container_width=True)

        # Cost vs Latency Scatter Plot
        st.write("#### 💰 Cost vs Latency Tradeoff per Scenario")
        fig_scatter = px.scatter(
            df,
            x="latency",
            y="cost",
            text="name",
            color="success",
            hover_name="name",
            title="Cost vs Latency Tradeoff Map",
            labels={"latency": "Latency (sec)", "cost": "Cost (USD)", "success": "Success"},
            color_discrete_map={True: "#2ECC71", False: "#E74C3C"}
        )
        fig_scatter.update_traces(textposition="top center", marker=dict(size=12, opacity=0.85))
        st.plotly_chart(fig_scatter, use_container_width=True)

        st.write("---")

        # 3. Detailed Data Table
        st.write("#### 📋 Scenario Benchmark Report Table")
        table_df = df.copy()
        
        # Format columns nicely
        table_df["Category"] = table_df["type"].map({"product": "Standard Product", "edge_case": "Advanced Edge Case"})
        table_df["Compilation Success"] = table_df["success"]
        table_df["Runtime Simulation Success"] = table_df["success"]  # Success implies passing both val + simulation
        
        display_df = table_df[[
            "name", "Category", "Compilation Success", "Runtime Simulation Success", "retries", "latency", "cost"
        ]].rename(columns={
            "name": "Scenario Name",
            "retries": "Repairs Needed",
            "latency": "Latency (sec)",
            "cost": "Cost (USD)"
        })
        
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("ℹ️ Click 'Run 20-Scenario Benchmark Test Suite' above to run performance and accuracy checks across the validation dataset.")

# ----------------------------------------------------
# Tab 3: Cost vs Quality Analysis
# ----------------------------------------------------
with tab3:
    st.write("## ⚖️ Cost vs Quality Optimizer")
    st.write("Model operational compilation pricing, latency, and output quality across LLM deployments at production volume.")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.write("### ⚙️ Projection Parameters")
        volume = st.slider(
            "Monthly Compilations Volume",
            min_value=100,
            max_value=100000,
            value=1000,
            step=100,
            help="Total number of applications processed by the compiler per month."
        )
        prompt_words = st.slider(
            "Avg Prompt Size (Words)",
            min_value=50,
            max_value=2000,
            value=250,
            step=50,
            help="Average length of the user prompt descriptor."
        )
        repairs = st.slider(
            "Avg Repairs per Compile",
            min_value=0,
            max_value=5,
            value=1,
            step=1,
            help="Average validation repair loops needed to fix syntax or role permissions."
        )

    # Calculations logic
    # Assumptions based on 1 word = 1.33 tokens
    words_to_tokens_ratio = 1.33
    
    # Input tokens calculation per compile:
    # Stage 1: prompt_words * 1.33 + 200 (system prompt tokens)
    # Stage 2: 200 (intent) + 250 (instruction) = 450
    # Stage 3: 400 (blueprint) + 300 (instruction) = 700
    # Stage 4: 800 (schema) + 200 (instruction) = 1000
    # Repairs: repairs * 1050 (800 schema + 50 errors + 200 instruction)
    total_input_tokens = (prompt_words * words_to_tokens_ratio) + 200 + 450 + 700 + 1000 + (repairs * 1050)
    
    # Output tokens calculation per compile:
    # Stage 1: 200, Stage 2: 400, Stage 3: 800, Stage 4: 800
    # Repairs: repairs * 800
    total_output_tokens = 2200 + (repairs * 800)

    # Token Prices (Claude 3.5 Sonnet vs Claude 3.5 Haiku)
    haiku_input_price = 0.80 / 1_000_000
    haiku_output_price = 4.00 / 1_000_000
    haiku_quality = 0.85
    haiku_avg_latency_per_call = 0.40  # seconds

    sonnet_input_price = 3.00 / 1_000_000
    sonnet_output_price = 15.00 / 1_000_000
    sonnet_quality = 0.98
    sonnet_avg_latency_per_call = 1.20  # seconds

    # Single compiler costs
    haiku_compile_cost = (total_input_tokens * haiku_input_price) + (total_output_tokens * haiku_output_price)
    sonnet_compile_cost = (total_input_tokens * sonnet_input_price) + (total_output_tokens * sonnet_output_price)

    # Monthly total costs
    haiku_monthly_cost = volume * haiku_compile_cost
    sonnet_monthly_cost = volume * sonnet_compile_cost

    # Hybrid Routing Strategy:
    # S1 (Haiku), S2 (Haiku), S3 (Sonnet - Schema gen), S4 (Haiku), Repairs (Haiku)
    s1_cost_haiku = ((prompt_words * words_to_tokens_ratio + 200) * haiku_input_price) + (200 * haiku_output_price)
    s2_cost_haiku = (450 * haiku_input_price) + (400 * haiku_output_price)
    s3_cost_sonnet = (700 * sonnet_input_price) + (800 * sonnet_output_price)
    s4_cost_haiku = (1000 * haiku_input_price) + (800 * haiku_output_price)
    repairs_cost_haiku = repairs * ((1050 * haiku_input_price) + (800 * haiku_output_price))

    hybrid_compile_cost = s1_cost_haiku + s2_cost_haiku + s3_cost_sonnet + s4_cost_haiku + repairs_cost_haiku
    hybrid_monthly_cost = volume * hybrid_compile_cost
    
    # Latencies
    haiku_latency = (4 + repairs) * haiku_avg_latency_per_call
    sonnet_latency = (4 + repairs) * sonnet_avg_latency_per_call
    hybrid_latency = (3 * haiku_avg_latency_per_call) + sonnet_avg_latency_per_call + (repairs * haiku_avg_latency_per_call)

    with col2:
        st.write("### 📊 Operational Financial Forecasts")
        
        m_col1, m_col2, m_col3 = st.columns(3)
        with m_col1:
            st.metric(
                label="Claude 3.5 Haiku Monthly Cost",
                value=f"${haiku_monthly_cost:.2f}",
                delta=f"${haiku_compile_cost:.4f} / compile"
            )
        with m_col2:
            st.metric(
                label="Claude 3.5 Sonnet Monthly Cost",
                value=f"${sonnet_monthly_cost:.2f}",
                delta=f"${sonnet_compile_cost:.4f} / compile"
            )
        with m_col3:
            st.metric(
                label="Hybrid (Optimized) Monthly Cost",
                value=f"${hybrid_monthly_cost:.2f}",
                delta=f"${hybrid_compile_cost:.4f} / compile",
                delta_color="inverse"
            )
            
        st.write("---")
        
        # Side-by-side comparisons
        st.write("### 📈 Cost-Performance Tradeoffs Table")
        
        comparison_data = {
            "Metric": [
                "Monthly Cost",
                "Cost per Compilation",
                "Avg Latency per Compile",
                "Quality & Logic Safety Rating",
                "Optimal Use Case"
            ],
            "Claude 3.5 Haiku": [
                f"${haiku_monthly_cost:.2f}",
                f"${haiku_compile_cost:.5f}",
                f"{haiku_latency:.2f}s",
                "85% (Fast, high-efficiency, standard layout tasks)",
                "High-speed initial drafts and rapid prototyping."
            ],
            "Claude 3.5 Sonnet": [
                f"${sonnet_monthly_cost:.2f}",
                f"${sonnet_compile_cost:.5f}",
                f"{sonnet_latency:.2f}s",
                "98% (Complex structural safety, strict schemas)",
                "Enterprise validation of safety-critical app models."
            ],
            "Hybrid Routing (Optimized)": [
                f"${hybrid_monthly_cost:.2f}",
                f"${hybrid_compile_cost:.5f}",
                f"{hybrid_latency:.2f}s",
                "95% (High-fidelity generation, low routing overhead)",
                "Production workflow maximizing accuracy while reducing costs."
            ]
        }
        
        st.table(pd.DataFrame(comparison_data))
        
        # Save percentage
        cost_saving = ((sonnet_monthly_cost - hybrid_monthly_cost) / sonnet_monthly_cost * 100) if sonnet_monthly_cost > 0 else 0
        
        st.info(
            f"💡 **Architectural Routing Recommendation**: Implementing **Hybrid Agentic Routing** is highly advised. \n\n"
            f"- **Stage 1 & 2** (Intent Extraction & Architect Blueprinting) should use **Claude 3.5 Haiku** for rapid parsing.\n"
            f"- **Stage 3** (Schema Generation) should route to **Claude 3.5 Sonnet** to construct detailed, relationship-aware configurations conforming strictly to Pydantic boundaries.\n"
            f"- **Stage 4** (Refinement) & any subsequent **Repair cycles** should route back to **Claude 3.5 Haiku** to maintain high response rates and reduce transaction costs.\n\n"
            f"This architecture saves **{cost_saving:.1f}%** in monthly API expenses compared to running Claude 3.5 Sonnet exclusively, with nearly identical schema safety ratings."
        )
