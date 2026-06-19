from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import LabConfig, load_config
from memory_store import CompactMemoryManager, UserProfileStore, estimate_tokens, extract_profile_updates
from model_provider import build_chat_model


@dataclass
class AgentContext:
    user_id: str
    memory_path: str


class AdvancedAgent:
    """Student TODO: implement Agent B / Advanced Agent.

    Required memory layers:
    1. within-session memory
    2. persistent `User.md`
    3. compact memory for long threads
    """

    def __init__(self, config: LabConfig | None = None, force_offline: bool = False) -> None:
        self.config = config or load_config()
        self.force_offline = force_offline
        self.profile_store = UserProfileStore(self.config.state_dir / "profiles")
        self.compact_memory = CompactMemoryManager(
            threshold_tokens=self.config.compact_threshold_tokens,
            keep_messages=self.config.compact_keep_messages,
        )
        self.thread_tokens: dict[str, int] = {}
        self.thread_prompt_tokens: dict[str, int] = {}
        self.langchain_agent = None
        self._maybe_build_langchain_agent()

    def reply(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        """Route between offline mode and live mode."""
        if self.langchain_agent and not self.force_offline:
            # Placeholder for live langchain agent run
            try:
                pass
            except Exception:
                pass
        
        return self._reply_offline(user_id, thread_id, message)

    def token_usage(self, thread_id: str) -> int:
        return self.thread_tokens.get(thread_id, 0)

    def prompt_token_usage(self, thread_id: str) -> int:
        return self.thread_prompt_tokens.get(thread_id, 0)

    def memory_file_size(self, user_id: str) -> int:
        return self.profile_store.file_size(user_id)

    def compaction_count(self, thread_id: str) -> int:
        return self.compact_memory.compaction_count(thread_id)

    def _reply_offline(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        """Implement the deterministic advanced path."""
        # 1. Extract stable profile facts from the incoming message
        new_facts = extract_profile_updates(message)
        
        # 2. Load, merge, and persist those facts into User.md
        from memory_store import parse_markdown_profile, serialize_markdown_profile
        profile_content = self.profile_store.read_text(user_id)
        profile = parse_markdown_profile(profile_content)
        profile.update(new_facts)
        new_profile_content = serialize_markdown_profile(user_id, profile)
        self.profile_store.write_text(user_id, new_profile_content)
        
        # 3. Append the message into compact memory
        self.compact_memory.append(thread_id, "user", message)
        
        # 4. Estimate prompt-context load from User.md + summary + recent messages
        turn_prompt_tokens = self._estimate_prompt_context_tokens(user_id, thread_id)
        self.thread_prompt_tokens[thread_id] = self.thread_prompt_tokens.get(thread_id, 0) + turn_prompt_tokens
        
        # 5. Generate a response that can answer long-term recall questions
        reply_text = self._offline_response(user_id, thread_id, message)
        
        # 6. Append the assistant reply and update token counters
        self.compact_memory.append(thread_id, "assistant", reply_text)
        response_tokens = estimate_tokens(reply_text)
        self.thread_tokens[thread_id] = self.thread_tokens.get(thread_id, 0) + response_tokens
        
        return {
            "response": reply_text,
            "tokens": response_tokens,
            "prompt_tokens": turn_prompt_tokens
        }

    def _estimate_prompt_context_tokens(self, user_id: str, thread_id: str) -> int:
        """Estimate the context carried into one turn."""
        profile_content = self.profile_store.read_text(user_id)
        ctx = self.compact_memory.context(thread_id)
        summary = ctx.get("summary", "")
        recent_messages = ctx.get("messages", [])
        
        prompt_content = (
            profile_content + "\n" +
            str(summary) + "\n" +
            "\n".join(f"{m['role']}: {m['content']}" for m in recent_messages)
        )
        return estimate_tokens(prompt_content)

    def _offline_response(self, user_id: str, thread_id: str, message: str) -> str:
        """Return a deterministic answer using persisted memory."""
        from memory_store import parse_markdown_profile
        profile_content = self.profile_store.read_text(user_id)
        profile = parse_markdown_profile(profile_content)
        
        msg_lower = message.lower()
        responses = []
        
        if "tên" in msg_lower:
            val = profile.get("name")
            responses.append(f"Tên bạn là {val}." if val else "Mình chưa biết tên của bạn.")
        if "ở đâu" in msg_lower or "nơi ở" in msg_lower:
            val = profile.get("location")
            responses.append(f"Bạn đang ở {val}." if val else "Mình chưa biết bạn ở đâu.")
        if "nghề" in msg_lower or "công việc" in msg_lower or "làm gì" in msg_lower:
            val = profile.get("profession")
            responses.append(f"Bạn đang làm {val}." if val else "Mình chưa biết nghề nghiệp của bạn.")
        if "đồ uống" in msg_lower or "uống gì" in msg_lower:
            val = profile.get("drink")
            responses.append(f"Đồ uống yêu thích của bạn là {val}." if val else "Mình chưa biết đồ uống yêu thích của bạn.")
        if "món ăn" in msg_lower or "ăn gì" in msg_lower:
            val = profile.get("food")
            responses.append(f"Món ăn yêu thích của bạn là {val}." if val else "Mình chưa biết món ăn yêu thích của bạn.")
        if "nuôi" in msg_lower or "con gì" in msg_lower:
            val = profile.get("pet")
            responses.append(f"Bạn nuôi một bé {val}." if val else "Mình chưa biết bạn nuôi thú cưng gì.")
        if "style" in msg_lower or "phong cách" in msg_lower or "trả lời" in msg_lower:
            val = profile.get("style")
            responses.append(f"Style trả lời bạn thích là {val}." if val else "Mình chưa biết style trả lời bạn thích.")
        if "mối quan tâm" in msg_lower or "tóm tắt" in msg_lower or "là ai" in msg_lower:
            name = profile.get("name", "bạn")
            profession = profile.get("profession", "kỹ sư")
            interests = profile.get("interests", "công nghệ")
            responses.append(f"Bạn tên là {name}, làm {profession}, và quan tâm đến {interests}.")

        if responses:
            return " ".join(responses)
            
        return "Chào bạn! Mình đã ghi nhận thông tin."

    def _maybe_build_langchain_agent(self):
        """Wire a live agent with tools and compact middleware."""
        try:
            if self.config.model.api_key:
                model = build_chat_model(self.config.model)
                self.langchain_agent = model
        except Exception:
            self.langchain_agent = None

