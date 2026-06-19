from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProviderConfig:
    """Student TODO: define the provider configuration shared by the agents.

    Required providers for this lab:
    - openai
    - custom (OpenAI-compatible base URL)
    - gemini
    - anthropic
    - ollama
    - openrouter
    """

    provider: str
    model_name: str
    temperature: float
    api_key: str | None = None
    base_url: str | None = None


def normalize_provider(value: str) -> str:
    """Map aliases like `anthorpic` -> `anthropic`."""
    normalized = value.strip().lower()
    mapping = {
        "anthorpic": "anthropic",
        "anthropic": "anthropic",
        "gemini": "gemini",
        "google": "gemini",
        "openai": "openai",
        "ollama": "ollama",
        "openrouter": "openrouter",
        "custom": "custom",
    }
    return mapping.get(normalized, normalized)


def build_chat_model(config: ProviderConfig):
    """Instantiate the real chat model for the selected provider."""
    provider = normalize_provider(config.provider)
    
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=config.model_name,
            temperature=config.temperature,
            openai_api_key=config.api_key,
        )
    elif provider == "custom":
        import httpx
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=config.model_name,
            temperature=config.temperature,
            openai_api_key=config.api_key,
            base_url=config.base_url,
            http_client=httpx.Client(headers={"User-Agent": "python-httpx/0.27.0"}),
        )

    elif provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=config.model_name,
            temperature=config.temperature,
            google_api_key=config.api_key,
        )
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=config.model_name,
            temperature=config.temperature,
            api_key=config.api_key,
        )
    elif provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=config.model_name,
            temperature=config.temperature,
            base_url=config.base_url,
        )
    elif provider == "openrouter":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=config.model_name,
            temperature=config.temperature,
            openai_api_key=config.api_key,
            base_url=config.base_url or "https://openrouter.ai/api/v1",
        )
    else:
        raise ValueError(f"Unsupported provider: {config.provider}")

