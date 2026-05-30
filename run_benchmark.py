"""
Automation script to run the 20-scenario compiler benchmark test suite,
save the results to JSON, and dynamically update README.md with a detailed metrics table.
"""

import json
import os
import re
from evaluation.runner import EvaluationRunner

def run_benchmark_and_update_readme():
    print("Starting 20-scenario compiler benchmark runner...")
    runner = EvaluationRunner(mock=True, model="claude-3-5-sonnet-20241022")
    results = runner.evaluate_dataset()
    
    # Save raw results
    results_path = "evaluation_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Raw benchmark results saved successfully to '{results_path}'")

    # Aggregate metrics
    total_cases = len(results)
    success_cases = sum(1 for r in results if r["success"])
    success_rate = (success_cases / total_cases) * 100
    total_retries = sum(r["retries"] for r in results)
    avg_retries = total_retries / total_cases
    total_latency = sum(r["latency"] for r in results)
    avg_latency = total_latency / total_cases
    total_cost = sum(r["cost"] for r in results)

    print(f"Success Rate: {success_rate:.1f}% ({success_cases}/{total_cases})")
    print(f"Avg Latency: {avg_latency:.3f}s")
    print(f"Total Repairs: {total_retries}")
    print(f"Total Cost: ${total_cost:.6f}")

    # Generate Markdown Table
    md_table = (
        "| Scenario ID | Name | Category | Compiled Success? | Simulator Success? | Repairs | Latency (s) | Estimated Cost ($) |\n"
        "| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |\n"
    )
    for r in results:
        comp_success = "✅ Yes" if r["success"] else "❌ No"
        sim_success = "✅ Passed" if (r["success"] and not r["errors"]) else "❌ Failed"
        # Category translation
        cat = "Product Template" if r["type"] == "product" else "Edge Case"
        md_table += (
            f"| `{r['id']}` | {r['name']} | {cat} | {comp_success} | {sim_success} | "
            f"{r['retries']} | {r['latency']:.3f}s | ${r['cost']:.6f} |\n"
        )

    # Read README.md
    readme_path = "README.md"
    if not os.path.exists(readme_path):
        print(f"Error: '{readme_path}' not found. Cannot update documentation.")
        return

    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Define the block pattern to insert metrics
    summary_block = (
        f"### Summary Metrics:\n"
        f"- **Overall Success Rate**: **{success_rate:.1f}%** ({success_cases}/{total_cases} scenarios)\n"
        f"- **Average Compilation Latency**: **{avg_latency:.3f} seconds**\n"
        f"- **Total System Repairs Needed**: **{total_retries} iterations**\n"
        f"- **Total Estimated Token Cost**: **${total_cost:.6f} USD**\n\n"
        f"{md_table}"
    )

    # Find the Benchmark Suite & Results section and replace the details
    pattern = r"(## 📊 Benchmark Suite & Results.*?\n)(.*?)(\n---|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        header = match.group(1)
        footer = match.group(3)
        # Keep introduction text if any, but replace table and metrics
        intro = (
            "The codebase includes an automated benchmarker evaluating **20 scenarios** (10 real products and 10 edge cases):\n"
            "*   **10 Core Products**: CRM, E-commerce, Inventory, Blog, LMS, Task Manager, Event Planner, Fitness Tracker, Expense Manager, Booking System.\n"
            "*   **10 Edge Cases**: Vague inputs, conflicting role permissions, negative pricing rates, circular page redirects, incorrect data types, and missing database tables.\n\n"
        )
        new_section = header + intro + summary_block + footer
        content = content[:match.start()] + new_section + content[match.end():]
        
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("README.md has been successfully updated with the latest benchmark metrics table!")
    else:
        print("Could not find '## 📊 Benchmark Suite & Results' section in README.md to replace.")

if __name__ == "__main__":
    run_benchmark_and_update_readme()
