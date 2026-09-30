import os
import uuid
from pathlib import Path

from dotenv import load_dotenv

from langchain.agents import create_agent
from langgraph.checkpoint.redis import RedisSaver
from langgraph.store.redis import RedisStore
from langchain_groq import ChatGroq

from tools import (
    search_tool,
    wiki_tool,
    save_to_txt,
)

from long_term_tools import (
    save_user_memory,
    get_user_memory,
)

from RAG.rag_tool import search_redis_knowledge

from router import route_query


# ============================================================
# 1. ENVIRONMENT CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

if not os.getenv("GROQ_API_KEY"):
    raise ValueError(
        "GROQ_API_KEY not found. Check your .env file."
    )


# ============================================================
# 2. LLM CONFIGURATION
# ============================================================

llm = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0,
)


# ============================================================
# 3. ROUTE-BASED TOOL SELECTION
# ============================================================

def get_tools_for_route(route: str):

    if route == "memory":
        return [
            save_user_memory,
            get_user_memory,
        ]

    elif route == "rag":
        return [
            search_redis_knowledge,
        ]

    elif route == "file":
        return [
            save_to_txt,
        ]

    elif route == "research":
        return [
            search_tool,
            wiki_tool,
        ]

    else:
        return [
            wiki_tool,
        ]


# ============================================================
# 4. TOOL DISPLAY NAMES
# ============================================================

def get_tool_names(route: str):

    tool_names = {
        "memory": [
            "save_user_memory",
            "get_user_memory",
        ],

        "rag": [
            "search_redis_knowledge",
        ],

        "file": [
            "save_to_txt",
        ],

        "research": [
            "duckduckgo_search",
            "wikipedia",
        ],

        "general": [
            "wikipedia",
        ],
    }

    return tool_names.get(route, [])


# ============================================================
# 5. SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are a helpful AI assistant.

Follow these rules:

1. Use only the tools available to you.
2. For personal memory questions, use memory tools. Always use user_id="current_user" for all memory operations.
3. For Redis knowledge-base questions, use the RAG tool and follow the RAG grounding rules below.
4. For current information, use web search when available.
5. Do not invent facts or claim a tool was used when it was not.
6. If information is insufficient, say so clearly.
7. Keep answers accurate and concise.

RAG GROUNDING RULES (apply whenever the rag route is active):
- Base your answer ONLY on the text returned by the search_redis_knowledge tool.
- Do not supplement retrieved content with your own pretrained knowledge.
- Do not invent technical details such as snapshot intervals, fsync settings, durability guarantees, or production recommendations unless that exact information appears in the retrieved text.
- If the retrieved text does not contain the answer to a specific question, state explicitly: "The knowledge base does not contain information about [topic]."
- Clearly distinguish between facts present in the retrieved text and information that was not retrieved.
"""


# ============================================================
# 6. REDIS CONFIGURATION
# ============================================================

REDIS_URI = "redis://localhost:6379"

# Generate a unique thread ID for each program execution.
thread_id = str(uuid.uuid4())

print("=" * 60)
print("AI AGENT")
print("=" * 60)

print(f"Thread ID: {thread_id}")


# ============================================================
# 7. MAIN EXECUTION
# ============================================================

with RedisSaver.from_conn_string(REDIS_URI) as checkpointer:

    checkpointer.setup()

    with RedisStore.from_conn_string(REDIS_URI) as store:

        store.setup()

        while True:

            query = input("\nYou: ").strip()

            if query.lower() in ["exit", "quit"]:
                print("Exiting agent...")
                break

            if not query:
                continue

            # ------------------------------------------------
            # STEP 1: ROUTING
            # ------------------------------------------------

            route = route_query(query)

            print(f"\nDetected Route: {route}")

            # ------------------------------------------------
            # STEP 2: SELECT TOOLS
            # ------------------------------------------------

            selected_tools = get_tools_for_route(route)

            print("\nAvailable Tools:")

            for tool_name in get_tool_names(route):
                print(f"- {tool_name}")

            # ------------------------------------------------
            # STEP 3: CREATE AGENT
            # ------------------------------------------------

            agent = create_agent(
                model=llm,
                tools=selected_tools,
                system_prompt=SYSTEM_PROMPT,
                checkpointer=checkpointer,
                store=store,
            )

            config = {
                "configurable": {
                    "thread_id": thread_id
                }
            }

            # ------------------------------------------------
            # STEP 4: GET PREVIOUS CHECKPOINT STATE
            # ------------------------------------------------

            previous_state = agent.get_state(config)

            previous_message_count = (
                len(previous_state.values.get("messages", []))
                if previous_state.values
                else 0
            )

            # ------------------------------------------------
            # STEP 5: INVOKE AGENT
            # ------------------------------------------------

            response = agent.invoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": query,
                        }
                    ]
                },
                config=config,
            )

            # Extract only messages generated in this invocation.
            new_messages = response["messages"][
                previous_message_count:
            ]

            # ------------------------------------------------
            # STEP 6: EXECUTION TRACE
            # ------------------------------------------------

            print("\n" + "-" * 60)
            print("CURRENT EXECUTION TRACE")
            print("-" * 60)

            for message in new_messages:

                if message.type == "human":

                    print(f"\nUSER: {message.content}")

                elif message.type == "ai":

                    if message.tool_calls:

                        for tool_call in message.tool_calls:

                            print(
                                f"\nTOOL CALL: {tool_call['name']}"
                            )

                            print(
                                f"INPUT: {tool_call['args']}"
                            )

                    elif message.content:

                        print(f"\nAI: {message.content}")

                elif message.type == "tool":

                    print(
                        f"\nTOOL RESULT ({message.name}):"
                    )

                    print(message.content)

            # ------------------------------------------------
            # STEP 7: FINAL RESPONSE
            # ------------------------------------------------

            final_response = None

            for message in reversed(new_messages):

                if message.type == "ai" and message.content:

                    final_response = message.content
                    break

            print("\n" + "=" * 60)
            print("FINAL ANSWER")
            print("=" * 60)

            if final_response:
                print(final_response)

            else:
                print("No final response was generated.")

            print("=" * 60)