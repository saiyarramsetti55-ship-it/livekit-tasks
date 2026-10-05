from langchain.tools import tool


@tool
def get_exchange_rate(base: str, target: str) -> float:
    """Get the exchange rate between two currencies.

    Args:
        base: The currency to convert FROM. Example: 'USD' or 'EUR'.
        target: The currency to convert TO. Example: 'GBP' or 'JPY'.

    Returns:
        The exchange rate as a number. For example, 1.27 means 1 base = 1.27 target.
    """
    # In a real project, call a currency API here
    rates = {
        "USD_GBP": 0.79,
        "USD_EUR": 0.92,
        "EUR_GBP": 0.86,
    }

    key = f"{base}_{target}"

    if key not in rates:
        raise ValueError(f"No rate found for {base} to {target}")

    return rates[key]


# Check the schema the LLM will see
print("Tool name:", get_exchange_rate.name)
print("Description:", get_exchange_rate.description)
print("Schema:", get_exchange_rate.args_schema.schema())


# Test valid tool execution
print("\n--- Tool Execution Test ---")

result = get_exchange_rate.invoke({
    "base": "USD",
    "target": "GBP"
})

print("USD -> GBP:", result)


# Test invalid currency
print("\n--- Invalid Currency Test ---")

result = get_exchange_rate.invoke({
    "base": "USD",
    "target": "INR"
})

print("USD -> INR:", result)
