from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from model_provider import ProviderConfig


import os
from dotenv import load_dotenv

@dataclass
class LabConfig:
    """Shared configuration for the lab."""

    base_dir: Path
    data_dir: Path
    state_dir: Path
    compact_threshold_tokens: int
    compact_keep_messages: int
    model: ProviderConfig
    judge_model: ProviderConfig


def load_config(base_dir: Path | None = None) -> LabConfig:
    """Load environment variables and return a LabConfig."""
    # 1. Resolve the repo root
    root = (base_dir or Path(__file__).resolve().parent.parent).resolve()

    # 2. Load environment variables from .env
    load_dotenv(root / ".env")

    # 3. Create state/ directory if it does not exist
    state_dir = root / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    
    # Also create profiles folder inside state
    (state_dir / "profiles").mkdir(parents=True, exist_ok=True)

    # 4. Resolve provider settings for main model
    antco_key = os.getenv("AntcoAI_LLM_Gateway_API_KEY")
    if antco_key:
        provider = "custom"
        base_url = "https://ai-gateway.antco.ai/v1"
        api_key = antco_key
        model_name = os.getenv("LLM_MODEL", "gemini-3-flash")
    else:
        provider = os.getenv("LLM_PROVIDER", "openai")
        model_name = os.getenv("LLM_MODEL", "gpt-4o-mini")
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        
        if provider == "gemini":
            api_key = os.getenv("GEMINI_API_KEY")
            model_name = os.getenv("LLM_MODEL", "gemini-1.5-flash")
        elif provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            model_name = os.getenv("LLM_MODEL", "claude-3-5-sonnet-latest")
        elif provider == "ollama":
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            model_name = os.getenv("LLM_MODEL", "llama3")
        elif provider == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY")
            model_name = os.getenv("LLM_MODEL", "meta-llama/llama-3-8b-instruct:free")
        elif provider == "custom":
            api_key = os.getenv("CUSTOM_API_KEY")
            base_url = os.getenv("CUSTOM_BASE_URL")

    model_config = ProviderConfig(
        provider=provider,
        model_name=model_name,
        temperature=0.0,
        api_key=api_key,
        base_url=base_url
    )

    # Resolve provider settings for judge model
    if antco_key:
        judge_provider = "custom"
        judge_base_url = "https://ai-gateway.antco.ai/v1"
        judge_api_key = antco_key
        judge_model_name = os.getenv("JUDGE_MODEL", model_name)
    else:
        judge_provider = os.getenv("JUDGE_PROVIDER", provider)
        judge_model_name = os.getenv("JUDGE_MODEL", model_name)
        judge_api_key = os.getenv("JUDGE_API_KEY", api_key)
        judge_base_url = os.getenv("JUDGE_BASE_URL", base_url)

    judge_config = ProviderConfig(
        provider=judge_provider,
        model_name=judge_model_name,
        temperature=0.0,
        api_key=judge_api_key,
        base_url=judge_base_url
    )


    # 5. Sensible defaults for compact memory
    compact_threshold = int(os.getenv("COMPACT_THRESHOLD_TOKENS", "1000"))
    compact_keep = int(os.getenv("COMPACT_KEEP_MESSAGES", "4"))

    return LabConfig(
        base_dir=root,
        data_dir=root / "data",
        state_dir=state_dir,
        compact_threshold_tokens=compact_threshold,
        compact_keep_messages=compact_keep,
        model=model_config,
        judge_model=judge_config
    )

