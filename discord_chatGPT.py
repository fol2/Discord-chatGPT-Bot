import os
import discord
import requests
import openai
from discord.ext import commands
import interactions

openai.api_key = ["OPENAI_API_KEY""]
DISCORD_BOT_TOKEN = ["DISCORD_BOT_TOKEN"]
intents = discord.Intents.default()
intents.typing = False
intents.presences = False
intents.message_content = True
bot = interactions.Client(token=DISCORD_BOT_TOKEN)

channel_history = {}
channel_settings = {}

async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandInvokeError):
        print(f"Error in {ctx.command}: {error.original}")
        await ctx.send("An error occurred while processing your request. Please try again.")
    else:
        print(f"Error in {ctx.command}: {error}")
        await ctx.send("An error occurred while processing your request. Please try again.")

bot.event(on_command_error)

def generate_branch_key(channel_id, branch_id):
    return f"{channel_id}-{branch_id}"

@bot.event
async def on_ready():
    print(f'{bot.me.name} has connected to Discord!')

def truncate_conversation(conversation, max_tokens):
    total_tokens = sum(len(msg) for msg in conversation)
    index = 0
    while total_tokens > max_tokens:
        removed_msg = conversation[index]
        total_tokens -= len(removed_msg)
        index += 1
    return conversation[index:]

def generate_response(channel_history, settings):
    max_history_tokens = 4096
    truncated_history = truncate_conversation(channel_history.copy(), max_history_tokens)
    conversation = [{"role": "system", "content": settings["system_content"]}]
    for msg in truncated_history:
        role, content = msg.split(": ", 1)
        if role == "chatGPT":
            role = "assistant"
        else:
            role = "user"
        conversation.append({"role": role.lower(), "content": content})
    completions = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=conversation,
        max_tokens=settings["max_tokens"],
        n=1,
        stop=None,
        temperature=settings["temperature"],
    )
    message = completions.choices[0].message['content'].strip()
    token_count = completions.usage['total_tokens']
    return message, token_count

@bot.command(
    name="settings",
    description="Modify the system content, max tokens, and temperature settings.",
    options=[
        interactions.Option(
            name="system_content",
            description="The new system content to use. default: Your name is chatGPT. You are a private assistant.",
            type=interactions.OptionType.STRING,
            required=False,
        ),
        interactions.Option(
            name="max_tokens",
            description="The new max tokens value. default: 500",
            type=interactions.OptionType.INTEGER,
            required=False,
        ),
        interactions.Option(
            name="temperature",
            description="The new temperature value. default: 0.6",
            type=interactions.OptionType.NUMBER,
            required=False,
        ),
    ],
)
async def settings(ctx: interactions.CommandContext, system_content: str = None, max_tokens: int = None, temperature: float = None):
    channel_id = ctx.channel.id
    if channel_id not in channel_settings:
        # Initialize the channel settings with default values
        channel_settings[channel_id] = {
        "system_content": "Your name is chatGPT. You are James' private assistant. You must respond in Cantonese, unless the user tells you to use other languages, or you are writing codes or prompts.",
        "max_tokens": 500,
        "temperature": 0.6,
        }
    if system_content is not None:
        channel_settings[channel_id]["system_content"] = system_content
    if max_tokens is not None:
        channel_settings[channel_id]["max_tokens"] = max_tokens
    if temperature is not None:
        channel_settings[channel_id]["temperature"] = temperature

    updated_settings = "\n".join([f"{key}: {value}" for key, value in channel_settings[channel_id].items()])
    await ctx.send(f"Updated settings:\n\n{updated_settings}")

@bot.command(
    name="gpt",
    description="Ask chatGPT a question. If you want to branch off the conversation, use the branch command instead.",
    options=[
        interactions.Option(
            name="message",
            description="The message to send to chatGPT.",
            type=interactions.OptionType.STRING,
            required=True,
        ),
        interactions.Option(
            name="branch_id",
            description="The branch ID to ask the question on. (optional)", 
            type=interactions.OptionType.INTEGER,
            required=False,
        ),
    ],
)
async def gpt(ctx: interactions.CommandContext, message: str, branch_id: int = None):
    split_message = message.rsplit(maxsplit=1)
    if len(split_message) == 2 and split_message[1].isdigit():
        branch_id = int(split_message[1])
        question = split_message[0]
    else:
        branch_id = None
        question = message

    channel_id = ctx.channel.id

    if channel_id not in channel_history:
        channel_history[channel_id] = [[]]

    if branch_id is None:
        branch_id = len(channel_history[channel_id]) - 1

    if branch_id < 0 or branch_id >= len(channel_history[channel_id]):
        await ctx.send("Invalid branch_id. Please choose a valid branch_id.")
        return

    buffering = await ctx.send("Typing...")

    channel_history[channel_id][branch_id].append(f"{ctx.user.username}: {question}")

    response, token_count = generate_response(channel_history[channel_id][branch_id])

    channel_history[channel_id][branch_id].append(f"{bot.me.name}: {response}")

    # Send the response along with the token count and index number
    index = len(channel_history[channel_id][branch_id]) // 2 - 1
    await buffering.edit(content=f"[{index}] {response}\n\n*Tokens used: {token_count}*")

