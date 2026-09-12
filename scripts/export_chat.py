#!/usr/bin/env python3
"""
MedFusion AI — Full Chat History Exporter.

Extracts complete conversations across all project sessions from Day 1
into a unified, readable Markdown document.
"""

import json
from pathlib import Path

sessions_dir = Path.home() / ".claude-omniroute" / "projects" / "C--Users-RITESH-YADAV-desktop-ai-diagnosis"
output_path = Path(__file__).resolve().parent.parent / "SESSION_CHAT.md"

session_files = sorted(sessions_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)

print(f"Found {len(session_files)} session files in {sessions_dir}")
output_lines = ["# MedFusion AI — Complete Project Conversation History (All Sessions)\n\n"]

for idx, sf in enumerate(session_files):
    output_lines.append(f"\n\n# ============================================================\n")
    output_lines.append(f"# Session Part {idx + 1} ({sf.name})\n")
    output_lines.append(f"# ============================================================\n\n")

    with open(sf, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except Exception:
                continue

            entry_type = data.get("type") or data.get("role")

            if entry_type == "user":
                content = data.get("message", {}).get("content") or data.get("content")
                text = ""
                if isinstance(content, list):
                    text = "\n".join(
                        item.get("text", "")
                        for item in content
                        if isinstance(item, dict) and item.get("type") == "text"
                    )
                elif isinstance(content, str):
                    text = content

                if text:
                    if "This session is being continued from a previous conversation" in text:
                        output_lines.append("### 📌 [Progress Milestone / Context Compaction]\n\n")
                        output_lines.append(f"{text.strip()}\n\n---\n\n")
                    elif not text.startswith("CRITICAL: Respond with TEXT ONLY") and not text.startswith("<local-command"):
                        output_lines.append(f"## 👤 User\n\n{text.strip()}\n\n---\n\n")

            elif entry_type == "assistant":
                content = data.get("message", {}).get("content") or data.get("content")
                text = ""
                if isinstance(content, list):
                    text_parts = [
                        item.get("text", "")
                        for item in content
                        if isinstance(item, dict) and item.get("type") == "text"
                    ]
                    text = "\n".join(text_parts)
                elif isinstance(content, str):
                    text = content

                if text.strip() and not text.strip().startswith("I will read") and not text.strip().startswith("Let me"):
                    output_lines.append(f"## 🤖 Claude\n\n{text.strip()}\n\n---\n\n")

with open(output_path, "w", encoding="utf-8") as f:
    f.writelines(output_lines)

print(f"✓ Successfully exported full chat history to: {output_path} ({output_path.stat().st_size / 1024:.1f} KB)")
