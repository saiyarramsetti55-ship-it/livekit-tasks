import asyncio

from dotenv import load_dotenv
from langchain.mcp import MCPAdapter
from langchain_groq import ChatGroq

load_dotenv()


# Practice Exercise Answers:
# 1. How many tools did the server expose?
#    Answer: 3
#
# 2. Which tool was called for each question?
#    Question 1: search_docs_by_lang_chain
#    Question 2: search_docs_by_lang_chain


async def main():
    # Connect to the live LangChain MCP server
    adapter = MCPAdapter("https://docs.langchain.com/mcp")

    # Get tools from the MCP server
    tools = await adapter.list_tools()

    print(f"Tools exposed: {len(tools)}")

    for tool in tools:
        print(f"- {tool.name}")

    # Create the LLM
    llm = ChatGroq(
        model="openai/gpt-oss-20b",
        temperature=0
    )

    # Give the MCP tools to the LLM
    agent = llm.bind_tools(tools)

    questions = [
        "How do I use `interrupt()` in LangGraph?",
        "What is `subgraphs=True` used for in streaming?"
    ]

    for question in questions:
        print("\n" + "=" * 70)
        print("Question:", question)

        # First LLM call: decide which MCP tool to use
        response = await agent.ainvoke(question)

        if response.tool_calls:
            for tool_call in response.tool_calls:

                tool_name = tool_call["name"]
                tool_args = tool_call["args"]

                print("\nTool called:")
                print("-", tool_name)

                # Find the selected MCP tool
                selected_tool = next(
                    tool for tool in tools
                    if tool.name == tool_name
                )

                # Execute the MCP tool
                tool_result = await selected_tool.ainvoke(tool_args)

                # Limit result size for Groq
                tool_result_text = str(tool_result)

                if len(tool_result_text) > 8000:
                    tool_result_text = (
                        tool_result_text[:8000]
                        + "\n...[truncated]"
                    )

                print("\nTool result:")
                print(tool_result_text)

                # Send tool result back to the LLM
                final_response = await agent.ainvoke([
                    response,
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": tool_result_text,
                    }
                ])

                print("\nFinal answer:")
                print(final_response.content)

        else:
            print("\nFinal answer:")
            print(response.content)


if __name__ == "__main__":
    asyncio.run(main())