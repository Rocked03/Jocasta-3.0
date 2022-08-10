import asyncio, asyncpg, datetime, discord, enum, random
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice
from funcs.buttonpaginator import *

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

		self.bot.pollmanagers = [289238128860856320]

		self.sort = {
			self.Sort.poll_id: "Poll ID",
			self.Sort.newest: "Newest",
			self.Sort.oldest: "Oldest",
			self.Sort.most_votes: "Most votes",
			self.Sort.least_votes: "Least votes"
		}

	class Tags(enum.Enum):
		comics = 1
		mcu = 2

	findchoice = lambda self, choices, x: [i for i in choices if i.value == x][0]

	tagschoices = [
		Choice(name="Comics", value="comics"),
		Choice(name="MCU", value="mcu")
	]
	findtag = lambda self, x: self.findchoice(self.tagschoices, x)

	class Sort(enum.Enum):
		poll_id = "Poll ID"
		newest = "Newest"
		oldest = "Oldest"
		most_votes = "Most votes"
		least_votes = "Least votes"

	sortchoices = [Choice(name=v.value, value=e) for e, v in dict(Sort.__members__).items()]


	datetosql = lambda self, x: x.strftime('%Y-%m-%d %H:%M:%S')
	s = lambda self, x: "" if x == 1 else "s"

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
			await self.interaction.response.defer()
			self.stop()

		@discord.ui.button(label='Cancel', style=discord.ButtonStyle.grey)
		async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
			# await interaction.response.send_message('Cancelling...', ephemeral=True)
			self.value = False
			self.interaction = interaction
			await self.interaction.response.defer()
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
		if poll['tag']: embed.add_field(name = "Tag", value = f"`{self.findtag(poll['tag']).name}`")

		if poll['time']: embed.add_field(name = "Publish Date", value = poll['time'])
		if poll['duration']: embed.add_field(name = "Duration", value = poll['duration'])

		if poll['message_id']: 
			message = await self.bot.fetch_message(poll['message_id'])
			if message:
				embed.add_field(name = "Poll Message", value = f"[{question}]({message.jump_url})")
			else:
				embed.add_field(name = "Poll Message", value = f"Can't locate message {message_id}")

		if poll['image']: embed.set_image(url = poll['image'])

		embed.set_footer(text = f"ID: {poll['id']}")

		return embed


	pollsgroup = app_commands.Group(name="polls", description="Poll commands", guild_ids=[288896937074360321])

	@pollsgroup.command(name="create")
	@app_commands.describe(
		question = "Main Poll Question to ask.",
		opt_1 = "Option 1.", opt_2 = "Option 2.", opt_3 = "Option 3.", opt_4 = "Option 4.", opt_5 = "Option 5.", opt_6 = "Option 6.", opt_7 = "Option 7.", opt_8 = "Option 8.",
		thread_question = "Question to ask in the accompanying Thread.",
		image = "Image to accompany Poll Question.",
		tag = "Tag categorising this Poll Question."
	)
	@app_commands.choices(tag=tagschoices)
	async def pollcreate(self, interaction: discord.Interaction, 
			question: str, 
			opt_1: str, opt_2: str, 
			thread_question: str = None,
			image: str = None,
			tag: Choice[str] = None,
			opt_3: str = None, opt_4: str = None, opt_5: str = None, opt_6: str = None, opt_7: str = None, opt_8: str = None
		):
		"""Creates a poll question."""
		
		choices = [i for i in [opt_1, opt_2, opt_3, opt_4, opt_5, opt_6, opt_7, opt_8] if i]

		while True:
			pollid = random.randint(10000, 99999)
			if not await self.bot.db.fetchrow("SELECT id FROM polls WHERE id = $1", pollid):
				break

		# id (int), num (int), time (datetime), message_id (int), question (str), thread_question (str), choices (str[]), tag (str), votes (int[]), image (str), duration (datetime), published (bool)
		await self.bot.db.execute(
			f"INSERT INTO polls VALUES ($1, null, null, null, $2, $3, $4, $5, null, $6, null, false)", 
			pollid, question, thread_question, choices, tag.value, image
		)

		embed = discord.Embed(title = question, colour = self.colour, timestamp=discord.utils.utcnow())
		embed.add_field(name = "Choices", value = "\n".join([f'- {i}' for i in choices]), inline = False)
		embed.add_field(name = "Thread Question", value = thread_question if thread_question else "`None`")
		embed.add_field(name = "Tag", value = f"`{tag.name}`")
		if image: embed.set_image(url = image)
		embed.set_footer(text = pollid)

		await interaction.response.send_message(f'Created new poll question: "{question}"', embed = embed)


	@pollsgroup.command(name="delete")
	@app_commands.describe(poll_id = "The 5-digit ID of the poll to delete.")
	async def polldelete(self, interaction: discord.Interaction, poll_id: int):
		"""Deletes a poll question."""

		poll = await self.bot.db.fetchrow("SELECT * FROM polls WHERE id = $1", poll_id)

		if not poll:
			return await interaction.response.send_message(f"Couldn't find a poll with the ID `{poll_id}`.")

		if poll['published']:
			return await interaction.response.send_message(f"This poll has already been published, and cannot be deleted.")

		view = self.Confirm()
		embed = await self.pollinfoembed(poll)

		await interaction.response.send_message(embed = embed)

		msg = await (await interaction.original_response()).reply(f"Do you want to delete this poll question?", view = view)

		await view.wait()

		for child in view.children:
			child.disabled = True

		if view.value is None:
			await msg.edit(content = "Timed out.", view = view)
		elif view.value:
			await self.bot.db.execute("DELETE FROM polls WHERE id = $1", poll_id)

			recreate = ["/polls create", f"question: {poll['question']}"]
			recreate += [f"opt_{i}: c" for c, i in zip(poll['choices'], range(1, len(poll['choices']) + 1))]
			if poll['thread_question']: recreate.append(f"thread_question: {poll['thread_question']}")
			if poll['image']: recreate.append(f"image: {poll['image']}")
			if poll['tag']: recreate.append(f"tag: {self.findtag(poll['tag']).name}")
			recreatemsg = ' '.join(recreate)

			await msg.edit(content = f"Deleted the poll question.\n\nTo recreate this poll, type:\n`{recreatemsg}`\n\n`WIP`", view = view)
		else:
			await msg.edit(content = "Cancelled.", view = view)


	def sortpolls(self, polls: list, sort: Sort = Sort.poll_id):
		# poll id, newest, oldest, most votes, least votes
		polls.sort(key = lambda x: x['id']) # default poll id order

		if sort == self.Sort.newest: key = lambda x: x['time'].total_seconds * -1 if x['time'] else 1
		elif sort == self.Sort.oldest: key = lambda x: x['time'].total_seconds if x['time'] else 9999999
		elif sort == self.Sort.most_votes: key = lambda x: sum(x['votes']) * -1 if x['votes'] else 1
		elif sort == self.Sort.least_votes: key = lambda x: sum(x['votes']) if x['votes'] else 9999999
		else: key = None

		if key: polls.sort(key = key)

		return polls


	@pollsgroup.command(name="search")
	@app_commands.describe(
		poll_id = "The ID (5-digit or #) of the poll to search for.",
		keyword = "Keyword to search for. Searches the question and thread question. Case-insensitive.",
		sort = "Order to list results.",
		tag = "Tag to filter results by.",
		published = "List published or unpublished questions only. Unpublished polls are only visible to Poll Managers."
	)
	@app_commands.choices(tag=tagschoices, sort=sortchoices)
	async def pollsearch(self, interaction: discord.Interaction,
			poll_id: int = None,
			keyword: str = None,
			sort: Choice[str] = Sort.poll_id.name,
			tag: Choice[str] = None,
			published: bool = None
		):
		"""Searches poll questions. Search by poll ID, or by keyword, and filter by tag."""

		sort = self.Sort.__members__[sort.value]

		if poll_id:
			poll = await self.bot.db.fetchrow("SELECT * FROM polls WHERE id = $1", poll_id)

			if not poll: poll = await self.bot.db.fetchrow("SELECT * FROM polls WHERE num = $1", poll_id)

			if not poll or (not poll['published'] and not any([i.id in self.bot.pollmanagers for i in interaction.user.roles])):
				return await interaction.response.send_message(f"Couldn't find a poll with the ID `{poll_id}`.")

			embed = await self.pollinfoembed(poll)

			await interaction.response.send_message(embed=embed)
			# add shortcut buttons to delete (and edit maybe?)

			return

		else:
			queries = []
			values = []
			text = []
			# keyword, tag, published
			if keyword:
				queries.append("(question ~* ${} OR thread_question ~* ${})")
				values += [keyword, keyword]
				text.append(f"Keyword search: `{keyword}`")
			if tag:
				queries.append("tag = ${}")
				values.append(tag.value)
				text.append(f"Tag: `{tag.name}`")
			if published is not None:
				queries.append("published = ${}")
				values.append(published)
				text.append(f"Published? `{published}`")
			if sort:
				text.append(f"Sorted by `{sort.name}`")

			try:
				if not queries: polls = await self.bot.db.fetch("SELECT * FROM polls")
				else: polls = await self.bot.db.fetch(f"SELECT * FROM polls WHERE {'AND'.join(queries).format(*list(range(1, len(values) + 1)))}", *values)
			except asyncpg.exceptions.InvalidRegularExpressionError:
				return await interaction.response.send_message(f"Your keyword input `{keyword}` seems to have failed. Please make sure to only search using alpha-numeric characters.")

			polls = self.sortpolls(polls, sort.value)

			await interaction.response.send_message("Searching...")

			class PollSearchPaginator(BaseButtonPaginator):
				text = None
				colour = None

				async def format_page(self, entries):
					embed = discord.Embed(title = "Polls Search", description = "\n".join(self.text), colour = self.colour, timestamp=discord.utils.utcnow())
					if entries: results = [f"""`{i['id']}`{f' (`#{i["num"]}`)' if i['num'] else ''}: {i['question']}""" for i in entries]
					else: results = "No results."
					embed.add_field(name = "Results", value = '\n'.join(results))
					
					embed.set_footer(text=f'Page {self.current_page}/{self.total_pages} ({len(self.entries)} results)')
					
					return embed

			PollSearchPaginator.text = text
			PollSearchPaginator.colour = self.colour

			paginator = await PollSearchPaginator.start(await interaction.original_response(), entries=polls, per_page=15)
			await paginator.wait()

			for child in paginator.children:
			    child.disabled = True
			paginator.stop()

			return await paginator.msg.edit(content="Timed out.", view=paginator)


	# @pollsgroup.command(name="schedule")
	# async def pollschedule(self, interaction: discord.Interaction, schedule_time: int = None, duration: )



async def setup(bot):
	await bot.add_cog(PollsCog(bot))