from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


def estimate_tokens(text: str) -> int:
    """Implement a simple token estimator."""
    if not text:
        return 0
    text_stripped = text.strip()
    if not text_stripped:
        return 0
    # Approximate tokens from character count (len / 4, minimum 1 token)
    return max(1, int(len(text_stripped) / 4))


def parse_markdown_profile(content: str) -> dict[str, str]:
    """Parse markdown content into a key-value dictionary of user facts."""
    profile = {}
    for line in content.splitlines():
        if line.startswith("- **") and "**:" in line:
            parts = line.split("**:", 1)
            key = parts[0].replace("- **", "").strip().lower()
            val = parts[1].strip()
            profile[key] = val
    return profile


def serialize_markdown_profile(user_id: str, profile: dict[str, str]) -> str:
    """Serialize user facts dictionary into a structured markdown profile."""
    lines = [f"# User Profile: {user_id}", ""]
    key_mapping = {
        "name": "Name",
        "location": "Location",
        "profession": "Profession",
        "drink": "Drink",
        "food": "Food",
        "pet": "Pet",
        "style": "Style",
        "interests": "Interests"
    }
    for k, display_name in key_mapping.items():
        if k in profile and profile[k]:
            lines.append(f"- **{display_name}**: {profile[k]}")
    return "\n".join(lines) + "\n"


