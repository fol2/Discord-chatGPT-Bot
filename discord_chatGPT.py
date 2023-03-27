import os
import discord
import requests
import openai
from discord.ext import commands

# Replace with your OpenAI API key
openai.api_key = "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"
# Replace with your Discord bot token
DISCORD_BOT_TOKEN = "MTA4OTcyMjIzMTUzNTQzOTkyNA.GNYVHh.LJU1c4gJ_yx1DXCBlnjoHLODe_gIxzCq1EY-Q0"

# Set the command prefix (e.g., !gpt)
PREFIX = "gpt"

intents = discord.Intents.default()
intents.typing = False
intents.presences = False
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Dictionary to store conversation history for each channel
channel_history = {}

def generate_branch_key(channel_id, branch_id):
    return f"{channel_id}-{branch_id}"

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

import openai

def truncate_conversation(conversation, max_tokens):
    total_tokens = sum(len(msg) for msg in conversation)
    while total_tokens > max_tokens:
        removed_msg = conversation.pop(0)
        total_tokens -= len(removed_msg)
    return conversation

def generate_response(channel_history):
    max_history_tokens = 4097
    
    truncated_history = truncate_conversation(channel_history.copy(), max_history_tokens)
    conversation = [{"role": "system", "content": "Your name is chatGPT. You are James' private assistant. You must response in Cantonese, unless user tell you to use other languages, or you are writing codes or prompts."}]
    
    for msg in truncated_history:
        role, content = msg.split(": ", 1)
        conversation.append({"role": role.lower(), "content": content})
    
    completions = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=conversation,
        max_tokens=500,
        n=1,
        stop=None,
        temperature=0.6,
    )

    message = completions.choices[0].message['content'].strip()
    token_count = completions.usage['total_tokens']
    return message, token_count

@bot.command(name="ask")
async def ask(ctx, *, message: str):
    try:
        split_message = message.split(maxsplit=1)
        if len(split_message) == 2 and split_message[0].isdigit():
            branch_id = int(split_message[0])
            question = split_message[1]
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

        channel_history[channel_id][branch_id].append(f"User: {question}")

        response, token_count = generate_response(channel_history[channel_id][branch_id])

        channel_history[channel_id][branch_id].append(f"Assistant: {response}")

        # Send the response along with the token count and index number
        index = len(channel_history[channel_id][branch_id]) // 2 - 1
        await ctx.send(f"[{index}] {response}\n\n*Tokens used: {token_count}*")
    except Exception as e:
        print(f"Error in ask command: {e}")
        await ctx.send("An error occurred while processing your request. Please try again.")

@bot.command(name="branch")
async def branch(ctx, index: int, *, new_question):
    try:
        channel_id = ctx.channel.id

        if channel_id not in channel_history:
            await ctx.send("No conversation history to branch from.")
            return

        if index < 0 or index >= len(channel_history[channel_id][0]) // 2:
            await ctx.send("Invalid index. Please choose a valid index.")
            return

        branch_id = len(channel_history[channel_id])
        branch_history = channel_history[channel_id][0][:index * 2].copy()
        branch_history.append(f"User: {new_question}")

        response, token_count = generate_response(branch_history)

        branch_history.append(f"Assistant: {response}")

        channel_history[channel_id].append(branch_history)

        # Send the response along with the token count and index number
        new_index = len(branch_history) // 2 - 1
        await ctx.send(f"[{branch_id}-{new_index}] {response}\n\n*Tokens used: {token_count}*")
    except Exception as e:
        print(f"Error in branch command: {e}")
        await ctx.send("An error occurred while processing your request. Please try again.")

@bot.command(name="review")
async def review(ctx, branch_id: int = None, index: int = None):
    try:
        channel_id = ctx.channel.id

        if channel_id not in channel_history and not any(generate_branch_key(channel_id, i) in channel_history for i in range(len(channel_history[channel_id][0]) // 2)):
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
        await ctx.send(f"Conversation history:\n\n{formatted_history}")
    except Exception as e:
        print(f"Error in review command: {e}")
        await ctx.send("An error occurred while processing your request. Please try again.")

@bot.command(name="reset")
async def reset(ctx):
    try:
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
    except Exception as e:
        print(f"Error in reset command: {e}")
        await ctx.send("An error occurred while processing your request. Please try again.")

bot.run(DISCORD_BOT_TOKEN)
