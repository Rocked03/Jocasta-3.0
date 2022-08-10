import discord
from discord.ext import commands
import asyncio
import asyncpg


class PostgreSQLCog(commands.Cog, name = "PostgreSQL"):
	"""Loads PostgreSQL"""

	def __init__(self, bot):
		self.bot = bot

		self.credentials = {"user": "jocasta", "password": "Obsidian", "database": "jocasta", "host": "188.166.191.180"}
		self.bot.loop.create_task(self.loadPostgreSQL())

	async def loadPostgreSQL(self):
		self.bot.db = await asyncpg.create_pool(**self.credentials)


async def setup(bot):
	await bot.add_cog(PostgreSQLCog(bot))