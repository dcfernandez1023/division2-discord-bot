from discord.ext import commands
from discord import Intents

from vendor import track_item, untrack_item, get_tracking

import os


bot = commands.Bot(command_prefix="/")


@bot.event
async def on_ready():
    print(f"{bot.user.name} has connected to Discord!")

@bot.slash_command()
async def track(ctx, arg):
    try:
        await ctx.defer()
        result = track_item(ctx.author.name, arg)
        if result == "exceeded":
            await ctx.followup.send("❌ Limit exceeded - there are currently 100 items being tracked. Please use the /untrack command to untrack these items.")
        elif result:
            await ctx.followup.send("✅ The item you entered is currently in the vendor!")
        else:
            await ctx.followup.send("✅ Now tracking '%s'. I will send a notification to this channel if it appears in the vendor." % arg)
    except Exception as e:
        print(e)
        await ctx.followup.send("❌ Failed to track item. Please try again.")

@bot.slash_command()
async def untrack(ctx, arg):
    try:
        await ctx.defer()
        untrack_item(arg)
        await ctx.followup.send("✅ '%s' is no longer being tracked." % arg)
    except Exception as e:
        print(e)
        await ctx.followup.send("❌ Failed to untrack item. Please try again.")

@bot.slash_command()
async def tracking(ctx):
    try:
        await ctx.defer()
        tracking = get_tracking()
        await ctx.followup.send(tracking)
    except Exception as e:
        print(e)
        await ctx.followup.send("❌ Failed to get list of tracked items. Please try again.") 

bot.run(os.environ.get("DISCORD_BOT_API_TOKEN"))
