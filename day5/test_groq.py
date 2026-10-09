import asyncio

from dotenv import load_dotenv
from livekit.agents.llm import ChatContext, ChatMessage
from livekit.plugins.groq import LLM


load_dotenv(".env.local")


async def main():
    llm = LLM(model="openai/gpt-oss-120b")

    chat_ctx = ChatContext(
        items=[
            ChatMessage(
                role="user",
                content=["Say OK"],
            )
        ]
    )

    print("Testing Groq...")

    try:
        stream = llm.chat(chat_ctx=chat_ctx)

        async for chunk in stream:
            print(chunk)

    except Exception as e:
        print("Groq error:", type(e).__name__)
        print(e)


asyncio.run(main())