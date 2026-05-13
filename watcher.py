import os
import asyncio
import tempfile
from pathlib import Path
import aiohttp
import discord
from discord import app_commands
from config import DISCORD_BOT_TOKEN, DISCORD_CHANNEL_NAME, SUPPORTED_EXTENSIONS
from usage_tracker import get_monthly_summary

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

_process_fn = None
_delete_fn = None
_recategorize_fn = None

# Maps bot message ID -> {drive_file_id, drive_url} for deletion
_receipt_cache = {}

DELETE_EMOJI = "🚫"


@client.event
async def on_ready():
    await tree.sync()
    print(f"HSSave bot is online as {client.user}")
    print(f"Listening for receipts in #{DISCORD_CHANNEL_NAME}")
    print(f"React with the no-entry-sign emoji to any receipt confirmation to delete it.")
    print(f"Use /recategorize to update the HSA eligible amount for a receipt.\n")


@client.event
async def on_message(message):
    if message.author.bot:
        return
    if message.channel.name != DISCORD_CHANNEL_NAME:
        return
    if not message.attachments:
        return

    for attachment in message.attachments:
        ext = Path(attachment.filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue

        await message.add_reaction("⏳")

        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                image_data = await resp.read()

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(image_data)
            tmp_path = tmp.name

        try:
            submitted_by = message.author.display_name
            result = await asyncio.get_event_loop().run_in_executor(
                None, _process_fn, tmp_path, attachment.filename, submitted_by
            )
            await message.remove_reaction("⏳", client.user)
            await message.add_reaction("✅")

            usage = get_monthly_summary()
            notes = result.get("notes", "")
            notes_line = f"\n📝 {notes}" if notes else ""
            reply = await message.reply(
                f"**Receipt processed!**\n"
                f"🪪 ID: `{result.get('receipt_id', 'N/A')}`\n"
                f"🏪 Merchant: {result.get('merchant', 'Unknown')}\n"
                f"📅 Date: {result.get('receipt_date', 'Unknown')}\n"
                f"💰 Total: ${result.get('total', '0')}\n"
                f"🏥 HSA Eligible: ${result.get('hsa_eligible_amount', '0')}"
                f"{notes_line}\n"
                f"📁 [View in Drive]({result.get('drive_url', '')})\n"
                f"\n**Gemini Usage — {usage['month']}**\n"
                f"Tokens used: {usage['total_tokens']:,} ({usage['requests']} receipts)\n"
                f"Estimated cost: ${usage['estimated_cost']}\n"
                f"\nReact with {DELETE_EMOJI} to delete · `/recategorize {result.get('receipt_id', '')} <amount>` to fix HSA amount."
            )

            _receipt_cache[reply.id] = {
                "drive_file_id": result.get("drive_file_id", ""),
                "drive_url": result.get("drive_url", ""),
            }

        except Exception as e:
            await message.remove_reaction("⏳", client.user)
            await message.add_reaction("❌")
            await message.reply(f"Error processing receipt: {e}")
        finally:
            os.unlink(tmp_path)


@client.event
async def on_raw_reaction_add(payload):
    if payload.user_id == client.user.id:
        return
    if str(payload.emoji) != DELETE_EMOJI:
        return

    try:
        channel = await client.fetch_channel(payload.channel_id)
    except Exception:
        return
    if channel.name != DISCORD_CHANNEL_NAME:
        return

    if payload.message_id not in _receipt_cache:
        await channel.send("Could not find that receipt in this session. If the bot was restarted after the receipt was processed, deletion is not available for that receipt — please remove it manually from Drive and Sheets.")
        return

    receipt = _receipt_cache.pop(payload.message_id)

    try:
        await asyncio.get_event_loop().run_in_executor(
            None, _delete_fn, receipt["drive_file_id"], receipt["drive_url"]
        )
        message = await channel.fetch_message(payload.message_id)
        await message.edit(content="~~" + message.content + "~~\n\n**Receipt deleted.**")
        await channel.send("Receipt deleted from Drive and Sheets.")
    except Exception as e:
        await channel.send(f"Error deleting receipt: {e}")


@tree.command(name="recategorize", description="Update the HSA eligible amount for a receipt")
@app_commands.describe(
    receipt_id="The Receipt ID shown in the bot's confirmation (e.g. HSA-20260513-A3F2)",
    hsa_amount="The correct HSA eligible amount in dollars (e.g. 45.00)",
)
async def recategorize(interaction: discord.Interaction, receipt_id: str, hsa_amount: float):
    if interaction.channel.name != DISCORD_CHANNEL_NAME:
        await interaction.response.send_message(
            f"This command can only be used in #{DISCORD_CHANNEL_NAME}.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    try:
        success = await asyncio.get_event_loop().run_in_executor(
            None, _recategorize_fn, receipt_id, hsa_amount
        )
        if success:
            await interaction.followup.send(
                f"Updated `{receipt_id}` — HSA eligible amount set to **${hsa_amount:.2f}**. Dashboard refreshed.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f"Could not find receipt `{receipt_id}` in the spreadsheet. Double-check the ID and try again.",
                ephemeral=True,
            )
    except Exception as e:
        await interaction.followup.send(f"Error updating receipt: {e}", ephemeral=True)


def start_watching(process_fn, delete_fn, recategorize_fn):
    global _process_fn, _delete_fn, _recategorize_fn
    _process_fn = process_fn
    _delete_fn = delete_fn
    _recategorize_fn = recategorize_fn
    print("Starting HSSave Discord bot...")
    client.run(DISCORD_BOT_TOKEN)
