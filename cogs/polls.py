import asyncio, asyncpg, copy, datetime, discord, enum, math, random, re, sys, traceback
from discord import *
from discord.ext import commands
from discord.app_commands import *
from discord.app_commands.tree import _log
from funcs.buttonpaginator import *

'''
x Create polls
x Delete polls
x View polls
x Search polls
x Edit polls
x Schedule polls
x Start polls
- End polls

x SQL DB
x Slashies
- Schedule timer
- Startup timer
  - Check on threads

- Vote on poll
  - update message function
  - update votes values in SQL function
- Add reaction adds to thread


x add description to poll qs
x add server to poll qs
x tags stored in SQL
x poll info per server
  x server id
  x manager role
  x tags
  x external command channel access
  x colour
x Search polls only by server
- Search all polls
x Server/channel/message IDs for crossposts
x Poll access perms by server

x fix tags for search

x table for votes
x question values
  x show question
  x show options
  x show votes

- show user history
- tags
  - create
  - edit
  - delete

x end message repeat

- format duration in info embed
- new embed for pretty



- make a poll object

'''

# id (int), num (int), time (datetime), message_id (int), question (str), thread_question (str), choices (str[]), votes (int[]), image (str), published (bool), duration (datetime), guildid (int), description (str), tag (int), show_question (bool), show_options (bool), show_voting (bool), active (bool), crosspost_message_ids (int[])


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



	async def searchpollsbyid(self, poll_id, showunpublished = False):
		if showunpublished:
			return await self.bot.db.fetch("SELECT id, question, published, active FROM polls WHERE CAST(id AS TEXT) LIKE $1", f"{poll_id}%")
		else:
			return await self.bot.db.fetch("SELECT id, question FROM polls, active WHERE CAST(id AS TEXT) LIKE $1 AND published = true", f"{poll_id}%")

	async def searchpollsbykeyword(self, keyword, showunpublished = False):
		if showunpublished:
			return await self.bot.db.fetch("SELECT id, question, published, active FROM polls WHERE question ~* $1", keyword)
		else:
			return await self.bot.db.fetch("SELECT id, question, published, active FROM polls WHERE question ~* $1 AND published = true", keyword)


	async def fetchpoll(self, poll_id: int):
		return await self.bot.db.fetchrow("SELECT * FROM polls WHERE id = $1", poll_id)

	async def fetchguildinfo(self, guildid: int):
		return await self.bot.db.fetchrow("SELECT * FROM pollsinfo WHERE guild_id = $1", guildid)

	async def fetchguildinfobymanagechannel(self, channelid: int):
		return await self.bot.db.fetchrow("SELECT * FROM pollsinfo WHERE manage_channel_id && $1", [channelid])

	async def fetchtag(self, tagid: int):
		return await self.bot.db.fetchrow("SELECT * FROM pollstags WHERE id = $1", tagid) if tagid else None

	async def fetchtagsbyguildid(self, guildid: int):
		return await self.bot.db.fetch("SELECT * FROM pollstags WHERE guild_id = $1", guildid)

	async def tagname(self, tagid: int):
		return (await self.fetchtag(tagid))['name']

	async def tagcolour(self, tagid: int):
		return (await self.fetchtag(tagid))['colour']

	async def fetchcolourbyid(self, guildid: int, tagid: int):
		guild = await self.fetchguildinfo(guildid)
		tag = await self.fetchtag(tagid)

		return self.fetchcolour(guild, tag)

	def fetchcolour(self, guild, tag):
		if tag and tag['colour']: colour = tag['colour']
		else: colour = guild['default_colour']

		return colour



	async def fetchguildid(self, interaction: discord.Interaction):
		return (await self.fetchguildinfobymanagechannel(interaction.channel_id))['guild_id'] if await self.ismanagechannel(interaction.channel_id) else interaction.guild_id


	async def ismanagechannel(self, channelid: int):
		return bool(await self.fetchguildinfobymanagechannel(channelid))

	async def validguild(self, interaction: discord.Interaction):
		return await self.fetchguildinfo(interaction.guild_id) is not None

	async def hasmanagerperms(self, interaction: discord.Interaction):
		return await self.hasmanagerpermsbyuserandids(interaction.user, interaction.guild_id, interaction.channel_id)

	async def hasmanagerpermsbyuserandids(self, user, guild_id, channel_id):
		info = await self.bot.db.fetchrow("SELECT * FROM pollsinfo WHERE guild_id = $1", guild_id)
		return channel_id in info['manage_channel_id'] or any([r.id in info['manager_role_id'] for r in user.roles])


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
			self.value = True
			self.interaction = interaction
			await self.interaction.response.defer()
			self.stop()

		@discord.ui.button(label='Cancel', style=discord.ButtonStyle.grey)
		async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
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


	async def pollinfoembed(self, poll, *, guild = None, tag = None):
		if not poll['num']:
			embed = discord.Embed(title = poll['question'])
		else:
			embed = discord.Embed(title = f"#{poll['num']}: {poll['question']}")

		embed.description = poll['description']

		if not guild: guild = await self.fetchguildinfo(poll['guild_id'])
		if not tag: tag = await self.fetchtag(poll['tag'])

		embed.colour = self.fetchcolour(guild, tag)

		if not poll['votes']:
			embed.add_field(name = "Choices", value = "\n".join([f'- {c}' for c in poll['choices']]), inline = False)
		else:
			embed.add_field(name = "Choices", value = "\n".join([f'- ({v}) {c}' for v, c in zip(poll['votes'], poll['choices'])]), inline = False)

		embed.add_field(name = "Published?", value = poll['published'])
		embed.add_field(name = "Active?", value = poll['active'])

		if poll['thread_question']: embed.add_field(name = "Thread Question", value = poll['thread_question'])
		if poll['tag']: embed.add_field(name = "Tag", value = f"`{tag['name']}`")

		if poll['time']: embed.add_field(name = "Publish Date", value = f"<t:{int(poll['time'].timestamp())}:F>")
		if poll['duration']: embed.add_field(name = "Duration", value = poll['duration'])

		if poll['message_id']:
			message = await self.bot.fetch_message(poll['message_id'])
			if message:
				embed.add_field(name = "Poll Message", value = f"[{question}]({message.jump_url})")
			else:
				embed.add_field(name = "Poll Message", value = f"Can't locate message {message_id}")

		display = [[poll['show_question'], "Question"], [poll['show_options'], "Options"], [poll['show_voting'], "Current Votes"]]
		displaysort = {"Showing": [], "Not showing": []}
		[displaysort["Showing"].append(i[1]) if i[0] else displaysort["Not showing"].append(i[1]) for i in display]
		embed.add_field(name = "Display", value = "\n".join([f"{k}: {', '.join(v)}" for k, v in displaysort.items() if v]))

		if poll['image']: embed.set_image(url = poll['image'])

		embed.set_footer(text = f"ID: {poll['id']} | {guild['guild_id']}")

		return embed

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


	pollsgroup = app_commands.Group(name="polls", description="Poll commands", guild_ids=[288896937074360321])



	async def autocomplete_tag(self, interaction: discord.Interaction, current: str, *, clear = None, clearname = "Clear tag."):
		if clear is not None:
			emptychoice = app_commands.Choice(name = clearname, value = clear)
			if current == clear:
				return [emptychoice]
		tags = await self.fetchtagsbyguildid(interaction.guild_id)
		choices = [app_commands.Choice(name = t['name'], value = str(t['id'])) for t in tags if re.search(f"^{current.lower()}", t['name'], re.IGNORECASE)]
		if current == "" and clear is not None: choices.append(emptychoice)
		return choices

	async def autocomplete_searchbypollid(self, interaction: discord.Interaction, current: int, *, published = None, active = None):
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

		if published is not None:
			results = [i for i in results if i['published'] == published]
		if active is not None:
			results = [i for i in results if i['active'] == active]

		choices = [app_commands.Choice(name = f"[{i['id']}] {i['question']}", value = i['id']) for i in results[:25]]
		return choices



	async def on_app_command_error(self, interaction: Interaction, error: AppCommandError):
		if isinstance(error, app_commands.errors.CheckFailure):
			if await self.validguild(interaction):
				return await interaction.response.send_message(f"You need to be a <@&{(await self.fetchguildinfo(interaction.guild_id))['manager_role_id'][0]}> to do that!", ephemeral = True)

		await interaction.followup.send("Something broke!")
		_log.error('Ignoring exception in command %r', interaction.command.name, exc_info=error)





	@pollsgroup.command(name="create")
	@poll_manager_only()
	@app_commands.describe(
		question = "Main Poll Question to ask.",
		opt_1 = "Option 1.", opt_2 = "Option 2.", opt_3 = "Option 3.", opt_4 = "Option 4.", opt_5 = "Option 5.", opt_6 = "Option 6.", opt_7 = "Option 7.", opt_8 = "Option 8.",
		thread_question = "Question to ask in the accompanying Thread.",
		image = "Image to accompany Poll Question.",
		tag = "Tag categorising this Poll Question.",
		show_question = "Show question in poll message", show_options = "Show options in poll message", show_voting = "Show the current state of votes in poll message"
		)
	async def pollcreate(self, interaction: discord.Interaction, 
			question: str, 
			opt_1: str, opt_2: str, 
			description: str = None,
			thread_question: str = None,
			image: str = None,
			tag: str = None,
			opt_3: str = None, opt_4: str = None, opt_5: str = None, opt_6: str = None, opt_7: str = None, opt_8: str = None,
			show_question: bool = True, show_options: bool = True, show_voting: bool = True
		):
		"""Creates a poll question."""
		
		await interaction.response.defer()

		choices = [i for i in [opt_1, opt_2, opt_3, opt_4, opt_5, opt_6, opt_7, opt_8] if i]

		while True:
			poll_id = random.randint(10000, 99999)
			if not await self.bot.db.fetchrow("SELECT id FROM polls WHERE id = $1", poll_id):
				break

		if tag:
			if tag.isdigit():
				tagobj = await self.fetchtag(int(tag))
				if tagobj and tagobj['guild_id'] == await self.fetchguildid(interaction):
					tag = int(tag)
				else:
					return await interaction.followup.send("Please select an available tag.")
			else:
				return await interaction.followup.send("Please select an available tag.")


		# id (int), num (int), time (datetime), message_id (int), question (str), thread_question (str), choices (str[]), votes (int[]), image (str), published (bool), duration (datetime), guildid (int), description (str), tag (int), show_question (bool), show_options (bool), show_voting (bool), active (bool), crosspost_message_ids (int[])
		await self.bot.db.execute(
			"INSERT INTO polls VALUES ($1, null, null, null, $2, $3, $4, null, $5, false, null, $6, $7, $8, $9, $10, $11, False, $12)", 
			poll_id, question, thread_question, choices, image, interaction.guild_id, description, tag, show_question, show_options, show_voting, []
		)

		# embed = discord.Embed(title = question, description = description, colour = await self.tagcolour(tag), timestamp=discord.utils.utcnow())
		# embed.add_field(name = "Choices", value = "\n".join([f'- {i}' for i in choices]), inline = False)
		# embed.add_field(name = "Thread Question", value = thread_question if thread_question else "`None`")
		# if tag: embed.add_field(name = "Tag", value = f"`{await self.tagname(tag)}`")
		# if image: embed.set_image(url = image)
		# embed.set_footer(text = poll_id)

		poll = await self.fetchpoll(poll_id)
		embed = await self.pollinfoembed(poll)

		await interaction.followup.send(f'Created new poll question: "{question}"', embed = embed)

	@pollcreate.autocomplete("tag")
	async def pollcreate_autocomplete_tag(self, interaction: discord.Interaction, current: str):
		return await self.autocomplete_tag(interaction, current)





	@pollsgroup.command(name="delete")
	@poll_manager_only()
	@app_commands.describe(poll_id = "5-digit ID of the poll to delete.")
	async def polldelete(self, interaction: discord.Interaction, poll_id: int):
		"""Deletes a poll question."""

		await interaction.response.defer()

		poll = await self.fetchpoll(poll_id)

		if not poll or not await self.hasmanagerpermsbyuserandids(interaction.user, poll['guild_id'], interaction.channel_id):
			return await interaction.followup.send(f"Couldn't find a poll with the ID `{poll_id}`.")

		if poll['published']:
			return await interaction.followup.send(f"This poll has already been published, and cannot be deleted.")

		view = self.Confirm()
		embed = await self.pollinfoembed(poll)


		msg = await interaction.followup.send(f"Do you want to delete this poll question?", embed = embed, view = view)


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






	@pollsgroup.command(name="edit")
	@poll_manager_only()
	@app_commands.describe(
		poll_id = "5-digit ID of the poll to edit.",
		question = "Main Poll Question to ask.",
		opt_1 = "Option 1.", opt_2 = "Option 2.", opt_3 = "Option 3.", opt_4 = "Option 4.", opt_5 = "Option 5.", opt_6 = "Option 6.", opt_7 = "Option 7.", opt_8 = "Option 8.",
		thread_question = "Question to ask in the accompanying Thread.",
		image = "Image to accompany Poll Question.",
		tag = "Tag categorising this Poll Question."
		)
	async def polledit(self, interaction: discord.Interaction,
			poll_id: int,
			question: str = None,
			description: str = None,
			thread_question: str = None,
			image: str = None,
			tag: str = None,
			opt_1: str = None, opt_2: str = None, opt_3: str = None, opt_4: str = None, opt_5: str = None, opt_6: str = None, opt_7: str = None, opt_8: str = None,
			show_question: bool = None, show_options: bool = None, show_voting: bool = None
		):
		"""Edits a poll question. Type '-clear' to clear the current value. You must have a question and at least two options. Leave values empty to keep them the same."""

		await interaction.response.defer()

		clearvalue = "-clear"


		poll = await self.fetchpoll(poll_id)

		if not poll or not await self.hasmanagerpermsbyuserandids(interaction.user, poll['guild_id'], interaction.channel_id):
			return await interaction.followup.send(f"Couldn't find a poll with the ID `{poll_id}`.")
		oldpoll = poll


		choices = []
		choicesmod = [opt_1, opt_2, opt_3, opt_4, opt_5, opt_6, opt_7, opt_8]


		for i in range(len(choicesmod)):
			if i < len(poll['choices']):
				old = poll['choices'][i]
			else:
				old = None
			mod = choicesmod[i]
			if mod == None: choices.append(old)
			elif mod == clearvalue: choices.append(None)
			else: choices.append(mod)
		choices = [i for i in choices if i is not None]


		if poll['published'] and len(choices) != len(poll['choices']):
			return await interaction.followup.send("You can't add/remove choices once the poll's been published!")

		if len(choices) < 2:
			return await interaction.followup.send("You need at least 2 choices!")


		if poll['published'] and tag:
			return await interaction.followup.send("You can't edit tags once the poll's been published!")

		if tag and tag != clearvalue and tag.isdigit():
			tagobj = await self.fetchtag(int(tag))
			if tagobj and tagobj['guild_id'] == poll['guild_id']:
				tag = int(tag)
		else:
			return await interaction.followup.send("Please select an available tag.")



		async def update(name, *values):
			if not isinstance(name, list):
				name = [name]
			if len(name) != len(values):
				raise Exception

			txt = [f"{k} = ${i}" for k, i in zip(name, list(range(1, len(values) + 1)))]

			await self.bot.db.execute(f"UPDATE polls SET {', '.join(txt)} WHERE id = ${len(values) + 1}", *values, poll_id)

		clear = lambda x: None if x == clearvalue else x


		names = []
		values = []
		def append(name, value):
			names.append(name)
			values.append(value)

		if question:
			append("question", question)
		if choices:
			append("choices", choices)
		if description:
			append("description", clear(description))
		if thread_question:
			append("thread_question", clear(thread_question))
		if image:
			append("image", clear(image))
		if tag:
			append("tag", clear(tag))
		if show_question:
			append("show_question", show_question)
		if show_options:
			append("show_options", show_options)
		if show_voting:
			append("show_voting", show_voting)

		await update(names, *values)



		newpoll = await self.fetchpoll(poll_id)

		guild = await self.fetchguildinfo(newpoll['guild_id'])
		tag = await self.fetchtag(newpoll['tag'])

		oldembed = await self.pollinfoembed(oldpoll, guild=guild, tag=tag)
		newembed = await self.pollinfoembed(newpoll, guild=guild, tag=tag)

		oldembed.title = f"[OLD] {oldembed.title}"
		newembed.title = f"[NEW] {newembed.title}"



		await interaction.followup.send(f"Edited poll `{poll_id}`", embeds = [oldembed, newembed])



	@polledit.autocomplete("poll_id")
	async def polledit_autocomplete_poll_id(self, interaction: discord.Interaction, current: int):
		return await self.autocomplete_searchbypollid(interaction, current)

	@polledit.autocomplete("tag")
	async def polledit_autocomplete_tag(self, interaction: discord.Interaction, current: str):
		return await self.autocomplete_tag(interaction, current, clear = "-clear")




	@pollsgroup.command(name="schedule")
	@poll_manager_only()
	@app_commands.describe(
		poll_id = "5-digit ID of the poll to schedule.",
		schedule_time = "Scheduled time for the poll to start. Given in Epoch timestamp (UTC). Leave empty if published, or want to leave the scheduled date unchanged. Set to -1 to clear.",
		duration = "Duration for poll to run. Can pass Epoch timestamp (UTC) as the ending time instead. Can give number of seconds as raw value. Set to -1 to clear.",
		)
	async def pollschedule(self, interaction: discord.Interaction, 
			poll_id: int,
			schedule_time: int = None, 
			duration: float = None
		):
		"""Schedules polls for publishing"""

		await interaction.response.defer()

		clearschedule = schedule_time == -1
		if clearschedule: schedule_time = None

		end_time = duration if duration and duration >= discord.utils.utcnow().timestamp() else None
		if end_time: duration = None

		poll = await self.fetchpoll(poll_id)

		if not poll or not await self.hasmanagerpermsbyuserandids(interaction.user, poll['guild_id'], interaction.channel_id):
			return await interaction.followup.send(f"Couldn't find a poll with the ID `{poll_id}`.")

		if poll['published']:
			if schedule_time:
				return await interaction.followup.send(f"This poll has already been published, therefore the start time cannot be rescheduled.")
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
				if (end_time - schedule_time) < 0:
					return await interaction.followup.send(f"You're trying to end the poll before it starts! (Starting <t:{int(schedule_time)}:F> but ending <t:{int(end.timestamp())}:F>")
				elif (end_time - current.timestamp()) < 0:
					return await interaction.followup.send(f"You're trying to end the poll in the past! <t:{int(end_time)}:F>, <t:{int(end_time)}:R>")


			if (scheduled - current).total_seconds() < 0:
				return await interaction.followup.send(f"You're trying to schedule a message in the past! <t:{int(schedule_time)}:F>, <t:{int(schedule_time)}:R>")

		else:
			if end_time:
				return await interaction.followup.send("You can't set an end time without a start time!")

		if clearschedule:
			schedule_time = None
			scheduled = None
		if schedule_time != poll['time'] or clearschedule:
			await self.bot.db.execute("UPDATE polls SET time = $1 WHERE id = $2", scheduled, poll_id)
		if duration:
			durationtimedelta = datetime.timedelta(seconds=duration)
			if duration == -1: durationtimedelta = None
			await self.bot.db.execute("UPDATE polls SET duration = $1 WHERE id = $2", durationtimedelta, poll_id)


		poll = await self.fetchpoll(poll_id)

		embed = discord.Embed(title = "Scheduled Poll", description = f"{poll['question']}", colour = await self.fetchcolourbyid(poll['guild_id'], poll['tag']), timestamp = discord.utils.utcnow())
		embed.set_footer(text = f"ID: {poll['id']}" + f'''{f" (#{poll['num']})" if poll['num'] else ""}''')
		embed.add_field(name = "Start time", value = f"<t:{int(poll['time'].timestamp())}:F>\n`{int(poll['time'].timestamp())}`" if poll['time'] else "No time scheduled.")
		embed.add_field(name = "End time", value = f"<t:{int((poll['time']+poll['duration']).timestamp())}:F> - lasts {poll['duration']}\n`{int(poll['duration'].total_seconds())}`" if poll['time'] and poll['duration'] else f"Lasts {poll['duration']}\n`{int(poll['duration'].total_seconds())}`" if poll['duration'] else "No end time scheduled.")

		return await interaction.followup.send(embed=embed)

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
					continue

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



	async def startpoll(self, poll_id, *, set_time = False):
		return await self.startpolls([poll_id], set_time = set_time)

	async def startpolls(self, poll_ids: list, *, set_time = None):
		if not isinstance(poll_ids, list):
			poll_ids = [poll_ids]


		polls = []
		for poll_id in poll_ids:
			poll = await self.fetchpoll(poll_id)
			tag = await self.fetchtag(poll['tag'])
			polls.append([poll, tag])

		tags = [tag['id'] if tag else None for poll, tag in polls]
		if not tags.count(tags[0]) == len(tags):
			print("Can't bulk-start polls with different tags!")
			return None


		poll, tag = polls[0]
		guild = await self.fetchguildinfo(poll['guild_id'])
		channel_id = guild['default_channel_id']
		if tag:
			if tag['channel_id']:
				channel_id = tag['channel_id']

		for poll, t in polls:
			num = None
			if tag:
				if tag['num']:
					num = (await self.fetchtag(poll['tag']))['num']
					await self.bot.db.execute("UPDATE pollstags SET num = $2 WHERE id = $1", tag['id'], num + 1)

			votes = [0 for i in range(len(poll['choices']))]

			await self.bot.db.execute("UPDATE polls SET published = $2, active = $3, votes = $4, num = $5 WHERE id = $1", poll['id'], True, True, votes, num)

			if set_time:
				await self.bot.db.execute("UPDATE polls SET time = $2 WHERE id = $1", poll['id'], set_time)


		msgs = [[await self.formatpollmessage(p['id']), p] for p in [i[0] for i in polls]]
		final = []

		channel = self.bot.get_channel(channel_id)
		crossposts = [self.bot.get_channel(i) for i in tag['crosspost_channels']] if tag else []

		async def send(txt, poll, channel, *, main = True):
			msg = await channel.send(**txt)

			if main:
				await self.bot.db.execute("UPDATE polls SET message_id = $2 WHERE id = $1", poll['id'], msg.id)
			else:
				await self.bot.db.execute("UPDATE polls SET crosspost_message_ids = crosspost_message_ids || $2 WHERE id = $1", poll['id'], [msg.id])

			if poll['thread_question']:
				name = poll['question']
				if poll['num']: name = f"{poll['num']} - {name}"
				try:
					thread = await msg.create_thread(name = name)
					threadq = await thread.send(poll['thread_question'])
					await threadq.pin()
				except commands.Forbidden:
					pass

			return msg

		for txt, poll in msgs:
			final.append([poll, await send(txt, poll, channel)])
			for ch in crossposts:
				final.append([poll, await send(txt, poll, ch, main = False)])
				

		if tag['end_message']:
			embed = discord.Embed(description = tag['end_message'], colour = await self.fetchcolourbyid(guild['guild_id'], tag['id']))
			endmsgs = [await channel.send(embed = embed)]
			for ch in crossposts:
				endmsgs.append(await ch.send(embed = embed))

			if tag['end_message_replace']:
				if tag['end_message_latest_ids']:
					for message_id in tag['end_message_latest_ids']:
						for ch in [channel] + crossposts:
							try:
								msg = await ch.fetch_message(message_id)
							except NotFound:
								continue
							else:
								await msg.delete()
								break
				await self.bot.db.execute("UPDATE pollstags SET end_message_latest_ids = $2 WHERE id = $1", tag['id'], [m.id for m in endmsgs])


		return final

	async def formatpollmessage(self, poll_id):
		poll = await self.fetchpoll(poll_id)

		content = poll['question']
		embed = await self.pollinfoembed(poll)

		return {
			"content": content,
			"embed": embed
		}


	@pollsgroup.command(name="start")
	@poll_manager_only()
	@app_commands.describe(
		poll_id = "5-digit ID of the poll to start.",
		duration = "Duration for poll to run. Can pass Epoch timestamp (UTC) as the ending time instead. Can give number of seconds as raw value.",
		)
	async def pollstart(self, interaction: discord.Interaction, 
		poll_id: int,
		duration: int = None
		):
		"""Starts the voting for a poll question."""

		await interaction.response.defer()


		poll = await self.fetchpoll(poll_id)


		if not poll or not await self.hasmanagerpermsbyuserandids(interaction.user, poll['guild_id'], interaction.channel_id):
			return await interaction.followup.send(f"Couldn't find a poll with the ID `{poll_id}`.")

		if poll['published']:
			return await interaction.followup.send(f"This poll has already been published!")



		end_time = duration if duration and duration >= discord.utils.utcnow().timestamp() else None
		if end_time:
			end = datetime.datetime.fromtimestamp(end_time, datetime.timezone.utc)
			duration = end_time - scheduled.timestamp()

			if (end_time - current.timestamp()) < 0:
				return await interaction.followup.send(f"You're trying to end the poll in the past! <t:{int(end_time)}:F>, <t:{int(end_time)}:R>")
		else:
			end = None
			


		currenttime = discord.utils.utcnow()

		if duration:
			durationtimedelta = datetime.timedelta(seconds=duration)
			await self.bot.db.execute("UPDATE polls SET time = $2, duration = $3 WHERE id = $1", poll_id, discord.utils.utcnow(), durationtimedelta)

		result = await self.startpoll(poll['id'], set_time = currenttime)

		if result:
			msglinks = '\n'.join([f"{msg.channel.mention} [{poll['question']}](<{msg.jump_url}>)" for poll, msg in result])
			return await interaction.followup.send(f"Successfully started the poll!\n{msglinks}")
		else:
			raise Exception

	@pollstart.autocomplete("poll_id")
	async def pollstart_autocomplete_poll_id(self, interaction: discord.Interaction, current: int):
		return await self.autocomplete_searchbypollid(interaction, current, published = False)

	@pollstart.autocomplete("duration")
	async def pollstart_autocomplete_duration(self, interaction: discord.Interaction, current: float):
		try:
			current = float(current)
		except ValueError:
			return []

		if current < discord.utils.utcnow().timestamp():
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
					continue

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



	async def endpoll(self, poll_id, *, set_time = False, lock_thread = True):
		# set active to false
		# end voting
		# lock thread?

		if set_time:
			current_time = discord.utils.utcnow()

		poll = await self.fetchpoll(poll_id)
		tag = await self.fetchtag(poll['tag'])
		guild = await self.fetchguildinfo(poll['guild_id'])


		channel_id = guild['default_channel_id']
		if tag:
			if tag['channel_id']:
				channel_id = tag['channel_id']

		await self.bot.db.execute("UPDATE polls SET active = $2 WHERE id = $1", poll['id'], False)

		if set_time:
			duration = current_time - poll['time']
			await self.bot.db.execute("UPDATE polls SET duration = $2 WHERE id = $1", poll['id'], duration)

		channel = self.bot.get_channel(channel_id)
		crossposts = [self.bot.get_channel(i) for i in tag['crosspost_channels']] if tag else []

		guilds = [self.bot.get_guild(g) for g in {i.guild.id for i in [channel] + crossposts}]

		if poll['thread_question']:
			for thread_id in [poll['message_id']] + poll['crosspost_message_ids']:
				for g in guilds:
					thread = g.get_channel_or_thread(thread_id)
					if thread is None:
						continue
					else:
						await thread.edit(archived = True, locked = True)
						break


	@pollsgroup.command(name="end")
	@poll_manager_only()
	@app_commands.describe(poll_id = "5-digit ID of the poll to end.")
	async def pollend(self, interaction: discord.Interaction, 
		poll_id: int
		):
		"""Ends the voting for a poll question."""

		await interaction.response.defer()


		poll = await self.fetchpoll(poll_id)


		if not poll or not await self.hasmanagerpermsbyuserandids(interaction.user, poll['guild_id'], interaction.channel_id):
			return await interaction.followup.send(f"Couldn't find a poll with the ID `{poll_id}`.")

		if not poll['active']:
			return await interaction.followup.send(f"This poll is not active!")


		await self.endpoll(poll['id'], set_time = True)

		await interaction.followup.send(f"Successfully ended the poll!")

	@pollend.autocomplete("poll_id")
	async def pollend_autocomplete_poll_id(self, interaction: discord.Interaction, current: int):
		return await self.autocomplete_searchbypollid(interaction, current, active = True)




	@pollsgroup.command(name="search")
	@app_commands.describe(
		poll_id = "ID (5-digit or #) of the poll to search for.",
		keyword = "Keyword to search for. Searches the question and thread question. Case-insensitive.",
		sort = "Order to list results.",
		tag = "Tag to filter results by.",
		published = "List published or unpublished questions only. Unpublished polls are only visible to Poll Managers.",
		active = "List active or inactive questions only."
		)
	@app_commands.choices(sort=choices['sort'])
	async def pollsearch(self, interaction: discord.Interaction,
			poll_id: int = None,
			keyword: str = None,
			sort: Choice[str] = Sort.poll_id.name,
			tag: str = None,
			active: bool = None,
			published: bool = None,
		):
		"""Searches poll questions. Search by poll ID, or by keyword, and filter by tag."""

		await interaction.response.defer()

		sort = self.Sort.__members__[sort.value if not isinstance(sort, str) else sort]


		if poll_id:
			poll = await self.fetchpoll(poll_id)

			if not poll: poll = await self.bot.db.fetchrow("SELECT * FROM polls WHERE num = $1", poll_id)

			if not poll or (not poll['published'] and not await self.hasmanagerperms(interaction)):
				return await interaction.followup.send(f"Couldn't find a poll with the ID `{poll_id}`.")

			embed = await self.pollinfoembed(poll)

			await interaction.followup.send(embed=embed)
			# add shortcut buttons to delete (and edit maybe?)

			return

		else:
			notag = "-1"
			if tag:
				if (not tag.isdigit() or not await self.fetchtag(int(tag))) and not tag == notag:
					return await interaction.followup.send("Please select an available tag.")
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
				if tag != int(notag):
					queries.append("tag = ${}")
					values.append(tag)
					text.append(f"Tag: `{await self.tagname(tag)}`")
				else:
					queries.append("tag IS NULL")
					text.append(f"Tag: None")
			if published is not None:
				queries.append("published = ${}")
				values.append(published)
				text.append(f"Published? `{published}`")
			if active is not None:
				queries.append("active = ${}")
				values.append(active)
				text.append(f"Active? `{active}`")
			if sort:
				text.append(f"Sorted by `{sort.name}`")


			guildid = await self.fetchguildid(interaction)


			try:
				if not queries: polls = await self.bot.db.fetch("SELECT * FROM polls WHERE guild_id = $1", guildid)
				else: polls = await self.bot.db.fetch(f"SELECT * FROM polls WHERE {' AND '.join(queries).format(*list(range(1, len(values) + 1)))}", *values)
			except asyncpg.exceptions.InvalidRegularExpressionError:
				return await interaction.followup.send(f"Your keyword input `{keyword}` seems to have failed. Please make sure to only search using alphanumeric characters.")


			polls = self.sortpolls(polls, sort)

			if not polls:
				return await interaction.followup.send("No results found!")	

			msg = await interaction.followup.send("Searching...")

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
			PollSearchPaginator.colour = await self.fetchcolourbyid(await self.fetchguildid(interaction), None)

			paginator = await PollSearchPaginator.start(msg, entries=polls, per_page=15)
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
		return await self.autocomplete_tag(interaction, current, clear = "-1", clearname = "No tag.")







async def setup(bot):
	await bot.add_cog(PollsCog(bot))