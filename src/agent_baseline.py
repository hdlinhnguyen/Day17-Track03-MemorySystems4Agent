from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config import LabConfig, load_config
from memory_store import estimate_tokens
from model_provider import build_chat_model


@dataclass
class SessionState:
    messages: list[dict[str, str]] = field(default_factory=list)
    token_usage: int = 0
    prompt_tokens_processed: int = 0


class BaselineAgent:
    """Student TODO: implement Agent A.

    Requirements:
    - Within-session memory only
    - No persistent `User.md`
    - Should forget long-term facts across new threads
    """

    def __init__(self, config: LabConfig | None = None, force_offline: bool = False) -> None:
        self.config = config or load_config()
        self.force_offline = force_offline
        self.sessions: dict[str, SessionState] = {}
        self.langchain_agent = None
        self._maybe_build_langchain_agent()

    def reply(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        """Return the agent response and token accounting."""
        if self.langchain_agent and not self.force_offline:
            # Placeholder for live langchain agent run
            try:
                # We could run the real agent here
                pass
            except Exception:
                pass
        
        return self._reply_offline(thread_id, message)

    def token_usage(self, thread_id: str) -> int:
        # Return cumulative agent token count for one thread.
        if thread_id not in self.sessions:
            return 0
        return self.sessions[thread_id].token_usage

    def prompt_token_usage(self, thread_id: str) -> int:
        # Estimate how much prompt context this baseline kept processing.
        if thread_id not in self.sessions:
            return 0
        return self.sessions[thread_id].prompt_tokens_processed

    def compaction_count(self, thread_id: str) -> int:
        # Baseline has no compact memory.
        return 0

    def _reply_offline(self, thread_id: str, message: str) -> dict[str, Any]:
        """Implement a simple offline behavior."""
        if thread_id not in self.sessions:
            self.sessions[thread_id] = SessionState()
        session = self.sessions[thread_id]
        
        # 1. Append user message
        session.messages.append({"role": "user", "content": message})
        
        # 2. Estimate prompt tokens processed (entire conversation history in the session)
        prompt_content = "\n".join(f"{m['role']}: {m['content']}" for m in session.messages)
        turn_prompt_tokens = estimate_tokens(prompt_content)
        session.prompt_tokens_processed += turn_prompt_tokens
        
        # 3. Determine if this is a recall question
        msg_lower = message.lower()
        question_indicators = ["?", "nhắc lại", "là gì", "ở đâu", "uống gì", "ăn gì", "làm gì", "không nhỉ", "có nhớ", "con gì", "style gì", "tóm tắt"]
        is_question = any(ind in msg_lower for ind in question_indicators)
        
        if is_question:
            # Extract facts from history of this thread
            facts = {}
            for msg in session.messages:
                if msg["role"] == "user":
                    from memory_store import extract_profile_updates
                    extracted = extract_profile_updates(msg["content"])
                    facts.update(extracted)
            
            responses = []
            if "tên" in msg_lower:
                val = facts.get("name")
                responses.append(f"Tên bạn là {val}." if val else "Mình chưa biết tên của bạn.")
            if "ở đâu" in msg_lower or "nơi ở" in msg_lower:
                val = facts.get("location")
                responses.append(f"Bạn đang ở {val}." if val else "Mình chưa biết bạn ở đâu.")
            if "nghề" in msg_lower or "công việc" in msg_lower or "làm gì" in msg_lower:
                val = facts.get("profession")
                responses.append(f"Bạn đang làm {val}." if val else "Mình chưa biết nghề nghiệp của bạn.")
            if "đồ uống" in msg_lower or "uống gì" in msg_lower:
                val = facts.get("drink")
                responses.append(f"Đồ uống yêu thích của bạn là {val}." if val else "Mình chưa biết đồ uống yêu thích của bạn.")
            if "món ăn" in msg_lower or "ăn gì" in msg_lower:
                val = facts.get("food")
                responses.append(f"Món ăn yêu thích của bạn là {val}." if val else "Mình chưa biết món ăn yêu thích của bạn.")
            if "nuôi" in msg_lower or "con gì" in msg_lower:
                val = facts.get("pet")
                responses.append(f"Bạn nuôi một bé {val}." if val else "Mình chưa biết bạn nuôi thú cưng gì.")
            if "style" in msg_lower or "phong cách" in msg_lower or "trả lời" in msg_lower:
                val = facts.get("style")
                responses.append(f"Style trả lời bạn thích là {val}." if val else "Mình chưa biết style trả lời bạn thích.")
            if "mối quan tâm" in msg_lower or "tóm tắt" in msg_lower or "là ai" in msg_lower:
                name = facts.get("name", "bạn")
                profession = facts.get("profession", "kỹ sư")
                interests = facts.get("interests", "công nghệ")
                responses.append(f"Bạn tên là {name}, làm {profession}, và quan tâm đến {interests}.")

            if responses:
                reply_text = " ".join(responses)
            else:
                reply_text = "Xin lỗi, mình không có thông tin này trong thread hiện tại."
        else:
            reply_text = "Chào bạn! Mình đã ghi nhận thông tin."
            
        # 4. Append assistant response and update token usage
        session.messages.append({"role": "assistant", "content": reply_text})
        response_tokens = estimate_tokens(reply_text)
        session.token_usage += response_tokens
        
        return {
            "response": reply_text,
            "tokens": response_tokens,
            "prompt_tokens": turn_prompt_tokens
        }

    def _maybe_build_langchain_agent(self):
        """Optionally wire `create_agent` + `InMemorySaver` here."""
        try:
            if self.config.model.api_key:
                # Build chat model from provider config
                model = build_chat_model(self.config.model)
                self.langchain_agent = model
        except Exception:
            self.langchain_agent = None

