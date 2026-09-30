import redis
import json
from langchain_core.messages import HumanMessage, AIMessage

client = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True,
)


def save_message(session_id, role, content):
    key = f"chat:{session_id}"

    message = {
        "role": role,
        "content": content,
    }

    client.rpush(key, json.dumps(message))#adds a message to the end of the list stored at key


def get_messages(session_id):
    key = f"chat:{session_id}"

    messages = client.lrange(key, 0, -1)#retrives a message 

    result = []

    for message in messages:
        message = json.loads(message)

        if message["role"] == "user":
            result.append(
                HumanMessage(content=message["content"])
            )

        elif message["role"] == "assistant":
            result.append(
                AIMessage(content=message["content"])
            )

    return result



