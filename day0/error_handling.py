from langchain.tools import tool
from langchain_core.tools import ToolException
from langgraph.prebuilt import ToolNode


@tool
def divide(a: float, b: float) -> float:
    """Divide a by b."""
    if b == 0:
        raise ToolException(
            "Cannot divide by zero. Please provide a non-zero value for b and try again."
        )
    return a / b


print("Valid calculation:")
print(divide.invoke({"a": 10, "b": 2}))

print("\nDivision by zero:")
try:
    print(divide.invoke({"a": 10, "b": 0}))
except Exception as e:
    print("Caught error:", e)



#Error Strategy 2: Soft String Return
@tool
def find_user(user_id: str) -> str:
    """Look up a user by their ID."""

    users = {
        "user-001": "Alice",
        "user-002": "Bob"
    }

    user = users.get(user_id)

    if user is None:
        return f"No user found with ID '{user_id}'. Please check the ID and try again."

    return user
print("\n--- Find User ---")

print("Valid user:")
print(find_user.invoke({"user_id": "user-001"}))

print("\nUnknown user:")
print(find_user.invoke({"user_id": "user-999"}))

#Unexpected Errors

@tool
def risky_operation(value: str) -> str:
    """Perform an operation that may raise an unexpected error."""

    if value == "error":
        raise ValueError("Unexpected error occurred.")

    return f"Operation successful: {value}"


print("\n--- Unexpected Error ---")

print("Valid operation:")
print(risky_operation.invoke({"value": "hello"}))

print("\nUnexpected operation:")

try:
    print(risky_operation.invoke({"value": "error"}))
except Exception as e:
    print("Unexpected error caught:", e)


# ToolNode(handle_tool_errors=True)

tools = [divide]

# Catches all uncaught exceptions from any tool
tool_node = ToolNode(tools, handle_tool_errors=True)

# Or provide a custom error message
tool_node = ToolNode(
    tools,
    handle_tool_errors="The tool failed. Please try a different approach."
)

print("\n--- ToolNode Error Handling ---")
print(tool_node)