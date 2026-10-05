from langchain_core.tools import StructuredTool


def send_notification(
    channel: str,
    message: str,
    urgent: bool = False
) -> bool:
    """Existing notification function — we cannot add @tool here."""

    print(f"[{'URGENT ' if urgent else ''}#{channel}] {message}")

    return True


notify_tool = StructuredTool.from_function(
    func=send_notification,
    name="send_notification",
    description=(
        "Send a message to a team channel. "
        "Use urgent=True only for critical issues that need immediate attention."
    )
)


print("Tool name:", notify_tool.name)

result = notify_tool.invoke({
    "channel": "engineering",
    "message": "Deploy complete",
    "urgent": False
})

print("Sent:", result)