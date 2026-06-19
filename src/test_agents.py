from __future__ import annotations

from pathlib import Path

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from config import load_config


def make_config(tmp_path: Path) -> LabConfig:
    """Build an isolated config for tests."""
    from config import LabConfig
    from model_provider import ProviderConfig

    model_config = ProviderConfig(
        provider="openai",
        model_name="gpt-4o-mini",
        temperature=0.0,
        api_key="test-api-key",
        base_url=None
    )

    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "profiles").mkdir(parents=True, exist_ok=True)

    return LabConfig(
        base_dir=tmp_path,
        data_dir=Path(__file__).resolve().parent.parent / "data",
        state_dir=state_dir,
        compact_threshold_tokens=50,  # Low threshold so compaction triggers easily in tests
        compact_keep_messages=2,
        model=model_config,
        judge_model=model_config
    )


def test_user_markdown_read_write_edit(tmp_path: Path) -> None:
    """Verify `User.md` can be created, updated, and edited."""
    config = make_config(tmp_path)
    from memory_store import UserProfileStore
    store = UserProfileStore(config.state_dir / "profiles")

    user_id = "test_user"
    content = "# User Profile: test_user\n\n- **Name**: DũngCT\n"

    # 1. Write profile
    path = store.write_text(user_id, content)
    assert path.exists()
    assert store.file_size(user_id) > 0

    # 2. Read profile
    read_val = store.read_text(user_id)
    assert "DũngCT" in read_val

    # 3. Edit profile
    edited = store.edit_text(user_id, "DũngCT", "DũngCT Edited")
    assert edited is True

    # 4. Verify edit
    read_val_edited = store.read_text(user_id)
    assert "DũngCT Edited" in read_val_edited


def test_compact_trigger(tmp_path: Path) -> None:
    """Verify long threads trigger compaction."""
    config = make_config(tmp_path)
    from memory_store import CompactMemoryManager
    manager = CompactMemoryManager(
        threshold_tokens=config.compact_threshold_tokens,
        keep_messages=config.compact_keep_messages
    )

    thread_id = "test_thread"

    # Append first message (approx 25 tokens)
    manager.append(thread_id, "user", "A" * 100)
    assert manager.compaction_count(thread_id) == 0

    # Append second message (approx 25 tokens, total 50 tokens)
    manager.append(thread_id, "assistant", "B" * 100)

    # Append third message (triggers compaction as total tokens > 50)
    manager.append(thread_id, "user", "C" * 100)
    assert manager.compaction_count(thread_id) > 0

    # Verify state matches expected structure
    ctx = manager.context(thread_id)
    assert ctx["summary"] != ""
    assert len(ctx["messages"]) == config.compact_keep_messages


def test_cross_session_recall(tmp_path: Path) -> None:
    """Verify advanced remembers across sessions and baseline does not."""
    config = make_config(tmp_path)

    baseline = BaselineAgent(config, force_offline=True)
    advanced = AdvancedAgent(config, force_offline=True)

    user_id = "dungct_test"

    # Thread 1: Introduction of name
    thread_1 = "thread-1"
    baseline.reply(user_id, thread_1, "Chào bạn, mình tên là DũngCT.")
    advanced.reply(user_id, thread_1, "Chào bạn, mình tên là DũngCT.")

    # Thread 2: Recall name question in a fresh thread
    thread_2 = "thread-2"
    res_baseline = baseline.reply(user_id, thread_2, "Tên mình là gì?")
    res_advanced = advanced.reply(user_id, thread_2, "Tên mình là gì?")

    # Baseline has only within-session memory and should fail to recall
    assert "DũngCT" not in res_baseline["response"]
    # Advanced has persistent memory and should successfully recall
    assert "DũngCT" in res_advanced["response"]


def test_compact_reduces_prompt_load_on_long_thread(tmp_path: Path) -> None:
    """Compare prompt load of baseline vs advanced on a long thread."""
    config = make_config(tmp_path)

    baseline = BaselineAgent(config, force_offline=True)
    advanced = AdvancedAgent(config, force_offline=True)

    user_id = "dungct_stress_test"
    thread_id = "long-thread"

    # Feed a series of long turns to trigger compaction on AdvancedAgent
    for i in range(10):
        baseline.reply(user_id, thread_id, f"Thông tin phụ số {i}: " + "X" * 150)
        advanced.reply(user_id, thread_id, f"Thông tin phụ số {i}: " + "X" * 150)

    p_baseline = baseline.prompt_token_usage(thread_id)
    p_advanced = advanced.prompt_token_usage(thread_id)

    # AdvancedAgent prompt token load should be significantly optimized by compaction
    assert p_advanced < p_baseline

