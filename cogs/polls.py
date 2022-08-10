import asyncio, asyncpg, datetime, discord, enum, random
from discord.ext import commands
from discord import app_commands

'''
x Create polls
x Delete polls
- View polls
- Edit polls
- Schedule polls
- Start polls

x SQL DB
x Slashies
- Schedule timer

- Add reaction adds to thread
'''

# id (int), num (int), time (datetime), message_id (int), question (str), thread_question (str), choices (str[]), tag (str), votes (int[]), image (str), duration (datetime), published (bool)


class PollsCog(commands.Cog, name = "Polls"):
	"""Polls commands"""


	def __init__(self, bot):
		self.bot = bot

		self.colour = 0xee171f

		self.tags = {
			self.Tags.comics: "comics",
			self.Tags.mcu: "mcu",
			None: None
		}

	class Tags(enum.Enum):
		comics = 1
		mcu = 2

	class Sort(enum.Enum):
		poll_id = 1
		newest = 2
		oldest = 3
		most_votes = 4
		least_votes = 5

	datetosql = lambda x: x.strftime('%Y-%m-%d %H:%M:%S')

	class Confirm(discord.ui.View):
		def __init__(self):
			super().__init__(timeout=60)
			self.value = None
			self.interaction = None

		@discord.ui.button(label='Confirm', style=discord.ButtonStyle.green)
		async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
			# await interaction.response.send_message('Confirming...', ephemeral=True)
			self.value = True
			self.interaction = interaction
			self.stop()

		@discord.ui.button(label='Cancel', style=discord.ButtonStyle.grey)
		async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
			# await interaction.response.send_message('Cancelling...', ephemeral=True)
			self.value = False
			self.interaction = interaction
			self.stop()


	@commands.command()
	@commands.is_owner()
	async def pools(self, ctx):

		# await self.bot.db.execute("INSERT INTO polls VALUES (1, null, null, null, 'test q', 'thread q', ARRAY ['a1', 'a2', 'a3'], 'comic', ARRAY [0, 0, 0])")
		# await self.bot.db.execute("INSERT INTO polls (id) VALUES (2)")

		# await self.bot.db.execute("DELETE FROM polls WHERE id=1")

		# a = await self.bot.db.fetchrow("SELECT id FROM polls")
		# print(type(a))
		# print(a['id'])

		print(bool(await self.bot.db.fetchrow("SELECT id FROM polls WHERE id = $1", 88375)))

		pass


	async def pollinfoembed(self, poll):
		if not poll['num']:
			embed = discord.Embed(title = poll['question'], colour = self.colour)
		else:
			embed = discord.Embed(title = f"{poll['num']}: {poll['question']}", colour = self.colour)

		if not poll['votes']:
			embed.add_field(name = "Choices", value = "\n".join([f'- {c}' for c in poll['choices']]), inline = False)
		else:
			embed.add_field(name = "Choices", value = "\n".join([f'- ({v}) {c}' for v, c in enumerate(poll['votes'], poll['choices'])]), inline = False)

		embed.add_field(name = "Published?", value = str(poll['published']), inline = False)

		if poll['thread_question']: embed.add_field(name = "Thread Question", value = poll['thread_question'])
		if poll['tag']: embed.add_field(name = "Tag", value = f"`{str(poll['tag'])}`")

		if poll['time']: embed.add_field(name = "Publish Date", value = poll['time'])
		if poll['duration']: embed.add_field(name = "Duration", value = poll['duration'])

		if poll['message_id']: 
			message = await self.bot.fetch_message(poll['message_id'])
			if message:
				embed.add_field(name = "Poll Message", value = f"[{question}]({message.jump_url})")
			else:
				embed.add_field(name = "Poll Message", value = f"Can't locate message {message_id}")

		if poll['image']: embed.set_image(url = poll['image'])

		embed.set_footer(text = poll['id'])

		return embed


	pollsgroup = app_commands.Group(name="polls", description="Poll commands", guild_ids=[288896937074360321])

	@pollsgroup.command(name="create")
	async def pollcreate(self, interaction: discord.Interaction, 
			question: str, 
			opt_1: str, opt_2: str, 
			thread_question: str = None,
			image: str = None,
			tag: Tags = None,
			opt_3: str = None, opt_4: str = None, opt_5: str = None, opt_6: str = None, opt_7: str = None, opt_8: str = None
		):
		"""Creates a poll question."""
		
		choices = [i for i in [opt_1, opt_2, opt_3, opt_4, opt_5, opt_6, opt_7, opt_8] if i]
		tag = self.tags[tag]

		while True:
			pollid = random.randint(10000, 99999)
			if not await self.bot.db.fetchrow("SELECT id FROM polls WHERE id = $1", pollid):
				break

		# id (int), num (int), time (datetime), message_id (int), question (str), thread_question (str), choices (str[]), tag (str), votes (int[]), image (str), duration (datetime), published (bool)
		await self.bot.db.execute(
			f"INSERT INTO polls VALUES ($1, null, null, null, $2, $3, $4, $5, null, $6, null, false)", 
			pollid, question, thread_question, choices, tag, image
		)

		embed = discord.Embed(title = question, colour = self.colour, timestamp=discord.utils.utcnow())
		embed.add_field(name = "Choices", value = "\n".join([f'- {i}' for i in choices]), inline = False)
		embed.add_field(name = "Thread Question", value = thread_question if thread_question else "`None`")
		embed.add_field(name = "Tag", value = f"`{str(tag)}`")
		if image: embed.set_image(url = image)
		embed.set_footer(text = pollid)

		await interaction.response.send_message(f'Created new poll question: "{question}"', embed = embed)

	@pollsgroup.command(name="delete")
	async def polldelete(self, interaction: discord.Interaction, poll_id: int):
		"""Deletes a poll question."""

		poll = await self.bot.db.fetchrow("SELECT * FROM polls WHERE id = $1", poll_id)

		if not poll:
			return await interaction.response.send_message(f"Couldn't find a poll with the ID `{poll_id}`.")

		if poll['published']:
			return await interaction.response.send_message(f"This poll has already been published, and cannot be deleted.")

		view = self.Confirm()
		embed = await self.pollinfoembed(poll)

		msg = await interaction.response.send_message(f"Do you want to delete this poll question?", embed=embed, view=view)

		await view.wait()

		if view.value is None:
			return await view.interaction.response.send_message(content = "Timed out.")
		elif view.value:
			await self.bot.db.execute("DELETE FROM polls WHERE id = $1", poll_id)

			recreate = ["/polls create", f"question: {poll['question']}"]
			recreate += [f"opt_{i}: c" for c, i in zip(poll['choices'], range(1, len(poll['choices']) + 1))]
			if poll['thread_question']: recreate.append(f"thread_question: {poll['thread_question']}")
			if poll['image']: recreate.append(f"image: {poll['image']}")
			if poll['tag']: recreate.append(f"tag: {poll['tag']}")
			recreatemsg = ' '.join(recreate)

			await view.interaction.response.send_message(content = f"Deleted the poll question.\n\nTo recreate this poll, type:\n`{recreatemsg}`\n\n`WIP`")
		else:
			return await view.interaction.response.send_message(content = "Cancelled.")

	@pollsgroup.command(name="search")
	async def pollsearch(self, interaction: discord.Interaction,
			poll_id: int = None,
			sort: Sort = None,
			tag: Tags = None,
		):
		"""Searches poll questions."""

		if poll_id:
			poll = await self.bot.db.fetchrow("SELECT * FROM polls WHERE id = $1", poll_id)

			if not poll:
				return await interaction.response.send_message(f"Couldn't find a poll with the ID `{poll_id}`.")

			embed = await self.pollinfoembed(poll)

			await interaction.response.send(embed=embed)
			# add shortcut buttons to delete (and edit maybe?)

			return
			



		


async def setup(bot):
	await bot.add_cog(PollsCog(bot))