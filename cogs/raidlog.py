import asyncio, datetime, discord, re
from discord import *
from discord.app_commands import *
from discord.app_commands.tree import _log
from discord.ext import commands
from config import *


class RaidLogCog(discord.ext.commands.Cog, name = "Raid Log"):
	"""Raid Log commands"""

	def __init__(self, bot):
		self.bot = bot

		self.bot.tree.on_error = self.on_app_command_error

		self.servers = {s: None for s in raidlogservers}

		self.bot.loop.create_task(self.load_members())


	async def on_app_command_error(self, interaction: Interaction, error: AppCommandError):
		if isinstance(error, app_commands.errors.CheckFailure):
			return await interaction.response.send_message(f"You can't use this command!", ephemeral = True)

		await interaction.followup.send("Something broke!")
		_log.error('Ignoring exception in command %r', interaction.command.name, exc_info=error)


	async def load_members(self):
		g = None
		while g == None:
			g = self.bot.get_guild(288896937074360321)
			await asyncio.sleep(0.1)

		while True:
			for s in raidlogservers:
				self.servers[s] = self.bot.get_guild(s)

			for s in self.servers.values():
				await s.chunk()

			await asyncio.sleep(7200) # every 2 hours


	@commands.Cog.listener()
	async def on_raw_member_remove(self, payload):
		now = discord.utils.utcnow()

		if payload.guild_id not in raidlogservers: return

		channel = self.bot.get_guild(raidlogdest[0]).get_channel(raidlogdest[1])

		guild = self.bot.get_guild(payload.guild_id)
		user = payload.user

		if type(user) == discord.User:
			channel = self.bot.get_guild(288896937074360321).get_channel(1037676652433514526)
			await channel.send(f"{guild.name} - `{user.id}`")
			return


		join = user.joined_at
		diff = now - join

		if diff.days != 180: return

		txt = [
			f"{user.mention} - {str(user)}",
			f"**Joined:** <t:{int(join.timestamp())}:f>",
			f"**Left:** <t:{int(now.timestamp())}:f>",
			f"**Time in server:** {diff}",
			f"**Roles:** {', '.join(i.name for i in user.roles)}"
		]

		shared = []
		for s in self.servers.values():
			if s.id == guild.id: continue
			if user.id in [i.id for i in s.members]:
				shared.append(s)
		if shared:
			txt.append(f"\n🚨 **User is also in:** {','.join(s.name for s in shared)}")


		embed = discord.Embed(title = user.id, description = "\n".join(txt), color = raidlogservers[guild.id])
		embed.set_footer(text = guild.name)

		await channel.send(embed = embed)





async def setup(bot):
	await bot.add_cog(RaidLogCog(bot))