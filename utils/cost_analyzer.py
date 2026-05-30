"""
Cost and performance tracking utility for Gemini models.
Provides estimation of tokens, cost calculation, and aggregate metrics reporting.
"""

import logging
import math
from typing import Dict, Any, List
import pandas as pd
from pydantic import BaseModel, Field

logger = logging.getLogger("CostAnalyzer")


class ModelBreakdownMetrics(BaseModel):
    """Metrics breakdown for a specific model."""
    input_tokens: int = Field(default=0, description="Total input tokens for this model")
    output_tokens: int = Field(default=0, description="Total output tokens for this model")
    cost: float = Field(default=0.0, description="Total cost in USD for this model")
    latency: float = Field(default=0.0, description="Total latency in seconds for this model")
    calls: int = Field(default=0, description="Total number of calls for this model")


class CumulativeMetrics(BaseModel):
    """Aggregate metrics across all LLM client calls."""
    total_input_tokens: int = Field(default=0, description="Total input tokens across all models")
    total_output_tokens: int = Field(default=0, description="Total output tokens across all models")
    total_tokens: int = Field(default=0, description="Total tokens across all models")
    total_cost_usd: float = Field(default=0.0, description="Total cost in USD across all models")
    total_latency_seconds: float = Field(default=0.0, description="Total latency in seconds across all models")
    total_calls: int = Field(default=0, description="Total number of calls across all models")
    average_quality_score: float = Field(default=0.0, description="Weighted average quality score (0.0 to 1.0)")
    average_latency_seconds: float = Field(default=0.0, description="Average latency in seconds")
    model_breakdown: Dict[str, ModelBreakdownMetrics] = Field(
        default_factory=dict, description="Breakdown of metrics by model"
    )


class CostAnalyzer:
    """
    Tracks and analyzes LLM token usage, cost, latency, and quality.
    Supports 'gemini-2.5-flash' and 'gemini-2.5-pro'.
    """

    # Prices per 1M tokens as of specified guidelines
    PRICES = {
        "gemini-2.5-flash": {
            "input": 0.075 / 1_000_000,
            "output": 0.30 / 1_000_000,
            "quality": 0.75,  # Quality score rating (relative)
        },
        "gemini-2.5-pro": {
            "input": 1.25 / 1_000_000,
            "output": 5.00 / 1_000_000,
            "quality": 0.95,  # Quality score rating (relative)
        },
    }

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Resets all tracked metrics to zero."""
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.total_latency = 0.0
        self.call_count = 0
        self.weighted_quality_sum = 0.0

        self.model_metrics = {
            "gemini-2.5-flash": ModelBreakdownMetrics(),
            "gemini-2.5-pro": ModelBreakdownMetrics(),
        }

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Estimates the number of tokens in a text string.
        Rule of thumb: roughly 1 token = 4 characters of text.
        """
        if not text:
            return 0
        return max(1, math.ceil(len(text) / 4.0))

    def _resolve_model(self, model: str) -> str:
        """Resolves the model name to a canonical supported model name."""
        m_lower = model.lower()
        if "pro" in m_lower:
            return "gemini-2.5-pro"
        elif "flash" in m_lower:
            return "gemini-2.5-flash"
        else:
            logger.warning(f"Unknown model name: '{model}'. Defaulting to 'gemini-2.5-flash'.")
            return "gemini-2.5-flash"

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """
        Calculates the dollar cost of a single call based on the model and token counts.
        """
        resolved_model = self._resolve_model(model)
        pricing = self.PRICES[resolved_model]
        return (input_tokens * pricing["input"]) + (output_tokens * pricing["output"])

    def track_call(self, model: str, input_tokens: int, output_tokens: int, latency: float) -> float:
        """
        Tracks a call's metrics, updates cumulative costs, latency, and quality.
        Returns the cost of this specific call.
        """
        resolved_model = self._resolve_model(model)
        pricing = self.PRICES[resolved_model]
        cost = self.calculate_cost(resolved_model, input_tokens, output_tokens)
        quality = pricing["quality"]

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost += cost
        self.total_latency += latency
        self.call_count += 1
        self.weighted_quality_sum += quality

        # Update breakdown
        metrics = self.model_metrics[resolved_model]
        metrics.input_tokens += input_tokens
        metrics.output_tokens += output_tokens
        metrics.cost += cost
        metrics.latency += latency
        metrics.calls += 1

        return cost

    def get_metrics(self) -> CumulativeMetrics:
        """Returns a CumulativeMetrics object containing all cumulative metrics."""
        avg_quality = (self.weighted_quality_sum / self.call_count) if self.call_count > 0 else 0.0
        avg_latency = (self.total_latency / self.call_count) if self.call_count > 0 else 0.0

        return CumulativeMetrics(
            total_input_tokens=self.total_input_tokens,
            total_output_tokens=self.total_output_tokens,
            total_tokens=self.total_input_tokens + self.total_output_tokens,
            total_cost_usd=round(self.total_cost, 6),
            total_latency_seconds=round(self.total_latency, 3),
            total_calls=self.call_count,
            average_quality_score=round(avg_quality, 3),
            average_latency_seconds=round(avg_latency, 3),
            model_breakdown=self.model_metrics,
        )

    def get_metrics_df(self) -> pd.DataFrame:
        """
        Renders a clean Pandas DataFrame of the metrics for visualization.
        """
        data = []
        metrics = self.get_metrics()

        # Add total row
        data.append({
            "Model": "All Models (Total)",
            "Calls": metrics.total_calls,
            "Input Tokens": metrics.total_input_tokens,
            "Output Tokens": metrics.total_output_tokens,
            "Total Tokens": metrics.total_tokens,
            "Total Cost ($)": round(metrics.total_cost_usd, 6),
            "Avg Latency (s)": round(metrics.average_latency_seconds, 3),
            "Avg Quality Score": round(metrics.average_quality_score, 3),
        })

        # Add individual models
        for model_name, m_metrics in metrics.model_breakdown.items():
            avg_lat = (m_metrics.latency / m_metrics.calls) if m_metrics.calls > 0 else 0.0
            data.append({
                "Model": model_name,
                "Calls": m_metrics.calls,
                "Input Tokens": m_metrics.input_tokens,
                "Output Tokens": m_metrics.output_tokens,
                "Total Tokens": m_metrics.input_tokens + m_metrics.output_tokens,
                "Total Cost ($)": round(m_metrics.cost, 6),
                "Avg Latency (s)": round(avg_lat, 3),
                "Avg Quality Score": self.PRICES[model_name]["quality"] if m_metrics.calls > 0 else 0.0,
            })

        return pd.DataFrame(data)
