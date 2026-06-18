"""
Persistent local memory — stores facts the user tells the AI across sessions.
All data is saved locally in backend/data/memory.json.
"""
import json, re
from pathlib import Path
from datetime import datetime

MEMORY_FILE = Path(__file__).parent / "data" / "memory.json"
MEMORY_FILE.parent.mkdir(exist_ok=True)

_EMPTY = {"facts": [], "preferences": [], "summaries": [], "ai_persona": {}, "version": 1}

_MALE_NAMES = {
    "max", "alex", "leo", "jake", "sam", "ryan", "nathan", "victor", "will",
    "atlas", "james", "john", "david", "mark", "owen", "liam", "noah", "ethan",
}


def detect_gender(name: str) -> str:
    """Return 'female' or 'male' from a name, defaulting to 'female'."""
    return "male" if name.strip().lower() in _MALE_NAMES else "female"


def get_ai_persona() -> dict:
    mem = _load()
    persona = mem.get("ai_persona", {}) or {}
    if not persona.get("name"):
        persona["name"] = "Nova"
    if "gender" not in persona:
        persona["gender"] = detect_gender(persona["name"])
    return persona


def save_ai_persona(persona: dict):
    if persona.get("name") and "gender" not in persona:
        persona["gender"] = detect_gender(persona["name"])
    mem = _load()
    mem["ai_persona"] = persona
    _save(mem)


def _load() -> dict:
    try:
        if MEMORY_FILE.exists():
            return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return dict(_EMPTY)


def _save(mem: dict):
    try:
        MEMORY_FILE.write_text(json.dumps(mem, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def get_memory() -> dict:
    return _load()


def add_fact(fact: str):
    """Store a user-provided fact (e.g. 'my name is Sachin')."""
    fact = fact.strip()
    if not fact:
        return
    mem = _load()
    if fact not in mem["facts"]:
        mem["facts"].append(fact)
        _save(mem)


def add_preference(pref: str):
    """Store a preference (e.g. 'I prefer dark anime art style')."""
    pref = pref.strip()
    if not pref:
        return
    mem = _load()
    if pref not in mem["preferences"]:
        mem["preferences"].append(pref)
        _save(mem)


def add_summary(session_id: str, summary: str):
    """Store a session summary (called after long chats)."""
    mem = _load()
    entry = {
        "session_id": session_id,
        "summary": summary.strip(),
        "date": datetime.now().isoformat()[:10],
    }
    # Keep only last 20 summaries
    mem["summaries"] = [s for s in mem["summaries"] if s.get("session_id") != session_id]
    mem["summaries"].append(entry)
    if len(mem["summaries"]) > 20:
        mem["summaries"] = mem["summaries"][-20:]
    _save(mem)


def clear_memory():
    _save(dict(_EMPTY))


def delete_fact(index: int):
    mem = _load()
    if 0 <= index < len(mem["facts"]):
        mem["facts"].pop(index)
        _save(mem)


def delete_preference(index: int):
    mem = _load()
    if 0 <= index < len(mem["preferences"]):
        mem["preferences"].pop(index)
        _save(mem)


def build_memory_context() -> str:
    """Return a formatted string to inject into the system prompt."""
    mem = _load()
    lines = []
    if mem["facts"]:
        lines.append("USER FACTS (things the user has told you):")
        for f in mem["facts"]:
            lines.append(f"  • {f}")
    if mem["preferences"]:
        lines.append("USER PREFERENCES:")
        for p in mem["preferences"]:
            lines.append(f"  • {p}")
    if mem["summaries"]:
        lines.append("PAST CONVERSATION HIGHLIGHTS (most recent):")
        for s in mem["summaries"][-5:]:
            lines.append(f"  [{s['date']}] {s['summary']}")
    return "\n".join(lines) if lines else ""


def extract_facts_from_message(user_msg: str) -> list[str]:
    """Quick regex pass to auto-detect facts worth remembering."""
    facts = []
    msg = user_msg.strip()
    # Name patterns: "my name is X", "I am X", "call me X"
    for pat in [r"my name is ([A-Z][a-z]+(?: [A-Z][a-z]+)*)",
                r"(?:i am|i'm|call me) ([A-Z][a-z]+(?: [A-Z][a-z]+)*)\b",
                r"I(?:'m| am) (?:from |based in )?([A-Z][a-z]+(?: [A-Z][a-z]+)*)(?:,| and|\.)?"]:
        m = re.search(pat, msg, re.IGNORECASE)
        if m:
            facts.append(f"User name/identity: {m.group(1)}")
            break
    # "I am a/an X" — profession/role
    m = re.search(r"I(?:'m| am) (?:a|an) ([\w\s]{3,30}?)(?:\.|,|\band\b|$)", msg, re.IGNORECASE)
    if m:
        role = m.group(1).strip()
        if 3 < len(role) < 30 and role.lower() not in ("sure", "not", "the", "this"):
            facts.append(f"User is a {role}")
    # "I like/love/prefer X"
    m = re.search(r"I (?:like|love|prefer|enjoy|always use|use) ([\w\s]{3,40}?)(?:\.|,|$)",
                  msg, re.IGNORECASE)
    if m:
        facts.append(f"User prefers: {m.group(1).strip()}")
    return facts
