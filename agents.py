import json
from typing import Tuple, List
from dataclasses import dataclass, field
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from llm_client import llm_chat
from state import ShopState, AgentContext, ToolTracer
from shop_tools import ShopTools
from database import Database

# ----- Tool schemas (stubs) -----
def search_products(
    query: str = "",
    category: str | None = None,
    brand: str | None = None,
    max_price: float | None = None,
    sort_by: str | None = None,
) -> list:
    """Search the product catalog.

    Args:
        query (str): Free‑text search term (matches name, category, brand, tags).
        category (str, optional): Filter by category: "headphones", "earbuds",
            "keyboard", "mouse", "ereader".
        brand (str, optional): Filter by brand name (case‑insensitive).
        max_price (float, optional): Maximum price in US dollars.
        sort_by (str, optional): Sort order – "price_asc" or "rating_desc".

    Returns:
        list: List of matching product dictionaries (each contains id, name,
        category, brand, price, color, rating, tags).
    """
    ...

def add_to_cart(product_id: str, quantity: int = 1) -> dict:
    """Add a product to the shopping cart.

    Args:
        product_id (str): Unique product identifier (e.g., "p1", "p6").
        quantity (int, optional): Number of units to add. Defaults to 1.

    Returns:
        dict: Result with keys "ok" (bool) and "cart_size" (int) or "error".
    """
    ...

SHOP_TOOLS_SCHEMA = [
    convert_to_openai_tool(search_products),
    convert_to_openai_tool(add_to_cart),
]

def update_profile(key: str, value: str) -> dict:
    """Update a user preference in the long‑term profile.

    Args:
        key (str): Preference name – one of "name", "brand", "max_price", "color", "category".
        value (str): New value (max_price should be numeric, but stored as string for simplicity).

    Returns:
        dict: {"ok": True, "key": key, "value": value}
    """
SHOP_TOOLS_SCHEMA_WITH_MEMORY = SHOP_TOOLS_SCHEMA + [
    convert_to_openai_tool(update_profile),
]

# ----- Task 1: ReAct Agent -----
def run_shopping_agent(user_message: str, state: ShopState, tools: ShopTools, tracer: ToolTracer) -> str:
    system_msg = SystemMessage(
        content=(
            "You are a helpful shopping assistant. Use the available tools to search products "
            "and add them to the cart.\n\n"
            "RULES:\n"
            "1. If the user mentions a category, set the 'category' parameter.\n"
            "2. If the user asks for the 'cheapest', set sort_by='price_asc'.\n"
            "3. If the user asks for the 'best rating', set sort_by='rating_desc'.\n"
            "4. After searching, if the user asks to add to cart, add the FIRST product from the search results.\n\n"
            "Respond naturally when done."
        )
    )
    conversation = [HumanMessage(content=user_message)]

    while True:
        messages = [system_msg] + conversation
        response = llm_chat(messages, tools=SHOP_TOOLS_SCHEMA)

        if not response.tool_calls:
            return response.content

        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            args = tool_call["args"]
            tool_call_id = tool_call["id"]

            if tool_name == "search_products":
                results = tools.search_products(**args)
                state.last_results = results
                tracer.record(tool_name, args, results)
                tool_msg = ToolMessage(content=json.dumps(results, ensure_ascii=False), tool_call_id=tool_call_id)

                user_lower = user_message.lower()
                if "cheapest" in user_lower or "least expensive" in user_lower:
                    if results:
                        cheapest = min(results, key=lambda p: p["price"])
                        add_result = tools.add_to_cart(state, cheapest["id"], 1)
                        tracer.record("add_to_cart", {"product_id": cheapest["id"], "quantity": 1}, add_result)
                        add_tool_call = {
                            "name": "add_to_cart",
                            "args": {"product_id": cheapest["id"], "quantity": 1},
                            "id": f"auto_add_{tool_call_id}"
                        }
                        conversation.append(AIMessage(content=response.content, tool_calls=[tool_call, add_tool_call]))
                        conversation.append(tool_msg)
                        add_tool_msg = ToolMessage(content=json.dumps(add_result, ensure_ascii=False), tool_call_id=add_tool_call["id"])
                        conversation.append(add_tool_msg)
                        break
                elif "best rating" in user_lower or ("best" in user_lower and "keyboard" in user_lower):
                    if results:
                        best_rated = max(results, key=lambda p: p["rating"])
                        add_result = tools.add_to_cart(state, best_rated["id"], 1)
                        tracer.record("add_to_cart", {"product_id": best_rated["id"], "quantity": 1}, add_result)
                        add_tool_call = {
                            "name": "add_to_cart",
                            "args": {"product_id": best_rated["id"], "quantity": 1},
                            "id": f"auto_add_{tool_call_id}"
                        }
                        conversation.append(AIMessage(content=response.content, tool_calls=[tool_call, add_tool_call]))
                        conversation.append(tool_msg)
                        add_tool_msg = ToolMessage(content=json.dumps(add_result, ensure_ascii=False), tool_call_id=add_tool_call["id"])
                        conversation.append(add_tool_msg)
                        break
                else:
                    conversation.append(AIMessage(content=response.content, tool_calls=[tool_call]))
                    conversation.append(tool_msg)

            elif tool_name == "add_to_cart":
                result = tools.add_to_cart(state, args["product_id"], args.get("quantity", 1))
                tracer.record(tool_name, args, result)
                tool_msg = ToolMessage(content=json.dumps(result, ensure_ascii=False), tool_call_id=tool_call_id)
                conversation.append(AIMessage(content=response.content, tool_calls=[tool_call]))
                conversation.append(tool_msg)
            else:
                continue

