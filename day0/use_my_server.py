import asyncio
from langchain.mcp import MCPAdapter
from langchain_groq import ChatGroq
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage
from typing import Annotated
from typing_extensions import TypedDict
from dotenv import load_dotenv

load_dotenv()

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

async def main():
    # Connect to your local server
    async with MCPAdapter("http://localhost:8001/mcp") as adapter:
        tools = await adapter.list_tools()

        print(f"Your server exposed {len(tools)} tools:")
        for t in tools:
            print(f"  - {t.name}")

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

        # Test your server
        questions = [
            "Look up employee EMP-001. What is their annual leave balance?",
            "Request 1 day of sick leave for EMP-002 because they have a doctor's appointment.",
        ]

        for q in questions:
            print(f"\nQ: {q}")
            result = await graph.ainvoke({"messages": [HumanMessage(content=q)]})
            print(f"A: {result['messages'][-1].content}")

asyncio.run(main())