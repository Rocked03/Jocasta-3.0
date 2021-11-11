import discord
from discord.ext import commands

from config import *

import datetime


description = "Jocasta"
bot = commands.Bot(command_prefix=commands.when_mentioned_or(BOT_PREFIX), description=description)


initial_extensions = [
]

if __name__ == '__main__':
    for extension in initial_extensions:
        bot.load_extension(extension)

bot.recentcog = None

@bot.event
async def on_connect():
    print('Loaded Discord')
    activity = discord.Game(name="Starting up...")
    await bot.change_presence(status=discord.Status.idle, activity=activity)

@bot.event
async def on_ready():
    print('------')
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print(discord.utils.utcnow().strftime("%d/%m/%Y %I:%M:%S:%f"))
    print('------')

    statusactivity = f"discord.gg/marvel | Type {BOT_PREFIX}help"
    await bot.change_presence(activity=discord.Game(name=statusactivity), status=discord.Status.online)


@bot.check
async def globally_block_dms(ctx):
    return ctx.guild is not None


bot.run(TOKEN, reconnect=True)