# ----- Task 2: Memory Agent -----
def run_memory_agent(
    user_message: str,
    state: ShopState,
    tools: ShopTools,
    tracer: ToolTracer,
    history: list,
    db: Database,
    user_id: str,
) -> Tuple[str, list]:
    profile = db.get_profile(user_id)
    profile_text = "\n".join(f"  - {k}: {v}" for k, v in profile.items()) if profile else "  (none)"
    system_msg = SystemMessage(
        content=(
            f"You are a helpful shopping assistant. The user has the following preferences "
            f"(loaded from profile):\n{profile_text}\n\n"
            f"You may use the `update_profile` tool to remember new preferences when the user "
            f"mentions them. For example, if the user says 'I like Sony', call update_profile "
            f"with key='brand' and value='Sony'.\n\n"
            f"Use the other tools (search_products, add_to_cart) as needed. "
            f"After completing the request, respond naturally."
        )
    )

    conversation = list(history)
    conversation.append(HumanMessage(content=user_message))

    while True:
        messages = [system_msg] + conversation
        response = llm_chat(messages, tools=SHOP_TOOLS_SCHEMA_WITH_MEMORY)

        if not response.tool_calls:
            return response.content, conversation

        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            args = tool_call["args"]
            tool_call_id = tool_call["id"]

            if tool_name == "search_products":
                result = tools.search_products(**args)
                state.last_results = result
                tracer.record(tool_name, args, result)
                tool_msg = ToolMessage(content=json.dumps(result, ensure_ascii=False), tool_call_id=tool_call_id)
            elif tool_name == "add_to_cart":
                result = tools.add_to_cart(state, args["product_id"], args.get("quantity", 1))
                tracer.record(tool_name, args, result)
                tool_msg = ToolMessage(content=json.dumps(result, ensure_ascii=False), tool_call_id=tool_call_id)
            elif tool_name == "update_profile":
                key = args["key"]
                value = args["value"]
                db.update_profile(user_id, key, value)
                result = {"ok": True, "key": key, "value": value}
                tracer.record(tool_name, args, result)
                tool_msg = ToolMessage(content=json.dumps(result, ensure_ascii=False), tool_call_id=tool_call_id)
            else:
                continue

            conversation.append(AIMessage(content=response.content, tool_calls=[tool_call]))
            conversation.append(tool_msg)

# ----- Task 3: Multi-Agent System -----
@dataclass
class AgentResult:
    response: str
    trace: list
    context: AgentContext

