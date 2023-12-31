import json
import os
import re
import openai
import requests
import tiktoken
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


app = FastAPI()


if os.environ.get("CORS_DEV"):
    print("Running in development mode..")
    origins = [os.environ.get("CORS_DEV")]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


openai.api_key = os.environ.get("OPENAI_API_KEY")
openai.organization = os.environ.get("OPENAI_ORGANIZATION_ID")


class Message(BaseModel):
    messages: list[dict]


def search_google_images(query):
    api_key = os.environ.get("GOOGLE_API_KEY")
    cx = os.environ.get("GOOGLE_CX_ID")

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "searchType": "image",
    }
    response = requests.get(url, params=params)
    return response.json()


def get_llm_response(messages):
    buffer_tokens = 256
    wrapper_tokens = 5

    max_tokens = 8192
    if os.environ.get('OPENAI_MAX_TOKENS'):
        max_tokens = int(os.environ.get('OPENAI_MAX_TOKENS'))

    model = os.environ.get('OPENAI_MODEL') or "gpt-4"

    def count_tokens(text):
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))

    # The instruction prompt
    instruction = """You are an AI chatbot interacting with a human user. You possess a unique capability to enrich the conversation with images. While you are not able to see or comprehend images, the user will see them if you insert a placeholder in this format: {{image:<query string>}}. This placeholder will then be passed to the Google Image Search API and the first result will be displayed to the user. You should try to build the answers so that the text and images flow naturally, perhaps alternating, and most preferably, if possible, between paragraphs and not within sentences. I know you like your superpower, however, you should not go overboard: please only include images when appropriate. Remember, less is more."""

    # Calculate how many tokens we can use for the conversation history
    tokens_available = max_tokens - count_tokens(instruction) - buffer_tokens

    # Truncate conversation history if necessary
    conversation_str = "\n\n".join([msg["text"] for msg in messages])
    if (
        count_tokens(conversation_str) + wrapper_tokens * len(messages)
        > tokens_available
    ):
        while messages:
            conversation_str = "\n\n".join([msg["text"] for msg in messages])
            if (
                count_tokens(conversation_str) + wrapper_tokens * len(messages)
                <= tokens_available
            ):
                break
            else:
                messages.pop(0)

    # prepare prompt that ChatCompletion understands
    messages_prompt = []
    messages_prompt.append({"role": "system", "content": instruction})
    for message in messages:
        messages_prompt.append({"role": message["role"], "content": message["text"]})

    # And run the query
    response = openai.ChatCompletion.create(
        model=model, messages=messages_prompt, temperature=0
    )

    # Extract the message
    message = response["choices"][0]["message"]["content"]

    # Do a little cleanup.
    message = message.replace("}}.", "}}")

    return message


def create_message(messages):
    # get llm response
    message_text = get_llm_response(messages)

    # find image placeholders
    matches = re.findall(r"{{image:(.*?)}}", message_text)

    # for each placeholder, to a google image search
    # and pick the good first result.
    images = []
    for match in matches:
        results = search_google_images(match)
        found = False
        if results.get("items"):
            for result in results["items"]:
                # only allow secure urls
                # (most importantly to not face problems with
                # embedding http-urls within https-site)
                if not result["link"].startswith("https://"):
                    continue

                if all(
                    [
                        not result["link"].endswith(".png"),
                        not result["link"].endswith(".jpg"),
                    ]
                ):
                    continue

                images.append({"url": result["link"]})
                found = True
                break

        if not found:
            images.append({"url": ""})

    # combine everything to a single message
    message = {"text": message_text, "images": images, "role": "assistant"}
    return message


@app.post("/generate_response")
async def generate_response(content: Message):
    response = content.messages + [create_message(content.messages)]

    # to debug, you may use a mock
    # response = content.messages + [{
    #     "role": "assistant",
    #     "text": "Hello I am a bot. {{whale}} I like cats. {{cat}}",
    #     "images": [{"url": "https://img.freepik.com/premium-photo/mammals-animals-big-blue-whale-white-background_124507-30784.jpg"}, {"url": "https://cdn.britannica.com/39/7139-050-A88818BB/Himalayan-chocolate-point.jpg"}]
    # }]
    # import time; time.sleep(2)

    return {"messages": response}
