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


if os.environ.get("IMAGELLM_DEV") == "true":
    print("Running in development mode..")
    origins = ["http://localhost:1234"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


openai.api_key = os.environ.get("OPENAI_API_KEY")


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
    buffer_tokens = 50
    max_tokens = 4096
    model = "text-davinci-003"

    def count_tokens(text):
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))

    def format_message(message):
        if message["role"] == "user":
            return "User: " + message["text"]
        else:
            return "System: " + message["text"]

    # The instruction prompt
    instruction = """
You are an AI chatbot interacting with a human user. You possess a unique capability to enrich the conversation with images. While you are not able to see or comprehend images, you can invoke them in the conversation. Whenever you deem it appropriate to include an image, insert a placeholder in this format: {{description of the contents of the image}}. This placeholder will then be passed to the Google Image Search API and the first result will be displayed to the user. You should try to build the answers so that the text and images flow naturally, perhaps alternating. However, the images should never be placed inside a sentence, as that will make it hard to present it to the user. So, the text and images could alternate, and the best places to put images are between paragraphs. You may build your textual responses so that images can be well placed. You do not always need to include images, only when it seems helpful.
    """

    # The conversation history
    conversation_history = [format_message(message) for message in messages]

    # Calculate how many tokens we can use for the conversation history
    tokens_available = max_tokens - count_tokens(instruction) - buffer_tokens

    # Create a single string from the list of messages
    conversation_str = "\n\n".join(conversation_history)

    # Truncate conversation history if necessary
    if count_tokens(conversation_str) > tokens_available:
        while conversation_history:
            conversation_str = "\n".join(conversation_history)
            if count_tokens(conversation_str) <= tokens_available:
                break
            else:
                conversation_history.pop(0)

    # Combine the instruction and conversation history into the final prompt
    prompt = (
        instruction
        + "\n"
        + "Here's the chat so far:\n\n"
        + conversation_str
        + "\n\nAssistant's turn:"
    )

    response = openai.Completion.create(engine=model, prompt=prompt, max_tokens=512)

    message = response.choices[0].text.strip()
    return message


def create_message(messages):
    # get llm response
    message_text = get_llm_response(messages)

    # find image placeholders
    matches = re.findall(r"{{(.*?)}}", message_text)

    # for each placeholder, to a google image search
    # and pick the first result.
    images = []
    for match in matches:
        results = search_google_images(match)
        if results:
            images.append({"url": results["items"][0]["link"]})

    # combine everything to a single message
    message = {"text": message_text, "images": images, "role": "assistant"}
    return message


@app.post("/generate_response")
async def generate_response(content: Message):
    response = content.messages + [create_message(content.messages)]
    return {"messages": response}
