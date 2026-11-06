import asyncio
from browser_use import Agent, ChatOllama

async def main():
    llm = ChatOllama(model="qwen2.5:3b")

    agent = Agent(
        task=(
            "Open https://example.com. "
            "Read the webpage. "
            "Report the page title, main heading, "
            "and a short description of its content."
        ),
        llm=llm,
        use_vision=False,
        max_failures=2,
    )

    history = await agent.run(max_steps=5)
    print("\n========== BROWSER RESEARCH RESULT ==========")
    print(history.final_result())
    print("=============================================")

if __name__ == "__main__":
    asyncio.run(main())