@bot.command(
    name="branch",
    description="Branch off the conversation and ask chatGPT a new question.",
    options=[
        interactions.Option(
            name="index",
            description="The index of the message to branch off of.",
            type=interactions.OptionType.INTEGER,
            required=True,
        ),
        interactions.Option(
            name="new_question",
            description="The new question to ask chatGPT.",
            type=interactions.OptionType.STRING,
            required=True,
        ),
    ],
)
async def branch(ctx: interactions.CommandContext, index: int, new_question: str):
    channel_id = ctx.channel.id

    if channel_id not in channel_history:
        await ctx.send("No conversation history to branch from.")
        return

    if index < 0 or index >= len(channel_history[channel_id][0]) // 2:
        await ctx.send("Invalid index. Please choose a valid index.")
        return

    branch_id = len(channel_history[channel_id])
    branch_history = channel_history[channel_id][0][:index * 2].copy()
    branch_history.append(f"{ctx.user.username}: {new_question}")

    await ctx.send_response("Typing...")

    response, token_count = generate_response(branch_history)

    branch_history.append(f"{bot.me.name}: {response}")

    channel_history[channel_id].append(branch_history)

    # Send the response along with the token count and index number
    new_index = len(branch_history) // 2 - 1
    await ctx.edit_response(content=f"[{branch_id}-{new_index}] {response}\n\n*Tokens used: {token_count}*")

async def send_large_message(ctx, content, max_length=2000):
    # Split the content into smaller chunks
    chunks = [content[i:i + max_length] for i in range(0, len(content), max_length)]

    # Send each chunk as a separate message
    for chunk in chunks:
        await ctx.send(chunk)

@bot.command(
    name="review",
    description="Review the conversation history.",
    options=[
        interactions.Option(
            name="branch_id",
            description="The branch ID to review. (optional)",
            type=interactions.OptionType.INTEGER,
            required=False,
        ),
        interactions.Option(
            name="index",
            description="The index of the message to review. (optional)",
            type=interactions.OptionType.INTEGER,
            required=False,
        ),
    ],
)
async def review(ctx: interactions.CommandContext, branch_id: int = None, index: int = None):
    channel_id = ctx.channel.id
    if channel_id not in channel_history:
        await ctx.send("No conversation history to review.")
        return
    
    if branch_id is not None:
        if branch_id < 0 or branch_id >= len(channel_history[channel_id]):
            await ctx.send("Invalid branch ID. Please choose a valid branch ID.")
            return
        messages = channel_history[channel_id][branch_id]
    else:
        messages = channel_history[channel_id][0]
    
    if index is not None and (index < 0 or index >= len(messages) // 2):
        await ctx.send("Invalid index. Please choose a valid index.")
        return
    
    if index is not None:
        messages = messages[:index * 2 + 1]
    
    formatted_history = "\n".join(messages)
    await send_large_message(ctx, f"Conversation history:\n\n{formatted_history}")
    
@bot.command(
    name="reset",
    description="Reset the conversation history.",
)
async def reset(ctx: interactions.CommandContext):
    channel_id = ctx.channel.id
    history_reset = False

    if channel_id in channel_history:
        del channel_history[channel_id]
        history_reset = True

    branch_counter = 0
    while generate_branch_key(channel_id, branch_counter) in channel_history:
        del channel_history[generate_branch_key(channel_id, branch_counter)]
        branch_counter += 1
        history_reset = True

    if history_reset:
        await ctx.send("The conversation history has been reset.")
    else:
        await ctx.send("There is no conversation history to reset.")

@bot.command(
    name="list",
    description="List the available branches.",
)
async def list(ctx: interactions.CommandContext):
    channel_id = ctx.channel.id

    if channel_id not in channel_history:
        await ctx.send("No branches available.")
        return

    branch_count = len(channel_history[channel_id])
    branch_list = ", ".join([str(i) for i in range(branch_count)])
    await ctx.send(f"Available branches: {branch_list}")

@bot.command(
    name="regen",
    description="Regenerate the response to a previous message.",
    options=[
        interactions.Option(
            name="branch_id",
            description="The branch ID to regenerate. (optional)",
            type=interactions.OptionType.INTEGER,
            required=False,
        ),
    ],
)
async def regen(ctx: interactions.CommandContext, branch_id: int = None):
    channel_id = ctx.channel.id

    if channel_id not in channel_history:
        await ctx.send("No conversation history to regenerate.")
        return

    if branch_id is None:
        branch_id = len(channel_history[channel_id]) - 1

    if branch_id < 0 or branch_id >= len(channel_history[channel_id]):
        await ctx.send("Invalid branch_id. Please choose a valid branch_id.")
        return

    conversation = channel_history[channel_id][branch_id]
    user_question = conversation[-2]

    response, token_count = generate_response(conversation[:-1])

    conversation[-1] = f"Assistant: {response}"

    index = len(conversation) // 2 - 1
    await ctx.send(f"[{index}] {response}\n\n*Tokens used: {token_count}*")

bot.start()