from langchain.tools import tool
from langchain_core.tools import ToolException
from langgraph.prebuilt import ToolNode


@tool
def get_stock_price(ticker: str) -> float:
    """Get the stock price for a ticker."""

    prices = {
        "AAPL": 225.50,
        "GOOGL": 195.30,
        "MSFT": 510.20,
    }

    if ticker not in prices:
        raise ToolException(
            f"Stock ticker '{ticker}' was not found."
        )

    return prices[ticker]


@tool
def calculate_gain(buy_price: float, sell_price: float) -> float:
    """Calculate the gain from a buy price and sell price."""

    if sell_price < buy_price:
        return "This would be a loss, not a gain."

    return sell_price - buy_price


@tool
def send_report(email: str) -> bool:
    """Send a report to an email address."""
    return True

tools = [
    get_stock_price,
    calculate_gain,
    send_report
]

tool_node = ToolNode(
    tools,
    handle_tool_errors=True
)

print("\n--- ToolNode ---")
print(tool_node)
print("\n--- Valid Stock ---")
print(get_stock_price.invoke({"ticker": "AAPL"}))

print("\n--- Unknown Stock ---")
try:
    print(get_stock_price.invoke({"ticker": "XYZ"}))
except Exception as e:
    print("Caught error:", e)

print("\n--- Valid Gain ---")
print(calculate_gain.invoke({
    "buy_price": 100,
    "sell_price": 150
}))

print("\n--- Loss Case ---")
print(calculate_gain.invoke({
    "buy_price": 150,
    "sell_price": 100
}))

print("\n--- Send Report ---")
print(send_report.invoke({
    "email": "test@example.com"
}))