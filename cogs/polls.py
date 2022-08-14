import asyncio, asyncpg, datetime, discord, enum, random, re
from discord.ext import commands
from discord import *
from discord.app_commands import *
from funcs.buttonpaginator import *

'''
x Create polls
x Delete polls
x View polls
x Search polls
- Edit polls
x Schedule polls
- Start polls

x SQL DB
x Slashies
- Schedule timer

- Vote on poll
  - update message function
  - update votes values in SQL function
- Add reaction adds to thread


- add description to poll qs
- add server to poll qs
- tags stored in SQL
- poll info per server
  - server id
  - manager role
  - tags
  - external command channel access
  - colour
- Search polls only by server
- Search all polls
- Server/channel/message IDs for crossposts
'''

# id (int), num (int), time (datetime), message_id (int), question (str), thread_question (str), choices (str[]), tag (str), votes (int[]), image (str), published (bool), duration (datetime)


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

	choices = {}

	choices['tags'] = [
		Choice(name="Comics", value="comics"),
		Choice(name="MCU", value="mcu")
	]
	findtag = lambda self, x: self.findchoice(self.choices['tags'], x)

	class Sort(enum.Enum):
		poll_id = "Poll ID"
		newest = "Newest"
		oldest = "Oldest"
		most_votes = "Most votes"
		least_votes = "Least votes"
	choices['sort'] = [Choice(name=v.value, value=e) for e, v in dict(Sort.__members__).items()]


	datetosql = lambda self, x: x.strftime('%Y-%m-%d %H:%M:%S')
	strf = lambda self, x: x.strftime('%a, %b %m, %Y ~ %I:%M:%S %p %Z').replace(" 0", " ")
	# Sun, Mar 6, 2022 ~ 3:30 PM UTC
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

		# print(bool(await self.bot.db.fetchrow("SELECT id FROM polls WHERE id = $1", 88375)))


		# await self.bot.db.execute(f"UPDATE polls SET time = $1, duration = $2 WHERE id = $3", discord.utils.utcnow(), datetime.timedelta(seconds=100), 63830)

		a = await self.bot.db.fetchrow("SELECT * FROM polls WHERE id = $1", 63830)
		print(type(a['time']), a['time'])
		print(type(a['duration']), a['duration'])


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

		embed.add_field(name = "Published?", value = poll['published'], inline = False)

		if poll['thread_question']: embed.add_field(name = "Thread Question", value = poll['thread_question'])
		if poll['tag']: embed.add_field(name = "Tag", value = f"`{self.findtag(poll['tag']).name}`")

		if poll['time']: embed.add_field(name = "Publish Date", value = f"<t:{int(poll['time'].timestamp())}:F>")
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


	async def searchpollsbyid(self, pollid, showunpublished = False):
		return await self.bot.db.fetch("SELECT id, question FROM polls WHERE CAST(id AS TEXT) LIKE $1", f"{pollid}%")

	async def searchpollsbykeyword(self, keyword, showunpublished = False):
		return await self.bot.db.fetch("SELECT id, question FROM polls WHERE question ~* $1", keyword)


	pollsgroup = app_commands.Group(name="polls", description="Poll commands", guild_ids=[288896937074360321])

	@pollsgroup.command(name="create")
	@app_commands.describe(
		question = "Main Poll Question to ask.",
		opt_1 = "Option 1.", opt_2 = "Option 2.", opt_3 = "Option 3.", opt_4 = "Option 4.", opt_5 = "Option 5.", opt_6 = "Option 6.", opt_7 = "Option 7.", opt_8 = "Option 8.",
		thread_question = "Question to ask in the accompanying Thread.",
		image = "Image to accompany Poll Question.",
		tag = "Tag categorising this Poll Question."
	)
	@app_commands.choices(tag=choices['tags'])
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

		# id (int), num (int), time (datetime), message_id (int), question (str), thread_question (str), choices (str[]), tag (str), votes (int[]), image (str), published (bool), duration (datetime)
		await self.bot.db.execute(
			f"INSERT INTO polls VALUES ($1, null, null, null, $2, $3, $4, $5, null, $6, false, null)", 
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

		if sort == self.Sort.newest: key = lambda x: x['time'].timestamp() * -1 if x['time'] else 1
		elif sort == self.Sort.oldest: key = lambda x: x['time'].timestamp() if x['time'] else 99999999999999999999999999999999
		elif sort == self.Sort.most_votes: key = lambda x: sum(x['votes']) * -1 if x['votes'] else 1
		elif sort == self.Sort.least_votes: key = lambda x: sum(x['votes']) if x['votes'] else 99999999999999999999999999999999
		else: key = None

		if key: polls.sort(key = key)

		return polls


	async def autocomplete_searchbypollid(self, interaction: discord.Interaction, current: int):
		if current.isdigit():
			current = int(current)
			if current <= 99999:
				results = await self.searchpollsbyid(current)
				results.sort(key = lambda x: x['id'])
			else:
				results = []
		else:
			results = await self.searchpollsbykeyword(current)
			print(results)
			lowered = current.lower()
			regex = [f"^\b{lowered}\b", f"\b{lowered}\b", f"^{lowered}", lowered]
			results.sort(key = lambda x: [bool(re.search(i, x['question'].lower())) for i in regex].index(True))

		choices = [app_commands.Choice(name = f"[{i['id']}] {i['question']}", value = str(i['id'])) for i in results[:25]]
		return choices

	@pollsgroup.command(name="search")
	@app_commands.describe(
		poll_id = "The ID (5-digit or #) of the poll to search for.",
		keyword = "Keyword to search for. Searches the question and thread question. Case-insensitive.",
		sort = "Order to list results.",
		tag = "Tag to filter results by.",
		published = "List published or unpublished questions only. Unpublished polls are only visible to Poll Managers."
	)
	@app_commands.choices(tag=choices['tags'], sort=choices['sort'])
	async def pollsearch(self, interaction: discord.Interaction,
			poll_id: int = None,
			keyword: str = None,
			sort: Choice[str] = Sort.poll_id.name,
			tag: Choice[str] = None,
			published: bool = None
		):
		"""Searches poll questions. Search by poll ID, or by keyword, and filter by tag."""

		sort = self.Sort.__members__[sort.value if not isinstance(sort, str) else sort]

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
				queries.append("(question ~* ${} OR thread_question ~* ${} OR ${} ~! ANY(choices))")
				values += [keyword, keyword, keyword]
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


			polls = self.sortpolls(polls, sort)

			await interaction.response.send_message("Searching...")

			class PollSearchPaginator(BaseButtonPaginator):
				text = None
				colour = None

				async def format_page(self, entries):
					embed = discord.Embed(title = "Polls Search", description = "\n".join(self.text), colour = self.colour, timestamp=discord.utils.utcnow())
					if entries: results = [f"""`{i['id']}`{f' (`#{i["num"]}`)' if i['num'] else ''}: {i['question']}{' (<t:'+str(int(i['time'].timestamp()))+':d>)' if i['time'] else ''}""" for i in entries]
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

	@pollsearch.autocomplete("poll_id")
	async def pollsearch_autocomplete_poll_id(self, interaction: discord.Interaction, current: int):
		return await self.autocomplete_searchbypollid(interaction, current)


	@pollsgroup.command(name="schedule")
	@app_commands.describe(
		poll_id = "The 5-digit ID of the poll to schedule.",
		schedule_time = "Scheduled time for the poll to start. Given in Epoch timestamp (UTC). Leave empty if published, or want to leave the scheduled date unchanged. Set to -1 to clear.",
		duration = "Duration for poll to run. Can pass Epoch timestamp (UTC) as the ending time instead. Can give number of seconds as raw value. Set to -1 to clear.",
	)
	async def pollschedule(self, interaction: discord.Interaction, 
			poll_id: str,
			schedule_time: int = None, 
			duration: float = None
		):
		"""Schedules polls for publishing"""

		clearschedule = schedule_time == -1
		if clearschedule: schedule_time = None

		end_time = duration if duration >= discord.utils.utcnow().timestamp() else None
		if end_time: duration = None

		poll = await self.bot.db.fetchrow("SELECT * FROM polls WHERE id = $1", poll_id)

		if not poll:
			return await interaction.response.send_message(f"Couldn't find a poll with the ID `{poll_id}`.")

		if poll['published']:
			if schedule_time:
				return await interaction.response.send_message(f"This poll has already been published, therefore the start time cannot be rescheduled.")
			else:
				schedule_time = poll['time'].timestamp()

		current = discord.utils.utcnow()


		if not schedule_time and not poll['published']:
			if poll['time']:
				schedule_time = poll['time'].timestamp()

		if schedule_time:
			scheduled = datetime.datetime.fromtimestamp(schedule_time, datetime.timezone.utc)

			if end_time:
				end = datetime.datetime.fromtimestamp(end_time, datetime.timezone.utc)
				duration = end_time - scheduled.timestamp()
			else:
				end = None

			if (scheduled - current).total_seconds() < 0:
				return await interaction.response.send_message(f"You're trying to schedule a message in the past! <t:{int(schedule_time)}:F>, <t:{int(schedule_time)}:R>")

			if end and (end_time - schedule_time) < 0:
				return await interaction.response.send_message(f"You're trying to end the poll before it starts! (Starting <t:{int(schedule_time)}:F> but ending <t:{int(end.timestamp())}:F>")

		else:
			if end_time:
				return await interaction.response.send_message("You can't set an end time without a start time!")

		if clearschedule:
			schedule_time = None
			scheduled = None
		if schedule_time != poll['time'] or clearschedule:
			await self.bot.db.execute(f"UPDATE polls SET time = $1 WHERE id = $2", scheduled, poll_id)
		if duration:
			durationtimedelta = datetime.timedelta(seconds=duration)
			if duration == -1: durationtimedelta = None
			await self.bot.db.execute(f"UPDATE polls SET duration = $1 WHERE id = $2", durationtimedelta, poll_id)


		poll = await self.bot.db.fetchrow("SELECT * FROM polls WHERE id = $1", poll_id)

		embed = discord.Embed(title = "Scheduled Poll", description = f"{poll['question']}", colour = self.colour, timestamp = discord.utils.utcnow())
		embed.set_footer(text = f"ID: {poll['id']}" + f'''{f" (#{poll['num']})" if poll['num'] else ""}''')
		embed.add_field(name = "Start time", value = f"<t:{int(poll['time'].timestamp())}:F>\n`{int(poll['time'].timestamp())}`" if poll['time'] else "No time scheduled.")
		embed.add_field(name = "End time", value = f"<t:{int((poll['time']+poll['duration']).timestamp())}:F> - lasts {poll['duration']}\n`{int(poll['duration'].total_seconds())}`" if poll['time'] and poll['duration'] else f"Lasts {poll['duration']}\n`{int(poll['duration'].total_seconds())}`" if poll['duration'] else "No end time scheduled.")

		return await interaction.response.send_message(embed=embed)

	@pollschedule.autocomplete("poll_id")
	async def pollschedule_autocomplete_poll_id(self, interaction: discord.Interaction, current: int):
		return await self.autocomplete_searchbypollid(interaction, current)

	@pollschedule.autocomplete("duration")
	async def pollschedule_autocomplete_duration(self, interaction: discord.Interaction, current: float):
		current = float(current)
		if current == -1:
			return [app_commands.Choice(name = f"Clear duration value.", value = int(current))]
		elif current < discord.utils.utcnow().timestamp():
			ranges = {
				"seconds": "second",
				"minutes": "minute",
				"hours": "hour",
				"days": "day",
				"weeks": "week"
			}
			times = []
			for k, v in ranges.items():
				try:
					times.append([datetime.timedelta(**{k: current}), v])
				except OverflowError:
					next

			choices = []
			for t in times:
				secs = int(round(t[0].total_seconds(), 0))
				if 15 <= secs <= 60480000: # Between 15s and 100w
					f = lambda x: int(x) if x.is_integer() else x
					choices.append(app_commands.Choice(name = f"{f(current)} {t[1]}{self.s(f(current))}", value = secs))
			return choices

		else:
			try:
				time = datetime.datetime.fromtimestamp(current, datetime.timezone.utc)
				return [app_commands.Choice(name = f"End at: {self.strf(time)}", value = int(current))]
			except (OSError, OverflowError):
				return []
		return []

	@pollschedule.autocomplete("schedule_time")
	async def pollschedule_autocomplete_schedule_time(self, interaction: discord.Interaction, current: int):
		current = int(current)
		if current == -1:
			return [app_commands.Choice(name = f"Clear scheduled time.", value = current)]
		elif current >= int(discord.utils.utcnow().timestamp()):
			try:
				time = datetime.datetime.fromtimestamp(current, datetime.timezone.utc)
				return [app_commands.Choice(name = f"{self.strf(time)}", value = int(current))]
			except (OSError, OverflowError):
				return []
		return []


	@pollschedule.error
	async def on_pollschedule_error(self, interaction: discord.Interaction, error: AppCommandError):
		pass
		# print("\n\n")
		# print(error)
		# print("\n\n")
		# if isinstance(error, ValueError):
		# 	return





async def setup(bot):
	await bot.add_cog(PollsCog(bot))