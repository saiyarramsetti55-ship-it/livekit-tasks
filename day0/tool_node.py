from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, MessagesState, START
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from dotenv import load_dotenv
load_dotenv()

@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@tool
def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b


@tool
def get_weather(city: str) -> str:
    """Get the current weather for a city."""

    weather = {
        "London": "15°C, cloudy",
        "Paris": "22°C, sunny",
        "Tokyo": "28°C, humid",
    }

    return weather.get(city, "Weather data not available")


print("Tools created:")
print(add.name)
print(multiply.name)
print(get_weather.name)

tools = [add, multiply, get_weather]

tool_node = ToolNode(tools)

print("\nToolNode created successfully")
print("Number of tools:", len(tools))

#Create the LangGraph

llm = ChatGroq(model="openai/gpt-oss-20b")

llm_with_tools = llm.bind_tools(tools)


def call_model(state: MessagesState):
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}


def should_continue(state: MessagesState):
    last = state["messages"][-1]

    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"

    return "__end__"

builder = StateGraph(MessagesState)

builder.add_node("agent", call_model)
builder.add_node("tools", tool_node)

builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", should_continue)
builder.add_edge("tools", "agent")

graph = builder.compile()

print("\nLangGraph compiled successfully")

#Test the graph

result = graph.invoke({
    "messages": [
        HumanMessage(
            content="What is 15 multiplied by 8? Also, what is the weather in London?"
        )
    ]
})

print("\nFinal Answer:")
print(result["messages"][-1].content)