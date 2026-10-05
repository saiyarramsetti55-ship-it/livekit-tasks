from langchain.tools import tool
from langgraph.prebuilt import InjectedState
from typing import Annotated
from typing_extensions import TypedDict
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from dotenv import load_dotenv

load_dotenv()

# --- State includes user info ---
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_id: str                    # Set when the user logs in
    user_role: str                  # Set from your database

# --- Tool uses injected state ---
@tool
def get_my_profile(
    fields: list,
    # This argument is injected from state — the LLM cannot see it
    user_id: Annotated[str, InjectedState("user_id")]
) -> dict:
    """Get profile information for the current logged-in user.

    Args:
        fields: List of profile fields to return. For example: ['name', 'email'].
    """
    # In a real project, query your database here
    profiles = {
        "alice": {"name": "Alice Smith", "email": "alice@company.com", "dept": "Engineering"},
        "bob":   {"name": "Bob Jones",  "email": "bob@company.com",  "dept": "Finance"},
    }
    profile = profiles.get(user_id, {})
    return {k: profile.get(k, "Not found") for k in fields}

@tool
def list_reports(
    # InjectedState injects user_role — LLM does not see this argument
    user_role: Annotated[str, InjectedState("user_role")]
) -> list:
    """List the reports available to the current user."""
    if user_role == "admin":
        return ["Sales Report", "HR Report", "Finance Report", "Security Report"]
    else:
        return ["Sales Report"]  # Regular users see fewer reports

# --- Verify the LLM schema does NOT include injected fields ---
print("get_my_profile schema:")
print(get_my_profile.args_schema.schema())
# You should see 'fields' but NOT 'user_id' in the properties

print("\nlist_reports schema:")
print(list_reports.args_schema.schema())
# You should see an EMPTY properties dict — no 'user_role'

# --- Build the agent ---
tools = [get_my_profile, list_reports]
llm = ChatGroq(model="openai/gpt-oss-20b").bind_tools(tools)
tool_node = ToolNode(tools)

def call_model(state: AgentState) -> dict:
    return {"messages": [llm.invoke(state["messages"])]}

def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    return "tools" if (hasattr(last, "tool_calls") and last.tool_calls) else END

builder = StateGraph(AgentState)
builder.add_node("agent", call_model)
builder.add_node("tools", tool_node)
builder.set_entry_point("agent")
builder.add_conditional_edges("agent", should_continue)
builder.add_edge("tools", "agent")
graph = builder.compile()

# --- Run as Alice (admin) ---
print("\n=== Alice (admin) ===")
result = graph.invoke({
    "messages": [HumanMessage(content="What reports can I see?")],
    "user_id": "alice",
    "user_role": "admin"
})
print(result["messages"][-1].content)

# --- Run as Bob (regular user) ---
print("\n=== Bob (viewer) ===")
result = graph.invoke({
    "messages": [HumanMessage(content="What reports can I see?")],
    "user_id": "bob",
    "user_role": "viewer"
})
print(result["messages"][-1].content)