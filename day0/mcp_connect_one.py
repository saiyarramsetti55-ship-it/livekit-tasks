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
    # Connect to the real LangChain docs MCP server
    # This is a live public server you can test against right now
    async with MCPAdapter("https://docs.langchain.com/mcp") as adapter:

        # Discover all tools the server offers
        tools = await adapter.list_tools()

        print(f"Found {len(tools)} tools:")
        for t in tools:
            print(f"  - {t.name}: {t.description[:70]}")

        # Use the tools exactly like any other LangChain tool
        llm = ChatGroq(model="openai/gpt-oss-20b")
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

        # Ask a question that requires the server's tools
        result = graph.invoke({
            "messages": [HumanMessage(content="What is LangGraph's ToolNode?")]
        })
        print("\nAnswer:", result["messages"][-1].content)

asyncio.run(main())

# file: mcp_connect_multi.py

import asyncio
from langchain.mcp import MCPAdapter

async def main():
    config = {
        "mcpServers": {
            # Server 1: remote HTTP
            "langchain_docs": {
                "url": "https://docs.langchain.com/mcp"
            },
            # Server 2: local Python script
            # "my_local_server": Path("hr_server.py"),
        }
    }

    async with MCPAdapter(config) as adapter:
        tools = await adapter.list_tools()
        print(f"Total tools from all servers: {len(tools)}")

asyncio.run(main())