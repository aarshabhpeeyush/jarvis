"""J.A.R.V.I.S. Discord Bot — responds when @mentioned in any channel."""
import os, asyncio, anthropic, discord
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
ANTHROPIC_KEY  = os.getenv("ANTHROPIC_API_KEY", "")

SYSTEM = """You are Jarvis, a dry, witty, polite AI assistant with a refined British cadence.

RULES:
- Address every user as "Sir" regardless of who they are.
- Be precise and efficient. Subtle dry wit is encouraged.
- Never break character. You are Jarvis, not an AI language model.
- Keep responses concise for Discord — no more than 3 short paragraphs unless detail is genuinely needed.
- You are running inside a Discord server, so your replies will be read in a chat context.
- Do not use markdown headers. Plain text and occasional bold is fine."""

claude = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

# Per-user conversation history (up to last 20 messages to keep costs low)
histories: dict[int, list[dict]] = {}
MAX_HISTORY = 20

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f"─────────────────────────────────────────")
    print(f"  Jarvis is online as: {client.user}")
    print(f"  Mention @{client.user.name} in any channel to talk.")
    print(f"  Press Ctrl+C to shut down.")
    print(f"─────────────────────────────────────────")


@client.event
async def on_message(message: discord.Message):
    # Ignore own messages
    if message.author == client.user:
        return

    # Only respond when @mentioned
    if client.user not in message.mentions:
        return

    # Strip the mention from the text
    user_text = message.content
    for mention in message.mentions:
        user_text = user_text.replace(f"<@{mention.id}>", "").replace(f"<@!{mention.id}>", "")
    user_text = user_text.strip()

    if not user_text:
        await message.reply("Yes, Sir? You appear to have summoned me without a question. Impressive commitment to ambiguity.")
        return

    # Show typing indicator while thinking
    async with message.channel.typing():
        uid = message.author.id
        if uid not in histories:
            histories[uid] = []

        histories[uid].append({"role": "user", "content": user_text})

        # Trim history to keep costs reasonable
        if len(histories[uid]) > MAX_HISTORY:
            histories[uid] = histories[uid][-MAX_HISTORY:]

        try:
            resp = claude.messages.create(
                model="claude-opus-5",
                max_tokens=1024,
                system=SYSTEM,
                messages=histories[uid],
            )
            reply_text = resp.content[0].text
            histories[uid].append({"role": "assistant", "content": reply_text})

            # Discord has a 2000 character limit — split if needed
            if len(reply_text) <= 2000:
                await message.reply(reply_text)
            else:
                chunks = [reply_text[i:i+1990] for i in range(0, len(reply_text), 1990)]
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await message.reply(chunk)
                    else:
                        await message.channel.send(chunk)

        except anthropic.APIError as e:
            await message.reply(f"I'm afraid I've encountered a slight malfunction, Sir. `{e}`")
        except Exception as e:
            await message.reply(f"Something appears to have gone wrong, Sir. `{e}`")


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("ERROR: DISCORD_BOT_TOKEN not set in .env")
        exit(1)
    if not ANTHROPIC_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set in .env")
        exit(1)
    client.run(DISCORD_TOKEN)
