from langchain.mcp import MCPAdapter


async def main():
    adapter = MCPAdapter("http://127.0.0.1:8002/mcp")

    tools = await adapter.list_tools()

    print("Available tools:")
    for tool in tools:
        print(f"- {tool.name}")

    print("\nTesting request_quote:")

    request_quote = next(
        tool for tool in tools
        if tool.name == "request_quote"
    )

    result = await request_quote.ainvoke({
    "supplier_id": "SUP-999",
    "sku": "SKU-001",
    "quantity": 100
})
    print(result)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())