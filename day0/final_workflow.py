from langchain.mcp import MCPAdapter


def check_stock(sku: str) -> dict:
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
        }
    }

    if sku not in stock:
        return {"error": f"Unknown SKU: {sku}"}

    return stock[sku]


async def main():
    adapter = MCPAdapter("http://127.0.0.1:8002/mcp")
    tools = await adapter.list_tools()

    request_quote = next(
        tool for tool in tools
        if tool.name == "request_quote"
    )

    sku = "SKU-002"

    stock = check_stock(sku)

    print("Stock information:")
    print(stock)

    if stock["quantity"] < 20:
        print("\nLow stock detected.")

        quote = await request_quote.ainvoke({
            "supplier_id": "SUP-001",
            "sku": sku,
            "quantity": 100
        })

        print("\nSupplier quote:")
        print(quote)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())