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

		try:
			await self.bot.db.execute("""
				create function commuted_regexp_match(text,text) returns bool as
				'select $2 ~* $1;'
				language sql;
			""")
		except asyncpg.exceptions.DuplicateFunctionError:
			pass

		try:
			await self.bot.db.execute("""
				create operator ~! (
	 				procedure=commuted_regexp_match(text,text),
	 				leftarg=text, rightarg=text
				);
			""")
		except asyncpg.exceptions.DuplicateFunctionError:
			pass

		p = await self.bot.db.fetch("SELECT * FROM polls WHERE $1 ~! ANY(choices)", "no")
		print(p)


async def setup(bot):
	await bot.add_cog(PostgreSQLCog(bot))