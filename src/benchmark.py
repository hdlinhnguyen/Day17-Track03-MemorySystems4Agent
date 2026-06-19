from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from config import load_config


@dataclass
class BenchmarkRow:
    agent_name: str
    agent_tokens_only: int
    prompt_tokens_processed: int
    recall_score: float
    response_quality: float
    memory_growth_bytes: int
    compactions: int


import json
from tabulate import tabulate


def load_conversations(path: Path) -> list[dict[str, Any]]:
    """Read JSON conversations from disk."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def recall_points(answer: str, expected: list[str]) -> float:
    """Return 0 / 0.5 / 1 depending on how many expected facts appear."""
    if not expected:
        return 1.0
    answer_lower = answer.lower()
    matches = 0
    for item in expected:
        if item.lower() in answer_lower:
            matches += 1
    
    if matches == len(expected):
        return 1.0
    elif matches > 0:
        return 0.5
    return 0.0


def heuristic_quality(answer: str, expected: list[str]) -> float:
    """Add a lightweight quality score for offline mode."""
    if not answer:
        return 0.0
    answer_lower = answer.lower()
    matches = sum(1 for item in expected if item.lower() in answer_lower)
    if not expected:
        return 1.0
    ratio = matches / len(expected)
    return min(1.0, 0.5 + 0.5 * ratio if matches > 0 else 0.2)


def run_agent_benchmark(agent_name: str, agent, conversations: list[dict[str, Any]], config) -> BenchmarkRow:
    """Evaluate one agent over many conversations."""
    # Clean old profiles if they exist
    if hasattr(agent, "profile_store"):
        profile_dir = agent.profile_store.root_dir
        if profile_dir.exists():
            for f in profile_dir.glob("*.md"):
                try:
                    f.unlink()
                except Exception:
                    pass
        profile_dir.mkdir(parents=True, exist_ok=True)

    all_threads = set()
    recall_scores = []
    quality_scores = []
    
    for conv in conversations:
        thread_id = conv["id"]
        user_id = conv["user_id"]
        all_threads.add(thread_id)
        
        # 1. Feed main conversation turns
        for turn in conv["turns"]:
            agent.reply(user_id, thread_id, turn)
            
        # 2. Ask recall questions in fresh threads
        for q_idx, q_item in enumerate(conv["recall_questions"]):
            recall_thread_id = f"{thread_id}-recall-{q_idx}"
            all_threads.add(recall_thread_id)
            
            question = q_item["question"]
            expected = q_item["expected_contains"]
            
            result = agent.reply(user_id, recall_thread_id, question)
            answer = result["response"]
            
            r_score = recall_points(answer, expected)
            q_score = heuristic_quality(answer, expected)
            
            recall_scores.append(r_score)
            quality_scores.append(q_score)

    avg_recall = sum(recall_scores) / len(recall_scores) if recall_scores else 0.0
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
    
    total_agent_tokens = sum(agent.token_usage(tid) for tid in all_threads)
    total_prompt_tokens = sum(agent.prompt_token_usage(tid) for tid in all_threads)
    total_compactions = sum(agent.compaction_count(tid) for tid in all_threads)
    
    total_memory_growth = 0
    if hasattr(agent, "memory_file_size"):
        unique_users = set(conv["user_id"] for conv in conversations)
        total_memory_growth = sum(agent.memory_file_size(uid) for uid in unique_users)
        
    return BenchmarkRow(
        agent_name=agent_name,
        agent_tokens_only=total_agent_tokens,
        prompt_tokens_processed=total_prompt_tokens,
        recall_score=avg_recall,
        response_quality=avg_quality,
        memory_growth_bytes=total_memory_growth,
        compactions=total_compactions
    )


def format_rows(rows: list[BenchmarkRow]) -> str:
    """Print a markdown table or tabulated output."""
    headers = [
        "Agent Name",
        "Agent Tokens",
        "Prompt Tokens",
        "Cross-Session Recall",
        "Response Quality",
        "Memory Growth (B)",
        "Compactions"
    ]
    data = []
    for r in rows:
        data.append([
            r.agent_name,
            r.agent_tokens_only,
            r.prompt_tokens_processed,
            f"{r.recall_score:.2%}",
            f"{r.response_quality:.2%}",
            r.memory_growth_bytes,
            r.compactions
        ])
    return tabulate(data, headers=headers, tablefmt="github")


def main() -> None:
    """Run both benchmark suites."""
    config = load_config(Path(__file__).resolve().parent.parent)

    # 1. Load standard and stress datasets
    conversations_std = load_conversations(config.data_dir / "conversations.json")
    conversations_stress = load_conversations(config.data_dir / "advanced_long_context.json")

    print("=== RUNNING STANDARD BENCHMARK ===")
    baseline_std = BaselineAgent(config, force_offline=True)
    advanced_std = AdvancedAgent(config, force_offline=True)
    
    row_baseline_std = run_agent_benchmark("Baseline Agent (Std)", baseline_std, conversations_std, config)
    row_advanced_std = run_agent_benchmark("Advanced Agent (Std)", advanced_std, conversations_std, config)
    
    print(format_rows([row_baseline_std, row_advanced_std]))
    print()

    print("=== RUNNING LONG-CONTEXT STRESS BENCHMARK ===")
    baseline_stress = BaselineAgent(config, force_offline=True)
    
    # Configure lower compact threshold for stress test if needed
    config_stress = load_config(Path(__file__).resolve().parent.parent)
    # The stress turns are very long, standard 1000 threshold will trigger compaction. Let's verify compaction occurs.
    advanced_stress = AdvancedAgent(config_stress, force_offline=True)
    
    row_baseline_stress = run_agent_benchmark("Baseline Agent (Stress)", baseline_stress, conversations_stress, config)
    row_advanced_stress = run_agent_benchmark("Advanced Agent (Stress)", advanced_stress, conversations_stress, config)
    
    print(format_rows([row_baseline_stress, row_advanced_stress]))
    print()



if __name__ == "__main__":
    main()
