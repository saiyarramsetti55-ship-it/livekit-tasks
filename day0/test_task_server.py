from fastmcp import FastMCP

mcp = FastMCP(
    name="Supplier Tools Server"
)


@mcp.tool
def get_supplier(supplier_id: str) -> dict:
    """Get supplier details by supplier ID."""

    suppliers = {
        "SUP-001": {
            "name": "Global Supplies Ltd",
            "location": "Hyderabad",
            "contact": "supplier1@example.com"
        },
        "SUP-002": {
            "name": "Tech Components Inc",
            "location": "Bangalore",
            "contact": "supplier2@example.com"
        },
        "SUP-003": {
            "name": "Industrial Goods Co",
            "location": "Chennai",
            "contact": "supplier3@example.com"
        },
    }

    if supplier_id not in suppliers:
        return {
            "error": f"Supplier {supplier_id} not found"
        }

    return suppliers[supplier_id]
@mcp.tool
def request_quote(
    supplier_id: str,
    sku: str,
    quantity: int
) -> dict:
    """Request a quote from a supplier for a product."""

    suppliers = {
        "SUP-001": {
            "name": "Global Supplies Ltd",
            "price_per_unit": 10.50,
            "lead_time_days": 5
        },
        "SUP-002": {
            "name": "Tech Components Inc",
            "price_per_unit": 12.75,
            "lead_time_days": 7
        },
        "SUP-003": {
            "name": "Industrial Goods Co",
            "price_per_unit": 9.25,
            "lead_time_days": 10
        },
    }

    if supplier_id not in suppliers:
        return {
            "error": f"Supplier {supplier_id} not found"
        }

    supplier = suppliers[supplier_id]

    return {
        "supplier_id": supplier_id,
        "supplier": supplier["name"],
        "sku": sku,
        "quantity": quantity,
        "unit_price": supplier["price_per_unit"],
        "total_price": quantity * supplier["price_per_unit"],
        "lead_time_days": supplier["lead_time_days"]
    }

if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8002,
        path="/mcp"
    )