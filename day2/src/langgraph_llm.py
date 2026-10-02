from typing import Annotated, TypedDict

from langchain_core.messages import SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

GROQ_MODEL = "llama-3.3-70b-versatile"


class State(TypedDict):
    messages: Annotated[list, add_messages]
    intent: str


def build_graph(system_prompt: str):
    # "nostream" tag: the classify step must NOT be spoken by the voice agent
    classifier = ChatGroq(model=GROQ_MODEL, temperature=0).with_config(
        tags=["nostream"]
    )
    answerer = ChatGroq(model=GROQ_MODEL)

    async def classify(state: State):
        question = state["messages"][-1].content
        result = await classifier.ainvoke(
            "Classify this caller message with ONE word: "
            "booking, policy, info, or other.\n"
            f"Message: {question}"
        )
        return {"intent": result.content.strip().lower()}

    async def answer(state: State):
        hint = f"The caller's intent is: {state['intent']}."
        messages = [SystemMessage(content=system_prompt + "\n" + hint)]
        messages += state["messages"]
        reply = await answerer.ainvoke(messages)
        return {"messages": [reply]}

    graph = StateGraph(State)
    graph.add_node("classify", classify)
    graph.add_node("answer", answer)
    graph.add_edge(START, "classify")
    graph.add_edge("classify", "answer")
    graph.add_edge("answer", END)
    return graph.compile()