from langchain.tools import tool
from langchain_core.tools import ToolException


@tool
def check_stock(sku: str) -> dict:
    """Check the current stock level for a product SKU."""

    stock = {
        "SKU-001": {
            "name": "Widget A",
            "quantity": 150,
            "warehouse": "WH-North"
        },
        "SKU-002": {
            "name": "Widget B",
            "quantity": 12,
            "warehouse": "WH-South"
        },
        "SKU-003": {
            "name": "Gadget X",
            "quantity": 0,
            "warehouse": "WH-North"
        },
    }

    if sku not in stock:
        raise ToolException(f"Unknown SKU: {sku}")

    return stock[sku]


print("Valid SKU:")
print(check_stock.invoke({"sku": "SKU-002"}))

print("\nUnknown SKU:")
try:
    print(check_stock.invoke({"sku": "SKU-999"}))
except Exception as e:
    print("Caught error:", e)


@tool
def place_order(sku: str, quantity: int) -> str:
    """Place an order for a product."""

    if quantity > 500:
        raise ToolException(
            "Cannot place order: maximum order is 500 units"
        )

    return f"Order ORD-{sku}-{quantity} placed successfully."    
print("\n--- Place Order ---")

print("Valid order:")
print(place_order.invoke({
    "sku": "SKU-001",
    "quantity": 100
}))

print("\nOver-limit order:")
try:
    print(place_order.invoke({
        "sku": "SKU-001",
        "quantity": 600
    }))
except Exception as e:
    print("Caught error:", e)

@tool
def get_low_stock_report() -> list:
    """Return all products with less than 20 units in stock."""

    stock = {
        "SKU-001": {
            "name": "Widget A",
            "quantity": 150,
            "warehouse": "WH-North"
        },
        "SKU-002": {
            "name": "Widget B",
            "quantity": 12,
            "warehouse": "WH-South"
        },
        "SKU-003": {
            "name": "Gadget X",
            "quantity": 0,
            "warehouse": "WH-North"
        },
    }

    return [
        {
            "sku": sku,
            **details
        }
        for sku, details in stock.items()
        if details["quantity"] < 20
    ]


print("\n--- Low Stock Report ---")
print(get_low_stock_report.invoke({}))


@tool
def calculate_restock_cost(
    sku: str,
    units_to_order: int,
    unit_cost: float
) -> float | str:
    """Calculate the cost of restocking a product."""

    if units_to_order < 0 or unit_cost < 0:
        return "Invalid input: all values must be positive."

    return units_to_order * unit_cost
print("\n--- Restock Cost ---")

print("Valid calculation:")
print(calculate_restock_cost.invoke({
    "sku": "SKU-001",
    "units_to_order": 10,
    "unit_cost": 10
}))

print("\nNegative units:")
print(calculate_restock_cost.invoke({
    "sku": "SKU-001",
    "units_to_order": -5,
    "unit_cost": 10
}))