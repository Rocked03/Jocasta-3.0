import asyncio, asyncpg, datetime, discord, enum, math, random, re
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

- fix tags for search
'''

# id (int), num (int), time (datetime), message_id (int), question (str), thread_question (str), choices (str[]), votes (int[]), image (str), published (bool), duration (datetime), guildid (int), description (str), tag (int)


class PollsCog(commands.Cog, name = "Polls"):
	"""Polls commands"""


	def __init__(self, bot):
		self.bot = bot

		self.bot.tree.on_error = self.on_app_command_error


		self.sort = {
			self.Sort.poll_id: "Poll ID",
			self.Sort.newest: "Newest",
			self.Sort.oldest: "Oldest",
			self.Sort.most_votes: "Most votes",
			self.Sort.least_votes: "Least votes"
		}

		self.bot.hasmanagerperms = self.hasmanagerperms


	findchoice = lambda self, choices, x: [i for i in choices if i.value == x][0]

	choices = {}

	# choices['tags'] = [
	# 	Choice(name="Comics", value="comics"),
	# 	Choice(name="MCU", value="mcu")
	# ]
	# findtag = lambda self, x: self.findchoice(self.choices['tags'], x) 

	class Sort(enum.Enum):
		poll_id = "Poll ID"
		newest = "Newest"
		oldest = "Oldest"
		most_votes = "Most votes"
		least_votes = "Least votes"
	choices['sort'] = [Choice(name=v.value, value=e) for e, v in dict(Sort.__members__).items()]


	datetosql = lambda self, x: x.strftime('%Y-%m-%d %H:%M:%S')
	strf = lambda self, x: x.strftime('%a, %b %d, %Y ~ %I:%M:%S %p %Z').replace(" 0", " ")
	# Sun, Mar 6, 2022 ~ 3:30 PM UTC
	s = lambda self, x: "" if x == 1 else "s"



	async def searchpollsbyid(self, pollid, showunpublished = False):
		if showunpublished:
			return await self.bot.db.fetch("SELECT id, question FROM polls WHERE CAST(id AS TEXT) LIKE $1", f"{pollid}%")
		else:
			return await self.bot.db.fetch("SELECT id, question FROM polls WHERE CAST(id AS TEXT) LIKE $1 AND published = true", f"{pollid}%")

	async def searchpollsbykeyword(self, keyword, showunpublished = False):
		if showunpublished:
			return await self.bot.db.fetch("SELECT id, question FROM polls WHERE question ~* $1", keyword)
		else:
			return await self.bot.db.fetch("SELECT id, question FROM polls WHERE question ~* $1 AND published = true", keyword)


	async def fetchguildinfo(self, guildid: int):
		return await self.bot.db.fetchrow("SELECT * FROM pollsinfo WHERE guild_id = $1", guildid)

	async def fetchguildinfobymanagechannel(self, channelid: int):
		return await self.bot.db.fetchrow("SELECT * FROM pollsinfo WHERE manage_channel_id = $1", channelid)

	async def fetchtag(self, tagid: int):
		return await self.bot.db.fetchrow("SELECT * FROM polltags WHERE id = $1", tagid) if tagid else None

	async def fetchtagsbyguildid(self, guildid: int):
		return await self.bot.db.fetch("SELECT * FROM polltags WHERE guild_id = $1", guildid)

	async def tagname(self, tagid: int):
		return (await self.fetchtag(tagid))['name']

	async def tagcolour(self, tagid: int):
		return (await self.fetchtag(tagid))['colour']

	async def fetchcolour(self, guildid: int, tagid: int):
		guild = await self.fetchguildinfo(guilid)
		tag = await self.fetchtag(tagid)

		if tag and tag['colour']: colour = tag['colour']
		else: colour = guild['default_colour']

		return colour



	async def fetchguildid(self, interaction: discord.Interaction):
		return await self.fetchguildinfobymanagechannel(interaction.channel_id) if await self.ismanagechannel(interaction.channel_id) else interaction.guild_id


	async def ismanagechannel(self, channelid: int):
		return bool(await self.fetchguildinfobymanagechannel(channelid))

	async def validguild(self, interaction: discord.Interaction):
		return await self.fetchguildinfo(interaction.guild_id) is not None

	async def hasmanagerperms(self, interaction: discord.Interaction):
		info = await self.bot.db.fetchrow("SELECT * FROM pollsinfo WHERE guild_id = $1", interaction.guild_id)
		return interaction.channel_id in info['manage_channel_id'] or any([r.id in info['manager_role_id'] for r in interaction.user.roles])


	@staticmethod
	def poll_manager_only():
		async def actual_check(interaction: Interaction):
			return await interaction.client.hasmanagerperms(interaction)
		return app_commands.check(actual_check)



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
			embed = discord.Embed(title = poll['question'])
		else:
			embed = discord.Embed(title = f"{poll['num']}: {poll['question']}")

		guild = await self.fetchguildinfo(poll['guild_id'])
		tag = await self.fetchtag(poll['tag'])

		embed.colour = self.fetchcolour(poll['guild_id'], poll['tag'])

		if not poll['votes']:
			embed.add_field(name = "Choices", value = "\n".join([f'- {c}' for c in poll['choices']]), inline = False)
		else:
			embed.add_field(name = "Choices", value = "\n".join([f'- ({v}) {c}' for v, c in enumerate(poll['votes'], poll['choices'])]), inline = False)

		embed.add_field(name = "Published?", value = poll['published'], inline = False)

		if poll['thread_question']: embed.add_field(name = "Thread Question", value = poll['thread_question'])
		if poll['tag']: embed.add_field(name = "Tag", value = f"`{await self.tagname(poll['tag'])}`")

		if poll['time']: embed.add_field(name = "Publish Date", value = f"<t:{int(poll['time'].timestamp())}:F>")
		if poll['duration']: embed.add_field(name = "Duration", value = poll['duration'])

		if poll['message_id']: 
			message = await self.bot.fetch_message(poll['message_id'])
			if message:
				embed.add_field(name = "Poll Message", value = f"[{question}]({message.jump_url})")
			else:
				embed.add_field(name = "Poll Message", value = f"Can't locate message {message_id}")

		if poll['image']: embed.set_image(url = poll['image'])

		embed.set_footer(text = f"ID: {poll['id']} | {guild['guild_id']}")

		return embed



	pollsgroup = app_commands.Group(name="polls", description="Poll commands", guild_ids=[288896937074360321])



	async def autocomplete_tag(self, interaction: discord.Interaction, current: str):
		tags = await self.fetchtagsbyguildid(interaction.guild_id)
		choices = [app_commands.Choice(name = t['name'], value = str(t['id'])) for t in tags if re.search(f"^{current.lower()}", t['name'], re.IGNORECASE)]
		return choices

	async def autocomplete_searchbypollid(self, interaction: discord.Interaction, current: int):
		if current.isdigit():
			current = int(current)
			if current <= 99999:
				results = await self.searchpollsbyid(current, await self.hasmanagerperms(interaction))
				results = self.sortpolls(results)
			else:
				results = []
		else:
			results = await self.searchpollsbykeyword(current, await self.hasmanagerperms(interaction))
			lowered = current.lower()
			regex = [f"^\b{lowered}\b", f"\b{lowered}\b", f"^{lowered}", lowered]
			results = self.sortpolls(results)
			results.sort(key = lambda x: [bool(re.search(i, x['question'].lower())) for i in regex].index(True))

		choices = [app_commands.Choice(name = f"[{i['id']}] {i['question']}", value = i['id']) for i in results[:25]]
		return choices



	async def on_app_command_error(self, interaction: Interaction, error: AppCommandError):
		if isinstance(error, app_commands.errors.CheckFailure):
			if await self.validguild(interaction):
				return await interaction.response.send_message(f"You need to be a <@&{(await self.fetchguildinfo(interaction.guild_id))['manager_role_id'][]}> to do that!", ephemeral = True)




	@pollsgroup.command(name="create")
	@poll_manager_only()
	@app_commands.describe(
		question = "Main Poll Question to ask.",
		opt_1 = "Option 1.", opt_2 = "Option 2.", opt_3 = "Option 3.", opt_4 = "Option 4.", opt_5 = "Option 5.", opt_6 = "Option 6.", opt_7 = "Option 7.", opt_8 = "Option 8.",
		thread_question = "Question to ask in the accompanying Thread.",
		image = "Image to accompany Poll Question.",
		tag = "Tag categorising this Poll Question."
	)
	# @app_commands.choices(tag=choices['tags'])
	async def pollcreate(self, interaction: discord.Interaction, 
			question: str, 
			opt_1: str, opt_2: str, 
			description: str = None,
			thread_question: str = None,
			image: str = None,
			tag: str = None,
			opt_3: str = None, opt_4: str = None, opt_5: str = None, opt_6: str = None, opt_7: str = None, opt_8: str = None
		):
		"""Creates a poll question."""
		
		choices = [i for i in [opt_1, opt_2, opt_3, opt_4, opt_5, opt_6, opt_7, opt_8] if i]

		while True:
			pollid = random.randint(10000, 99999)
			if not await self.bot.db.fetchrow("SELECT id FROM polls WHERE id = $1", pollid):
				break

		if tag and (not tag.isdigit() or not await self.fetchtag(int(tag))):
			return await interaction.response.send_message("Please select an available tag.")
		else:
			tag = int(tag)


		# id (int), num (int), time (datetime), message_id (int), question (str), thread_question (str), choices (str[]), votes (int[]), image (str), published (bool), duration (datetime), guildid (int), description (str), tag (int)
		await self.bot.db.execute(
			f"INSERT INTO polls VALUES ($1, null, null, null, $2, $3, $4, null, $5, false, null, $6, $7, $8)", 
			pollid, question, thread_question, choices, image, interaction.guild_id, description, tag, 
		)

		embed = discord.Embed(title = question, description = description, colour = await self.tagcolour(tag), timestamp=discord.utils.utcnow())
		embed.add_field(name = "Choices", value = "\n".join([f'- {i}' for i in choices]), inline = False)
		embed.add_field(name = "Thread Question", value = thread_question if thread_question else "`None`")
		if tag: embed.add_field(name = "Tag", value = f"`{await self.tagname(tag)}`")
		if image: embed.set_image(url = image)
		embed.set_footer(text = pollid)

		await interaction.response.send_message(f'Created new poll question: "{question}"', embed = embed)

	@pollcreate.autocomplete("tag")
	async def pollcreate_autocomplete_tag(self, interaction: discord.Interaction, current: str):
		return await self.autocomplete_tag(interaction, current)



	@pollsgroup.command(name="delete")
	@poll_manager_only()
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

	@polldelete.autocomplete("poll_id")
	async def polldelete_autocomplete_poll_id(self, interaction: discord.Interaction, current: int):
		return await self.autocomplete_searchbypollid(interaction, current)


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


	

	@pollsgroup.command(name="search")
	@app_commands.describe(
		poll_id = "The ID (5-digit or #) of the poll to search for.",
		keyword = "Keyword to search for. Searches the question and thread question. Case-insensitive.",
		sort = "Order to list results.",
		tag = "Tag to filter results by.",
		published = "List published or unpublished questions only. Unpublished polls are only visible to Poll Managers."
	)
	@app_commands.choices(sort=choices['sort'])
	async def pollsearch(self, interaction: discord.Interaction,
			poll_id: int = None,
			keyword: str = None,
			sort: Choice[str] = Sort.poll_id.name,
			tag: str = None,
			published: bool = None
		):
		"""Searches poll questions. Search by poll ID, or by keyword, and filter by tag."""

		sort = self.Sort.__members__[sort.value if not isinstance(sort, str) else sort]


		if poll_id:
			poll = await self.bot.db.fetchrow("SELECT * FROM polls WHERE id = $1", poll_id)

			if not poll: poll = await self.bot.db.fetchrow("SELECT * FROM polls WHERE num = $1", poll_id)

			if not poll or (not poll['published'] and not self.hasmanagerperms(interaction)):
				return await interaction.response.send_message(f"Couldn't find a poll with the ID `{poll_id}`.")

			embed = await self.pollinfoembed(poll)

			await interaction.response.send_message(embed=embed)
			# add shortcut buttons to delete (and edit maybe?)

			return

		else:
			if tag:
				if (not tag.isdigit() or not await self.fetchtag(int(tag))):
					return await interaction.response.send_message("Please select an available tag.")
				else:
					tag = int(tag)

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
				values.append(tag)
				text.append(f"Tag: `{await self.tagname(tag)}`")
			if published is not None:
				queries.append("published = ${}")
				values.append(published)
				text.append(f"Published? `{published}`")
			if sort:
				text.append(f"Sorted by `{sort.name}`")


			guildid = await self.fetchguildid(interaction)


			try:
				if not queries: polls = await self.bot.db.fetch("SELECT * FROM polls WHERE guild_id = $1", guildid)
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
			PollSearchPaginator.colour = self.fetchcolour(guildid, None)

			paginator = await PollSearchPaginator.start(await interaction.original_response(), entries=polls, per_page=15)
			await paginator.wait()

			for child in paginator.children:
				child.disabled = True
			paginator.stop()

			return await paginator.msg.edit(content="Timed out.", view=paginator)

	@pollsearch.autocomplete("poll_id")
	async def pollsearch_autocomplete_poll_id(self, interaction: discord.Interaction, current: int):
		return await self.autocomplete_searchbypollid(interaction, current)

	@pollsearch.autocomplete("tag")
	async def pollsearch_autocomplete_tag(self, interaction: discord.Interaction, current: str):
		return await self.autocomplete_tag(interaction, current)




	@pollsgroup.command(name="schedule")
	@poll_manager_only()
	@app_commands.describe(
		poll_id = "The 5-digit ID of the poll to schedule.",
		schedule_time = "Scheduled time for the poll to start. Given in Epoch timestamp (UTC). Leave empty if published, or want to leave the scheduled date unchanged. Set to -1 to clear.",
		duration = "Duration for poll to run. Can pass Epoch timestamp (UTC) as the ending time instead. Can give number of seconds as raw value. Set to -1 to clear.",
	)
	async def pollschedule(self, interaction: discord.Interaction, 
			poll_id: int,
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

		embed = discord.Embed(title = "Scheduled Poll", description = f"{poll['question']}", colour = self.fetchcolour(poll['guild_id'], poll['tag']), timestamp = discord.utils.utcnow())
		embed.set_footer(text = f"ID: {poll['id']}" + f'''{f" (#{poll['num']})" if poll['num'] else ""}''')
		embed.add_field(name = "Start time", value = f"<t:{int(poll['time'].timestamp())}:F>\n`{int(poll['time'].timestamp())}`" if poll['time'] else "No time scheduled.")
		embed.add_field(name = "End time", value = f"<t:{int((poll['time']+poll['duration']).timestamp())}:F> - lasts {poll['duration']}\n`{int(poll['duration'].total_seconds())}`" if poll['time'] and poll['duration'] else f"Lasts {poll['duration']}\n`{int(poll['duration'].total_seconds())}`" if poll['duration'] else "No end time scheduled.")

		return await interaction.response.send_message(embed=embed)

	@pollschedule.autocomplete("poll_id")
	async def pollschedule_autocomplete_poll_id(self, interaction: discord.Interaction, current: int):
		return await self.autocomplete_searchbypollid(interaction, current)

	@pollschedule.autocomplete("duration")
	async def pollschedule_autocomplete_duration(self, interaction: discord.Interaction, current: float):
		try:
			current = float(current)
		except ValueError:
			return []

		if current == -1 or math.isnan(current):
			return [app_commands.Choice(name = f"Clear duration value.", value = -1)]
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
		if current == '' or int(current) == -1:
			return [app_commands.Choice(name = f"Clear scheduled time.", value = -1)]
		elif current >= int(discord.utils.utcnow().timestamp()):
			current = int(current)
			try:
				time = datetime.datetime.fromtimestamp(current, datetime.timezone.utc)
				return [app_commands.Choice(name = f"{self.strf(time)}", value = int(current))]
			except (OSError, OverflowError):
				return []
		return []




async def setup(bot):
	await bot.add_cog(PollsCog(bot))