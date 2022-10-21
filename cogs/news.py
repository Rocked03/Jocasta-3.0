import asyncio, datetime, discord, re
from discord import *
from discord.app_commands import *
from discord.app_commands.tree import _log
from discord.ext import commands
from config import *


class NewsCog(discord.ext.commands.Cog, name = "News"):
	"""News commands"""

	def __init__(self, bot):
		self.bot = bot

		self.bot.tree.on_error = self.on_app_command_error

		self.newsguild = None
		self.newsrole = None

		self.bot.loop.create_task(self.on_startup_scheduler())


	async def on_app_command_error(self, interaction: Interaction, error: AppCommandError):
		if isinstance(error, app_commands.errors.CheckFailure):
			return await interaction.response.send_message(f"You can't use this command!", ephemeral = True)

		await interaction.followup.send("Something broke!")
		_log.error('Ignoring exception in command %r', interaction.command.name, exc_info=error)


	async def on_startup_scheduler(self):
		channel = None
		while channel == None:
			channel = self.bot.get_channel(newschannels[0])
			await asyncio.sleep(0.1)
		self.newsguild = channel.guild
		self.newsrole = self.newsguild.get_role(newspingrole)
		self.bot.add_view(self.PingRoleView(self.newsrole, "Add/Remove Ping Role"))



	guild_ids = [281648235557421056, 288896937074360321, 1010550869391065169]
	newspinggroup = app_commands.Group(name="newsping", description="News Ping commands", guild_ids=guild_ids)



	class PingRoleView(discord.ui.View):
		def __init__(self, role, text):
			super().__init__(timeout=None)

			self.add_item(self.SelfAssignButton(
				role,
				label = text,
				custom_id = str(role.id),
				style = discord.ButtonStyle.grey
				))

		class SelfAssignButton(discord.ui.Button):
			def __init__(self, role, **kwargs):
				super().__init__(**kwargs)
				self.role = role

			async def callback(self, interaction: discord.Interaction):
				user = interaction.user

				if self.role in user.roles:
					await user.remove_roles(self.role)
					await interaction.response.send_message(f"**Removed** the {self.role.mention} role", ephemeral = True)
				else:
					await user.add_roles(self.role)
					await interaction.response.send_message(f"**Added** the {self.role.mention} role", ephemeral = True)


	@commands.Cog.listener()
	async def on_message(self, message):
		if message.channel.id in newschannels:
			if message.author.id == self.bot.user.id: 
				return

			try:
				await message.publish()
			except discord.errors.Forbidden:
				pass


			await self.send_news_ping(message)


	@commands.Cog.listener()
	async def on_message_edit(self, before, message):
		if message.channel.id in newschannels:
			if message.author.id == self.bot.user.id:
				return

			await self.send_news_ping(message)


	async def send_news_ping(self, message):
		if (discord.utils.utcnow() - message.created_at).total_seconds() >= newspingbuffertime:
			return


		urlregex = "(https?:\/\/)?([\da-z\.-]+)\.([a-z\.]{2,6})([\/\w \.-]*)"

		titles = set()
		for e in message.embeds:
			if e.footer.text == "Twitter":
				desc = [i for i in e.description.split(' ') if not re.match(urlregex, i)]
				titles.add(' '.join(desc))
			else:
				titles.add(e.title)

		titles = {i for i in titles if i and not any(j.startswith(i.strip('...')) and j != i for j in titles)}

		if len(re.findall(urlregex, message.content)) != len(message.embeds):
			return


		channel = message.channel


		formatmsg = lambda mention, titles: f"{mention} " + '\n'.join(f"*{t}*" for t in titles)

		channelinfo = await self.bot.db.fetchrow("SELECT * FROM newschannelsping WHERE channel_id = $1", channel.id)
		if channelinfo:
			if channelinfo['latest_message_id']:
				try:
					oldmsg = await channel.fetch_message(channelinfo['latest_message_id'])
				except NotFound:
					pass
				else:
					if (discord.utils.utcnow() - oldmsg.created_at).total_seconds() >= newspingbuffertime:
						await oldmsg.delete()
					else:
						print(2)
						current = [i.strip('*') for i in oldmsg.content.replace(f"{self.newsrole.mention} ").split('\n')]
						for t in titles:
							if t not in current:
								current.append(t)
						new = formatmsg(self.newsrole.mention, current)
						await oldmsg.edit(content = new)
						return
		else:
			await self.bot.db.execute("INSERT INTO newschannelsping (channel_id) VALUES ($1)", channel.id)

		msg = await channel.send(
			formatmsg(self.newsrole.mention, titles),
			view = self.PingRoleView(self.newsrole, "Add/Remove Ping Role"))

		await self.bot.db.execute("UPDATE newschannelsping SET latest_message_id = $2 WHERE channel_id = $1", channel.id, msg.id)



	@commands.Cog.listener()
	async def on_member_join(self, member):
		if member.guild.id == self.newsguild.id:
			await member.add_roles(self.newsrole)



	@newspinggroup.command(name="button")
	@app_commands.describe(message = "Message to send with button. (optional)")
	async def newspingbutton(self, interaction: discord.Interaction, message: str):
		"""Generates a message with the news ping role button."""
		role = interaction.guild.get_role(newspingrole)
		if not role: return interaction.response.send_message("Cannot access role in this server!", ephemeral = True)

		view = self.PingRoleView(role, "Add/Remove Ping Role")

		await interaction.channel.send(message, view=view)
		await interaction.response.send_message("Sent!", ephemeral = True)



async def setup(bot):
	await bot.add_cog(NewsCog(bot))