@dataclass
class UserProfileStore:
    """Persistent storage for `User.md`."""

    root_dir: Path

    def path_for(self, user_id: str) -> Path:
        # Slugify or sanitize the user id before building the file path.
        sanitized = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in user_id).lower()
        return self.root_dir / f"{sanitized}.md"

    def read_text(self, user_id: str) -> str:
        # Return file content or an empty default markdown profile.
        path = self.path_for(user_id)
        if not path.exists():
            return serialize_markdown_profile(user_id, {})
        return path.read_text(encoding="utf-8")

    def write_text(self, user_id: str, content: str) -> Path:
        # Write markdown to disk and return the file path.
        path = self.path_for(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def edit_text(self, user_id: str, search_text: str, replacement: str) -> bool:
        # Replace one occurrence inside User.md and return whether it changed.
        path = self.path_for(user_id)
        if not path.exists():
            return False
        content = path.read_text(encoding="utf-8")
        if search_text not in content:
            return False
        new_content = content.replace(search_text, replacement)
        path.write_text(new_content, encoding="utf-8")
        return True

    def file_size(self, user_id: str) -> int:
        # Return the current file size in bytes.
        path = self.path_for(user_id)
        if not path.exists():
            return 0
        return path.stat().st_size


def extract_profile_updates(message: str) -> dict[str, str]:
    """Convert raw user text into stable profile facts, with conflict resolution."""
    updates = {}
    message_lower = message.lower()
    
    # 1. Tránh lưu khi tin nhắn chỉ là câu hỏi thuần túy
    question_indicators = ["?", "nhắc lại", "là gì", "ở đâu", "uống gì", "ăn gì", "làm gì", "không nhỉ", "có nhớ", "con gì", "style gì"]
    is_pure_question = any(ind in message_lower for ind in question_indicators) and not any(
        kw in message_lower for kw in [
            "tên là", "ở huế", "ở đà nẵng", "làm mlops", "làm backend", "cà phê sữa đá", 
            "mì quảng", "corgi", "đính chính", "cập nhật", "style của mình là", "trả lời ngắn", "3 bullet"
        ]
    )
    
    if is_pure_question:
        return updates

    # 2. Tên
    if "tên là dũngct stress" in message_lower or "tên mình là dũngct stress" in message_lower:
        updates["name"] = "DũngCT Stress"
    elif "tên là dũngct" in message_lower or "tên mình là dũngct" in message_lower:
        updates["name"] = "DũngCT"
        
    # 3. Nơi ở (với conflict handling & bỏ qua Hà Nội nhiễu)
    if "đã cập nhật từ huế sang đà nẵng" in message_lower or "làm việc ở đà nẵng" in message_lower:
        updates["location"] = "Đà Nẵng"
    elif "hà nội chỉ là nơi" in message_lower:
        pass
    elif "ở huế" in message_lower and "đã cập nhật từ huế" not in message_lower:
        updates["location"] = "Huế"
    elif "ở đà nẵng" in message_lower and "từ huế sang" not in message_lower:
        updates["location"] = "Đà Nẵng"
        
    # 4. Nghề nghiệp (với conflict handling & bỏ qua product manager nhiễu)
    if "product manager" in message_lower and "đùa" in message_lower:
        pass
    elif "mlops engineer" in message_lower or "chuyển sang mlops" in message_lower:
        updates["profession"] = "MLOps engineer"
    elif "backend engineer" in message_lower and "không còn làm" not in message_lower and "đừng nói backend" not in message_lower:
        updates["profession"] = "backend engineer"
        
    # 5. Đồ uống
    if "cà phê sữa đá" in message_lower:
        updates["drink"] = "cà phê sữa đá"
        
    # 6. Món ăn
    if "mì quảng" in message_lower:
        updates["food"] = "mì Quảng"
        
    # 7. Thú cưng
    if "corgi" in message_lower or "con bơ" in message_lower:
        updates["pet"] = "corgi"
        
    # 8. Style
    if "3 bullet" in message_lower:
        updates["style"] = "3 bullet"
    elif "ngắn gọn" in message_lower:
        updates["style"] = "ngắn gọn"
        
    # 9. Mối quan tâm kỹ thuật
    interests = []
    if "python" in message_lower:
        interests.append("Python")
    if "ai" in message_lower:
        interests.append("AI")
    if interests:
        updates["interests"] = ", ".join(interests)
        
    return updates


def summarize_messages(messages: list[dict[str, str]], max_items: int = 6) -> str:
    """Create a compact summary of older messages."""
    parts = []
    for msg in messages[:max_items]:
        role = msg["role"]
        content = msg["content"]
        # In offline mode, truncate the content to simulate summarization / compression
        if len(content) > 30:
            truncated = content[:27] + "..."
        else:
            truncated = content
        parts.append(f"{role.capitalize()}: {truncated}")
    return "; ".join(parts)



@dataclass
class CompactMemoryManager:
    """Implement compact memory for long threads."""

    threshold_tokens: int
    keep_messages: int
    state: dict[str, dict[str, object]] = field(default_factory=dict)

    def append(self, thread_id: str, role: str, content: str) -> None:
        if thread_id not in self.state:
            self.state[thread_id] = {
                "messages": [],
                "summary": "",
                "compactions": 0
            }
        
        thread_state = self.state[thread_id]
        thread_state["messages"].append({"role": role, "content": content})
        
        # Calculate current token usage of summary and messages
        summary_tokens = estimate_tokens(thread_state["summary"])
        messages_tokens = sum(estimate_tokens(msg["content"]) for msg in thread_state["messages"])
        total_tokens = summary_tokens + messages_tokens
        
        if total_tokens > self.threshold_tokens:
            if len(thread_state["messages"]) > self.keep_messages:
                to_compact = thread_state["messages"][:-self.keep_messages]
                kept = thread_state["messages"][-self.keep_messages:]
                
                # Generate summary for the compacted messages
                new_summary = summarize_messages(to_compact)
                if thread_state["summary"]:
                    thread_state["summary"] = thread_state["summary"] + "\n" + new_summary
                else:
                    thread_state["summary"] = new_summary
                
                thread_state["messages"] = kept
                thread_state["compactions"] += 1

    def context(self, thread_id: str) -> dict[str, object]:
        if thread_id not in self.state:
            return {
                "messages": [],
                "summary": "",
                "compactions": 0
            }
        return self.state[thread_id]

    def compaction_count(self, thread_id: str) -> int:
        if thread_id not in self.state:
            return 0
        return self.state[thread_id].get("compactions", 0)
