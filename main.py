import discord
from discord.ext import commands

from config import *

import datetime


class Jocasta(commands.Bot):
	async def setup_hook(self):
		initial_extensions = [
			'funcs.postgresql',
			'cogs.owner',
			'cogs.polls',
		]

		for extension in initial_extensions:
			await bot.load_extension(extension)



intents = discord.Intents.all()

description = "Jocasta 3.0"
get_pre = lambda bot, message: BOT_PREFIX
bot = Jocasta(command_prefix=get_pre, description=description, intents=intents)

bot.recentcog = None

bot.tasks = {}

@bot.event
async def on_connect():
	print('Loaded Discord')
	activity = discord.Game(name="Starting up...")
	# await bot.change_presence(status=discord.Status.idle, activity=activity)

@bot.event
async def on_ready():
	print('------')
	print('Logged in as')
	print(bot.user.name)
	print(bot.user.id)
	print(discord.utils.utcnow().strftime("%d/%m/%Y %I:%M:%S:%f"))
	print('------')

	# statusactivity = f"discord.gg/marvel | Type {BOT_PREFIX}help"
	# await bot.change_presence(activity=discord.Game(name=statusactivity), status=discord.Status.online)


@bot.check
async def globally_block_dms(ctx):
	return ctx.guild is not None


bot.run(TOKEN, reconnect=True)