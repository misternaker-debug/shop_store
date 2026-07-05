from langchain_gigachat import GigaChat
from langchain_core.messages import AIMessage
from config import GIGACHAT_CREDENTIALS, MODEL_NAME, TEMPERATURE

llm = GigaChat(
    credentials=GIGACHAT_CREDENTIALS,
    scope="GIGACHAT_API_PERS",
    model=MODEL_NAME,
    verify_ssl_certs=False,
    streaming=False,
    temperature=TEMPERATURE
)

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

def llm_chat(messages: list, tools: list | None = None) -> AIMessage:
    """
    Sends the message history to the LLM and returns the model response.

    Parameters:
      messages — list of dialog messages. Each message is a LangChain object:
                   SystemMessage(content="...")   — instruction for the model (agent role)
                   HumanMessage(content="...")    — message from the user
                   AIMessage(...)                 — previous model response
                   ToolMessage(content="...", tool_call_id="...") — tool result

      tools   — list of tool descriptions (OpenAI function calling schema or LangChain tools).

    Returns AIMessage:
      msg.content    — text response (str)
      msg.tool_calls — list of tool calls:
                         "name" — tool name
                         "args" — arguments (already parsed dict)
                         "id"   — unique call identifier
    """
    if tools:
        return llm.bind_tools([search_products, add_to_cart]).invoke(messages)
    return llm.invoke(messages)