from dataclasses import dataclass, field
from typing import Any, List, Dict

@dataclass
class ShopState:
    cart: List[dict] = field(default_factory=list)
    last_results: List[dict] = field(default_factory=list)
    user_id: str = ""

@dataclass
class ToolCallRecord:
    name: str
    args: dict
    result: Any = None

class ToolTracer:
    def __init__(self):
        self.calls: List[ToolCallRecord] = []

    def record(self, name: str, args: dict, result: Any = None) -> None:
        self.calls.append(ToolCallRecord(name=name, args=args, result=result))

    def called(self, name: str) -> bool:
        return any(c.name == name for c in self.calls)

    def get_calls(self, name: str) -> List:
        return [c for c in self.calls if c.name == name]

    def print_trace(self) -> None:
        import json
        print("=== Tool Call Trace ===")
        for i, c in enumerate(self.calls, 1):
            print(f"  {i}. {c.name}({json.dumps(c.args, ensure_ascii=False)[:80]})")
            if c.result is not None:
                print(f"     -> {json.dumps(c.result, ensure_ascii=False)[:100]}")
        print("=====================")

@dataclass
class AgentContext:
    query: str
    max_price: float | None = None
    candidates: List[dict] = field(default_factory=list)
    pros: Dict[str, str] = field(default_factory=dict)
    cons: Dict[str, str] = field(default_factory=dict)
    best: dict | None = None
    cart_result: dict | None = None