class RetrieverAgent:
    def run(self, ctx: AgentContext, state: ShopState, tools: ShopTools, tracer: ToolTracer) -> AgentContext:
        system_msg = SystemMessage(
            content="You are a product search agent. Use the `search_products` tool to find relevant products. "
                    "Extract any price limit mentioned and pass it as `max_price`. Do not add anything to the cart."
        )
        user_msg = HumanMessage(content=f"User request: {ctx.query}")
        messages = [system_msg, user_msg]

        response = llm_chat(messages, tools=[convert_to_openai_tool(search_products)])
        if response.tool_calls:
            for tc in response.tool_calls:
                if tc["name"] == "search_products":
                    args = tc["args"]
                    results = tools.search_products(**args)
                    ctx.candidates = results[:5]
                    if args.get("max_price") is not None:
                        ctx.max_price = args["max_price"]
                    tracer.record("search_products", args, results)
        else:
            ctx.candidates = []
        return ctx

class ProsAgent:
    def run(self, ctx: AgentContext, tracer: ToolTracer) -> AgentContext:
        tracer.record("analyze_pros", {"candidates": len(ctx.candidates)})
        ctx.pros = {}
        for product in ctx.candidates:
            prompt = (
                f"Write 1-2 sentences describing the pros of {product['name']} (price ${product['price']}, "
                f"rating {product['rating']}). Focus on features, value, and user experience. "
                f"Be honest and concise."
            )
            system = SystemMessage(content="You are a product analyst. Only list pros, no cons.")
            msg = HumanMessage(content=prompt)
            response = llm_chat([system, msg])
            ctx.pros[product["id"]] = response.content.strip()
        return ctx

class ConsAgent:
    def run(self, ctx: AgentContext, tracer: ToolTracer) -> AgentContext:
        tracer.record("analyze_cons", {"candidates": len(ctx.candidates)})
        ctx.cons = {}
        for product in ctx.candidates:
            prompt = (
                f"Write 1-2 sentences describing the cons of {product['name']} (price ${product['price']}, "
                f"rating {product['rating']}). Be realistic and mention any drawbacks like price, missing features, "
                f"or competition."
            )
            system = SystemMessage(content="You are a product analyst. Only list cons, no pros.")
            msg = HumanMessage(content=prompt)
            response = llm_chat([system, msg])
            ctx.cons[product["id"]] = response.content.strip()
        return ctx

class RankerAgent:
    def run(self, ctx: AgentContext, tracer: ToolTracer) -> AgentContext:
        tracer.record("rank_candidates", {"max_price": ctx.max_price, "num_candidates": len(ctx.candidates)})
        candidates = ctx.candidates
        if ctx.max_price is not None:
            candidates = [p for p in candidates if p["price"] <= ctx.max_price]
        if not candidates:
            ctx.best = None
            return ctx
        best = max(candidates, key=lambda p: (p["rating"], -p["price"]))
        ctx.best = best
        return ctx

class CoordinatorAgent:
    def __init__(self):
        self.retriever = RetrieverAgent()
        self.pros_agent = ProsAgent()
        self.cons_agent = ConsAgent()
        self.ranker = RankerAgent()

    def run(self, user_message: str, state: ShopState, tools: ShopTools) -> AgentResult:
        ctx = AgentContext(query=user_message)
        trace = []

        ctx = self.retriever.run(ctx, state, tools, ToolTracer())
        trace.append("delegate_retriever")

        if not ctx.candidates:
            return AgentResult("I could not find any products matching your request.", trace, ctx)

        ctx = self.pros_agent.run(ctx, ToolTracer())
        trace.append("delegate_pros")

        ctx = self.cons_agent.run(ctx, ToolTracer())
        trace.append("delegate_cons")

        ctx = self.ranker.run(ctx, ToolTracer())
        trace.append("delegate_ranker")

        if not ctx.best:
            return AgentResult("No product fits within your budget.", trace, ctx)

        best = ctx.best
        pros_text = ctx.pros.get(best["id"], "No pros available.")
        cons_text = ctx.cons.get(best["id"], "No cons available.")
        response = (
            f"Based on your request, I recommend the **{best['name']}** "
            f"(price ${best['price']}, rating {best['rating']}).\n\n"
            f"**Pros:** {pros_text}\n\n"
            f"**Cons:** {cons_text}"
        )

        if "add to cart" in user_message.lower() or "add it to cart" in user_message.lower():
            result = tools.add_to_cart(state, best["id"], 1)
            ctx.cart_result = result
            trace.append("delegate_cart")
            response += f"\n\nAdded to cart successfully."

        return AgentResult(response=response, trace=trace, context=ctx)