import asyncio, asyncpg, copy, datetime, discord, enum, math, random, re, sys, traceback
from config import *
from cogs.time import TimeCog
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
x End polls

x SQL DB
x Slashies
x Schedule timer
x Startup timer
  x Check on threads
x Force sync update

x Vote on poll
  x update message function
  x update votes values in SQL function
x Add reaction adds to thread

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

x show user history
  x show unvoted polls

x tags
  x create
  x edit
  x crosspost

x end message repeat
x end message ping
x end message gives role

x update message gets in queue
  x if flag doesn't exist, trigger function that sets flag to false, updates message, and waits x secs
  x if flag already exists, set to true (if not already)
  x function loops ONLY IF flag is true
x recover buttons on start

- make fetching crossposts more efficient by indexing

x TOTAL VOTES

x info embed when voting
x better more informative info embed
x ditto for schedule embed
x format duration in info embed
x new embed for pretty

x fix search with better regex or smth

x set up better config

x me command single polls
- delete message doesn't break bot
x move database to testing
x check perms for commands

x on-startup views check for archived polls
- countdown command

- admin: see who's voted


- make a poll object



to test:
x auto schedule start
x auto schedule end
x schedule on schedule command
x schedule on start command
x schedule on end command
x questions with same time diff tags processed separately
x editing embed with hiding things

'''

# id (int), num (int), time (datetime), message_id (int), question (str), thread_question (str), choices (str[]), votes (int[]), image (str), published (bool), duration (datetime), guild_id (int), description (str), tag (int), show_question (bool), show_options (bool), show_voting (bool), active (bool), crosspost_message_ids (int[])

def poll_manager_only():
	async def actual_check(interaction: Interaction):
		return await interaction.client.hasmanagerperms(interaction)
	return app_commands.check(actual_check)

def owner_only():
	async def actual_check(interaction: Interaction):
		return await interaction.client.is_owner(interaction.user)
	return app_commands.check(actual_check)

def valid_guild_only():
	async def actual_check(interaction: Interaction):
		bot = interaction.client
		return await bot.validguild(interaction) or await bot.ismanagechannel(interaction.channel_id)
	return app_commands.check(actual_check)


class PollsCog(commands.Cog, name = "Polls"):
	"""Polls commands"""

	def __init__(self, bot):
		self.bot = bot

		self.bot.tree.on_error = self.on_app_command_error

		self.bot.tasks['poll_schedules'] = {
			"starts": {},
			"ends": {},
		}

		self.bot.updatemsg_lock = asyncio.Lock()
		self.bot.updatemsg_flags = {}

		self.sort = {
			self.Sort.poll_id: "Poll ID",
			self.Sort.newest: "Newest",
			self.Sort.oldest: "Oldest",
			self.Sort.most_votes: "Most votes",
			self.Sort.least_votes: "Least votes"
		}

		self.bot.hasmanagerperms = self.hasmanagerperms
		self.bot.ismanagechannel = self.ismanagechannel
		self.bot.validguild = self.validguild

		self.maxqlength = 200


		self.bot.loop.create_task(self.on_startup_scheduler())



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
	strf = lambda self, x: x.strftime('%a, %b %d, %Y ~ %I:%M:%S %p %Z%z').replace(" 0", " ")
	# Sun, Mar 6, 2022 ~ 3:30 PM UTC
	s = lambda self, x: "" if x == 1 else "s"

	def strfdelta(self, tdelta):
		d = {}
		d["week"], d["day"] = divmod(tdelta.days, 7)
		d["hour"], rem = divmod(tdelta.seconds, 3600)
		d["minute"], d["second"] = divmod(rem, 60)
		return d
	def strfduration(self, tdt):
		txt = []
		for k, v in self.strfdelta(tdt).items():
			if v:
				txt.append(f"{v} {k}{self.s(v)}")
		return ', '.join(txt)



	choiceformats = ['<:A_p:1013463917843976212>', '<:B_p:1013463919794335914>', '<:C_p:1013463921614651463>', '<:D_p:1013463923531460628>', '<:E_p:1013463925049802934>', '<:F_p:1013463927276974170>', '<:G_p:1013463930204594206>', '<:H_p:1013463932171718666>']
	choiceformat = lambda self, x: self.choiceformats[x]
	
	lineformats = ['<:lf:1013463941172703344>', '<:le:1013463936135331860>', '<:lfc:1013463943202738276>', '<:lec:1013463939327205467>', '<:ld:1013463933966884865>']
	def lineformat(self, x):
		if not x: return self.lineformats[3]

		txt = [0] * (x - 1) + [1]
		txt[0] = txt[0] + 2

		return ''.join([self.lineformats[i] for i in txt])

	def truncate(self, x, y = None, *, length = 100):
		y = " " + y if y else ""
		length -= len(y)
		if len(x) > length:
			words = x.split(" ")
			i = 1
			while len(" ".join(words[:i+1])) <= length - 3 and i < len(words):
				i += 1
			return " ".join(words[:i]) + "..." + y
		return x + y



	async def searchpollsbyid(self, poll_id, showunpublished = False):
		if showunpublished:
			return await self.bot.db.fetch("SELECT * FROM polls WHERE CAST(id AS TEXT) LIKE $1", f"{poll_id}%")
		else:
			return await self.bot.db.fetch("SELECT * FROM polls WHERE CAST(id AS TEXT) LIKE $1 AND published = true", f"{poll_id}%")

	async def searchpollsbykeyword(self, keyword, showunpublished = False):
		# if showunpublished:
		# 	return await self.bot.db.fetch("SELECT * FROM polls WHERE question ~* $1", keyword)
		# else:
		# 	return await self.bot.db.fetch("SELECT * FROM polls WHERE question ~* $1 AND published = true", keyword)
		results = await self.fetchallpolls(showunpublished)

		return self.keywordsearch(keyword, results)

		

	def keywordsearch(self, keyword, polls):
		alnum = lambda x: re.sub(r'[\W_]+', '', x.lower())
		lowered = alnum(keyword)
		return [i for i in polls if (any(lowered in alnum(i[j]) for j in ['question', 'thread_question', 'description'] if isinstance(i[j], str)) or any(lowered in alnum(j) for j in i['choices']))]

	async def fetchallpolls(self, showunpublished = False):
		if showunpublished:
			return await self.bot.db.fetch("SELECT * FROM polls")
		else:
			return await self.bot.db.fetch("SELECT * FROM polls WHERE published = true")

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

	async def fetchalltags(self):
		return await self.bot.db.fetch("SELECT * FROM pollstags")

	async def tagname(self, tagid: int):
		return (await self.fetchtag(tagid))['name']

	async def tagcolour(self, tagid: int):
		return (await self.fetchtag(tagid))['colour']

	async def fetchcolourbyid(self, guildid: int, tagid: int):
		guild = await self.fetchguildinfo(guildid)
		tag = await self.fetchtag(tagid)

		return self.fetchcolour(guild, tag)

	def fetchcolour(self, guild, tag):
		if tag and tag['colour']: return tag['colour']
		else: return guild['default_colour']

	def fetchchannelid(self, guild, tag):
		if tag and tag['channel_id']: return tag['channel_id']
		else: return guild['default_channel_id']



	async def fetchguildid(self, interaction: discord.Interaction):
		return (await self.fetchguildinfobymanagechannel(interaction.channel_id))['guild_id'] if await self.ismanagechannel(interaction.channel_id) else interaction.guild_id


	async def ismanagechannel(self, channelid: int):
		return await self.fetchguildinfobymanagechannel(channelid) is not None

	async def validguild(self, interaction: discord.Interaction):
		return await self.fetchguildinfo(interaction.guild_id) is not None

	async def hasmanagerperms(self, interaction: discord.Interaction):
		return await self.hasmanagerpermsbyuserandids(interaction.user, interaction.guild_id, interaction.channel_id)

	async def hasmanagerpermsbyuserandids(self, user, guild_id, channel_id = None):
		guild = await self.bot.db.fetchrow("SELECT * FROM pollsinfo WHERE guild_id = $1", guild_id)
		if not guild: return []
		if channel_id:
			manage_channels = await self.bot.db.fetch("SELECT * FROM pollsinfo WHERE manage_channel_id && $1", [channel_id])
		else: manage_channels = []

		guilds = []

		guilds += [i['guild_id'] for i in manage_channels]

		if any([r.id in guild['manager_role_id'] for r in user.roles]):
			guilds.append(guild['guild_id'])

		return guilds

	async def canview(self, poll, guild_id):
		if guild_id == poll['guild_id']:
			return True
		else: 
			tag = await self.fetchtag(poll['tag'])
			return tag and guild_id in tag['crosspost_servers']


	async def validtag(self, tag, key = lambda x: True):
		if tag.isdigit():
			tagobj = await self.fetchtag(int(tag))
			if tagobj and key(tagobj):
				return tagobj
			else:
				return None
		else:
			return None



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

		# a = await self.bot.db.fetchrow("SELECT * FROM polls WHERE id = $1", 63830)
		# print(type(a['time']), a['time'])
		# print(type(a['duration']), a['duration'])

		# await self.schedule_starts()

		# await ctx.send(embed = await self.pollinfoembed(await self.fetchpoll(60320)), view = await self.pollbuttons(60320))

		# await self.vote({'id': 88071}, ctx.author, 1)

		pass


	async def pollinfoembed(self, poll, *, guild = None, tag = None):
		if not guild: guild = await self.fetchguildinfo(poll['guild_id'])
		if not tag: tag = await self.fetchtag(poll['tag'])

		if not poll['num']:
			embed = discord.Embed(title = poll['question'])
		else:
			embed = discord.Embed(title = f"#{poll['num']}: {poll['question']}")

		embed.description = poll['description']

		embed.colour = self.fetchcolour(guild, tag)


		if not poll['votes']:
			embed.add_field(name = "Choices", value = "\n".join([f'- {c}' for c in poll['choices']]), inline = False)
		else:
			embed.add_field(name = "Choices", value = "\n".join([f'- ({v}) {c}' for v, c in zip(poll['votes'], poll['choices'])]) + f"\nTotal votes: **{sum(poll['votes'])}**", inline = False)

		embed.add_field(name = "Published?", value = poll['published'])
		embed.add_field(name = "Active?", value = poll['active'])

		if poll['thread_question']: embed.add_field(name = "Thread Question", value = poll['thread_question'])
		if poll['tag']: embed.add_field(name = "Tag", value = f"`{tag['name']}`")

		if poll['time']: embed.add_field(name = "Publish Date", value = f"<t:{int(poll['time'].timestamp())}:F> (`{int(poll['time'].timestamp())}`)")
		if poll['duration']: embed.add_field(name = "Duration", value = self.strfduration(poll['duration']))

		if poll['message_id']:
			try:
				message = await self.bot.get_channel(self.fetchchannelid(guild, tag)).fetch_message(poll['message_id'])
				embed.add_field(name = "Poll Message", value = f"[{poll['question']}]({message.jump_url})")
			except NotFound:
				embed.add_field(name = "Poll Message", value = f"Can't locate message {message_id}")

		display = [[poll['show_question'], "Question"], [poll['show_options'], "Options"], [poll['show_voting'], "Current Votes"]]
		displaysort = {"Showing": [], "Not showing": []}
		[displaysort["Showing"].append(i[1]) if i[0] else displaysort["Not showing"].append(i[1]) for i in display]
		embed.add_field(name = "Display", value = "\n".join([f"{k}: {', '.join(v)}" for k, v in displaysort.items() if v]))

		if poll['image']: embed.set_image(url = poll['image'])

		embed.set_footer(text = f"ID: {poll['id']} | {guild['guild_id']}")

		return embed

	async def pollquestionembed(self, poll, *, guild = None, tag = None, interaction = None, showextra = False):
		if not guild: guild = await self.fetchguildinfo(poll['guild_id'])
		if not tag: tag = await self.fetchtag(poll['tag'])

		if showextra and interaction is None:
			showextra = False

		embed = discord.Embed()

		if poll['show_question']:
			if not poll['num']:
				embed.title = poll['question']
			else:
				embed.title = f"#{poll['num']}: {poll['question']}"

			embed.description = poll['description']

		embed.colour = self.fetchcolour(guild, tag)

		txt = []
		if poll['published']:
			max_length = 10
			max_vote = max(poll['votes'])
			total_votes = sum(poll['votes'])
			for c, v, n in zip(poll['choices'], poll['votes'], range(len(poll['choices']))):
				if poll['show_voting']:
					x = (v * max_length) // max_vote if max_vote else 0
					p = v / total_votes if total_votes else 0
					if poll['show_options']:
						embed.add_field(name = f"{self.lineformats[4]} {c}", value = f"{self.choiceformat(n)}{self.lineformat(x)} **{v}** vote{self.s(v)} ({round(p * 100)}%)", inline = False)
					else:
						txt.append(f"{self.choiceformat(n)}{self.lineformat(x)} **{v}** vote{self.s(v)} ({round(p * 100)}%)")
				elif poll['show_options']:
					txt.append(f"{self.choiceformat(n)} {poll['choices'][n]}")
			txt.append(f"Total votes: **{sum(poll['votes'])}**")
		else:
			for c, n in zip(poll['choices'], range(len(poll['choices']))):
				if poll['show_options']:
					txt.append(f"{self.choiceformat(n)} {poll['choices'][n]}")
		if txt:
			if not poll['show_voting']:
				embed.add_field(name = "Choices", value = '\n'.join(txt), inline = False)
			else:
				if not poll['show_options']:

					cap = 0
					while len('\n'.join(txt[:cap + 1])) <= 1024:
						if cap == len(txt):
							break
						cap += 1

					embed.add_field(name = "Choices", value = '\n'.join(txt[:cap]), inline = False)
					if txt[cap:]:
						embed.add_field(name ="--", value = '\n'.join(txt[cap:]), inline = False)
				else:
					embed.add_field(name = "Voting", value = '\n'.join(txt))


		name = ""
		value = ""
		if poll['duration'] and poll['published']:
			end_time = poll['time'] + poll['duration']
			if poll['active']: name = "Poll ends at"
			else: name = "Poll finished at"
			value = "<t:{0}:f>, <t:{0}:R>\n\n".format(int(end_time.timestamp()))
		elif poll['active']:
			name = "The poll is currently open for voting!"
			if not showextra:
				value = "Vote now!"


		if showextra and poll['published']:
			try:
				if interaction.guild_id == poll['guild_id']:
					msg = await interaction.guild.get_channel(guild['default_channel_id']).fetch_message(poll['message_id'])
				elif tag and interaction.guild_id in tag['crosspost_servers']:
					found = False
					for cid in tag['crosspost_channels']:
						channel = interaction.guild.get_channel(cid)
						if channel:
							for mid in poll['crosspost_message_ids']:
								try:
									msg = await channel.fetch_message(mid)
								except NotFound:
									continue
								else:
									found = True
									break
						if found: break

				if msg:
					value += f"Vote [here](<{msg.jump_url}>)!"
			except NotFound:
				pass

		if name and value:
			embed.add_field(name = name, value = value)


		if poll['thread_question'] and (not showextra or poll['active']): embed.add_field(name = "Discuss in the thread:", value = poll['thread_question'])

		if poll['image']: embed.set_image(url = poll['image'])

		if tag:
			embed.set_footer(text = f"{tag['name']} • [{poll['id']}]")
		else:
			embed.set_footer(text = f"[{poll['id']}]")

		return embed

	async def pollfooterembed(self, poll, user, *, guild = None, tag = None):
		if not guild: guild = await self.fetchguildinfo(poll['guild_id'])
		if not tag: tag = await self.fetchtag(poll['tag'])

		embed = discord.Embed()

		if poll['show_question']:
			if not poll['num']:
				embed.title = poll['question']
			else:
				embed.title = f"#{poll['num']}: {poll['question']}"

		embed.colour = self.fetchcolour(guild, tag)


		if poll['show_voting'] or await self.hasmanagerpermsbyuserandids(user, guild['guild_id']):
			txt = []
			max_length = 10
			max_vote = max(poll['votes'])
			total_votes = sum(poll['votes'])
			for c, v, n in zip(poll['choices'], poll['votes'], range(len(poll['choices']))):
				x = (v * max_length) // max_vote if max_vote else 0
				p = v / total_votes if total_votes else 0
				txt.append(f"{self.choiceformat(n)}{self.lineformat(x)} **{v}** vote{self.s(v)} ({round(p * 100, 2)}%)")

			ishidden = not poll['show_voting']

			cap = 0
			while len('\n'.join(txt[:cap + 1])) <= 1024:
				if cap == len(txt):
					break
				cap += 1

			embed.add_field(name = f"Votes {'(not revealed publicly, keep it a secret!)' if ishidden else ''}", value = '\n'.join(txt[:cap]), inline = False)
			if txt[cap:]:
				embed.add_field(name ="--", value = '\n'.join(txt[cap:]), inline = False)

		else:
			embed.add_field(name = "Votes", value = "Votes are hidden!")


		txt = []
		vote = await self.vote(poll, user)
		if vote is not None:
			txt.append(f"You've voted: {self.choiceformat(vote)}")
			if poll['show_options']: txt[-1] += f" *{poll['choices'][vote]}*"
		else:
			if poll['active']:
				txt.append(f"You haven't voted yet!")
			else:
				txt.append(f"You didn't vote!")

		embed.add_field(name = "Your vote", value = '\n'.join(txt))

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


	guild_ids = None if global_slashies else [288896937074360321, 1010550869391065169]
		
	pollsgroup = app_commands.Group(name="polls", description="Poll commands", guild_ids=guild_ids)
	
	pollsadmingroup = app_commands.Group(name="pollsadmin", description="Poll administrative commands", guild_ids=guild_ids)

	pollsadmintaggroup = app_commands.Group(name="tag", description="Tag management commands", parent=pollsadmingroup, guild_ids=guild_ids)

	pollsadmincrosspostgroup = app_commands.Group(name="crosspost", description="Crosspost management commands", parent=pollsadmingroup, guild_ids=guild_ids)



	async def autocomplete_tag(self, interaction: discord.Interaction, current: str, *, clear = None, clearname = "Clear tag.", local = True):
		if clear is not None:
			emptychoice = app_commands.Choice(name = clearname, value = clear)
			if current == clear:
				return [emptychoice]
		if local:
			tags = await self.fetchtagsbyguildid(interaction.guild_id)
		else:
			tags = await self.fetchalltags()
		choices = [app_commands.Choice(name = t['name'], value = str(t['id'])) for t in tags if re.search(f"^{current.lower()}", t['name'], re.IGNORECASE)][:25]
		if current == "" and clear is not None: 
			choices = choices[:24]
			choices.append(emptychoice)
		return choices

	async def autocomplete_searchbypollid(self, interaction: discord.Interaction, current: int, *, published = None, active = None, returnresults = False, local = True, crosspost = False):
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
			regex = [f"^\b{lowered}\b", f"\b{lowered}\b", f"^{lowered}", lowered, ""]
			results = self.sortpolls(results)
			results.sort(key = lambda x: [bool(re.search(i, x['question'].lower())) for i in regex].index(True))

		if published is not None:
			results = [i for i in results if i['published'] == published]
		if active is not None:
			results = [i for i in results if i['active'] == active]

		if local:
			tags = await self.fetchalltags()
			findtag = lambda x: next(i for i in tags if i['id'] == x['tag'])

			guilds = await self.hasmanagerperms(interaction)
			if interaction.guild_id not in guilds: guilds.append(interaction.guild_id)
			newresults = []
			for i in results:
				if i['guild_id'] in guilds:
					newresults.append(i)
				elif crosspost:
					try:
						crosspostmatch = [g in findtag(i)['crosspost_servers'] for g in guilds]
						if any(crosspostmatch):
							newresults.append(i)
					except StopIteration:
						continue
			results = newresults
			# results = [i for i in results if i['guild_id'] in guilds or (any(g in findtag(i)['crosspost_servers'] for g in guilds) and crosspost)]


		if returnresults: return results

		choices = [app_commands.Choice(name = self.truncate(f"[{i['id']}] {i['question']}"), value = i['id']) for i in results[:25]]
		return choices

	async def autocomplete_duration(self, interaction: discord.Interaction, current: float, *, clear = None):
		choices = []

		strcurrent = current if isinstance(current, str) else (str(current) if not math.isnan(current) else "")
		try:
			current = float(current)

			if clear and (current == clear or math.isnan(current)):
				choices += [app_commands.Choice(name = f"Clear duration value.", value = -1)]
				
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

				for t in times:
					secs = int(round(t[0].total_seconds(), 0))
					if 15 <= secs <= 60480000: # Between 15s and 100w
						f = lambda x: int(x) if x.is_integer() else x
						choices.append(app_commands.Choice(name = f"{f(current)} {t[1]}{self.s(f(current))}", value = secs))
		except ValueError:
			pass

		if not isinstance(current, float) or current >= 1970 or math.isnan(current):
			timestamp = TimeCog.strtodatetime(TimeCog, strcurrent)
			choices += [app_commands.Choice(name = f"End at: {self.strf(t)}", value = int(t.timestamp())) for t in timestamp]

		return choices[:25]




	async def on_app_command_error(self, interaction: Interaction, error: AppCommandError):
		if isinstance(error, app_commands.errors.CheckFailure):
			if await self.validguild(interaction):
				return await interaction.response.send_message(f"You need to be a <@&{(await self.fetchguildinfo(interaction.guild_id))['manager_role_id'][0]}> to do that!", ephemeral = True)
			else:
				return await interaction.response.send_message(f"This command is not available here!", ephemeral = True)

		await interaction.followup.send("Something broke!")
		_log.error('Ignoring exception in command %r', interaction.command.name, exc_info=error)



	async def splitstartpolls(self, poll_ids: list, *, set_time = None, natural = False):
		if not isinstance(poll_ids, list):
			poll_ids = [poll_ids]

		polls = {}
		for poll_id in poll_ids:
			poll = await self.fetchpoll(poll_id)
			tag = await self.fetchtag(poll['tag'])
			tid = None if not tag else tag['id']
			if tid in polls.keys(): polls[tid].append(poll_id)
			else: polls[tid] = [poll_id]

		for t, p in polls.items():
			await self.startpolls(p, set_time = set_time, natural = natural)

	async def startpoll(self, poll_id, **kwargs):
		return await self.startpolls([poll_id], **kwargs)

	async def startpolls(self, poll_ids: list, *, set_time = None, natural = False):
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
		channel_id = self.fetchchannelid(guild, tag)

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

		try:
			await self.bot.db.execute("ALTER TABLE pollsvotes ADD \"{}\" integer".format(str(poll['id'])))
		except asyncpg.exceptions.DuplicateColumnError:
			await self.bot.db.execute("ALTER TABLE pollsvotes DROP COLUMN \"{}\"".format(str(poll['id'])))
			await self.bot.db.execute("ALTER TABLE pollsvotes ADD \"{}\" integer".format(str(poll['id'])))


		msgs = [[await self.formatpollmessage(p), p] for p in [i[0] for i in polls]]
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

		await self.bot.db.execute("UPDATE polls SET crosspost_message_ids = $2 WHERE id = $1", poll['id'], [])
		for txt, poll in msgs:
			final.append([poll, await send(txt, poll, channel)])
			for ch in crossposts:
				final.append([poll, await send(txt, poll, ch, main = False)])
				

		for poll, t in polls:
			if poll['time']: # needs to be old time
				await self.schedule_starts(timestamps = [poll['time'].timestamp()], natural = natural)
			if poll['duration']:
				await self.schedule_ends(poll_ids = [poll['id']], natural = natural)


		if tag and tag['end_message']:
			txt = {
				"content": None,
				"embed": None,
				"view": None
				}

			view = None
			if tag['end_message_role_ids'] and tag['end_message_self_assign']:
				view = self.SelfAssignRoleView(tag['end_message_role_ids'])


			txt['embed'] = discord.Embed(description = tag['end_message'], colour = await self.fetchcolourbyid(guild['guild_id'], tag['id']))

			def getroles(channel):
				roles = []
				for r in tag['end_message_role_ids']:
					role = channel.guild.get_role(r)
					if role: roles.append(role)
				return roles

			roles = getroles(channel)
			txt['content'] = " ".join([r.mention for r in roles])
			txt['view'] = view if roles else None
			endmsgs = [await channel.send(**txt)]

			for ch in crossposts:
				roles = getroles(ch)
				txt['content'] = " ".join([r.mention for r in roles])
				txt['view'] = view if roles else None
				endmsgs.append(await ch.send(**txt))


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



		poll = await self.fetchpoll(poll['id'])
		await self.updatepollmessage(poll)


		return final




	async def endpoll(self, poll_id, *, set_time = False, lock_thread = True, natural = True):

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

		if poll['duration']:
			await self.schedule_ends(poll_ids = [poll['id']], natural = natural)

		channel = self.bot.get_channel(channel_id)
		crossposts = [self.bot.get_channel(i) for i in tag['crosspost_channels']] if tag else []

		guilds = [self.bot.get_guild(g) for g in {i.guild.id for i in [channel] + crossposts}]

		try:
			if poll['thread_question']:
				for thread_id in [poll['message_id']] + (poll['crosspost_message_ids'] if poll['crosspost_message_ids'] else []):
					for g in guilds:
						thread = g.get_channel_or_thread(thread_id)
						if thread is None:
							continue
						else:
							await thread.edit(archived = True, locked = True)
							break
		except Exception as e:
			traceback.print_exc()

		poll = await self.fetchpoll(poll['id'])
		await self.updatepollmessage(poll)




	async def scheduler(self, polls, start: bool):
		if not isinstance(polls, list):
			polls = [polls]

		if start:
			time = polls[0]['time']
		else:
			time = polls[0]['time'] + polls[0]['duration']

		# Saving on memory
		polls = [i['id'] for i in polls]


		sleepduration = time - discord.utils.utcnow()
		if sleepduration.total_seconds() > 0:
			print(f"[Polls Scheduler] ({', '.join(str(i) for i in polls)}) Started schedule \"{'start' if start else 'end'}\" to end in {sleepduration} ({time})")
			await asyncio.sleep(sleepduration.total_seconds())
		else:
			print(f"[Polls Scheduler] ({', '.join(str(i) for i in polls)}) {'Started' if start else 'Ended'} poll immediately from overdue timer ({time})")


		if start:
			await self.splitstartpolls(polls, natural = True)
		else:
			for p in polls:
				await self.endpoll(p, natural = True)

		print(f"[Polls Scheduler] ({', '.join(str(i) for i in polls)}) Successfully {'started' if start else 'ended'} poll")


	async def schedule_starts(self, *, timestamps = [], natural = False):
		polls = await self.bot.db.fetch("SELECT * FROM polls WHERE time IS NOT NULL AND published = $1", False)

		for k, v in self.bot.tasks['poll_schedules']['starts'].items():
			if (not timestamps or k in timestamps) and not natural:
				print(f"[Polls Scheduler] Cancelled \"start\" scheduler at {k} ({datetime.datetime.fromtimestamp(k, datetime.timezone.utc)})")
				v.cancel()

		groups = {}

		for p in polls:
			if p['time'] not in groups.keys():
				groups[p['time']] = [p]
			else:
				groups[p['time']].append(p)

		for k, v in groups.items():
			if k:
				if not timestamps or k.timestamp() in timestamps:
					self.bot.tasks['poll_schedules']['starts'][k.timestamp()] = self.bot.loop.create_task(self.scheduler(v, True))

	async def schedule_ends(self, *, poll_ids: list = [], natural = False):
		polls = await self.bot.db.fetch("SELECT * FROM polls WHERE duration IS NOT NULL AND active = $1", True)

		for k, v in self.bot.tasks['poll_schedules']['ends'].items():
			if (not poll_ids or k in poll_ids) and not natural:
				print(f"[Polls Scheduler] Cancelled \"end\" scheduler for ({k})")
				v.cancel()


		for p in polls:
			if p['duration']:
				if not poll_ids or p['id'] in poll_ids:
					self.bot.tasks['poll_schedules']['ends'][p['id']] = self.bot.loop.create_task(self.scheduler(p, False))

	async def on_startup_scheduler(self):
		while not self.bot.postgresql_loaded:
			await asyncio.sleep(0.1)
		self.bot.loop.create_task(self.schedule_starts())
		self.bot.loop.create_task(self.schedule_ends())
		self.bot.loop.create_task(self.on_startup_buttons())
		self.bot.loop.create_task(self.on_startup_selfassign())




	async def formatpollmessage(self, poll):
		content = None
		embed = await self.pollquestionembed(poll)
		view = await self.pollbuttons(poll['id'], active = poll['active'])

		return {
			"content": content,
			"embed": embed,
			"view": view,
		}

	async def updatepollmessage(self, poll):
		async with self.bot.updatemsg_lock:
			if poll['id'] not in self.bot.updatemsg_flags.keys():
				self.bot.updatemsg_flags[poll['id']] = True
				self.bot.loop.create_task(self.loop_updatepollmessage(poll))
			else:
				self.bot.updatemsg_flags[poll['id']] = True

	async def loop_updatepollmessage(self, poll):
		while self.bot.updatemsg_flags[poll['id']] == True:
			self.bot.updatemsg_flags[poll['id']] = False

			await self.do_updatepollmessage(poll)

			wait = 2
			await asyncio.sleep(wait)
		self.bot.updatemsg_flags.pop(poll['id'])


	async def do_updatepollmessage(self, poll, force = False):
		tag = await self.fetchtag(poll['tag'])
		guild = await self.fetchguildinfo(poll['guild_id'])
		channel_id = self.fetchchannelid(guild, tag)

		channel = self.bot.get_channel(channel_id)
		crossposts = [self.bot.get_channel(i) for i in tag['crosspost_channels']] if tag else []

		await self.updatevotes(poll)
		poll = await self.fetchpoll(poll['id'])

		txt = await self.formatpollmessage(poll)

		msg = await channel.fetch_message(poll['message_id'])

		if not force and txt['content'] == msg.content and msg.embeds and msg.embeds[0] == txt['embed']:
			return

		if msg.author.id == self.bot.user.id:
			await msg.edit(**txt)

		if poll['crosspost_message_ids']:
			for mid in poll['crosspost_message_ids']:
				for ch in crossposts:
					try:
						msg = await ch.fetch_message(mid)
					except NotFound:
						continue
					else:
						if msg.author.id == self.bot.user.id:
							await msg.edit(**txt)

	async def updatevotes(self, poll):
		votes = await self.bot.db.fetch("SELECT \"{}\" FROM pollsvotes".format(poll['id']))
		votes = [i[str(poll['id'])] for i in votes]
		total = [votes.count(i) for i in range(len(poll['choices']))]
		if total != poll['votes']:
			await self.bot.db.execute("UPDATE polls SET votes = $2 WHERE id = $1", poll['id'], total)
		return total




	class PollView(discord.ui.View):
		def __init__(self, client, poll, *, active = True):
			super().__init__(timeout=None)

			if active:
				if len(poll['choices']) <= 4:
					for c, n in zip(poll['choices'], range(len(poll['choices']))):
						self.add_item(self.ChoiceButton(
							client, poll, self.vote,
							emoji = client.choiceformat(n),
							custom_id = f"{poll['id']}{n}",
							row = (n) // 4,
							disabled = not active
							))
				else:
					self.add_item(self.ChoiceOptions(
						client, poll, self.vote,
						custom_id = f"{poll['id']}^",
						row = 0,
						disabled = not active,
						))

				self.add_item(self.ClearVoteButton(
					client, poll, self.vote,
					label = "Clear Vote",
					style = discord.ButtonStyle.red,
					custom_id = "-1",
					row = 2,
					disabled = not active
					))

			self.add_item(self.InfoButton(
				client, poll,
				emoji = "<:info:1014581512001294366>",
				style = discord.ButtonStyle.green,
				custom_id = str(poll['id']),
				row = 2,
				))


		async def vote(self, client, poll, interaction, value):
			await interaction.response.defer()

			poll = await client.fetchpoll(poll['id'])

			if poll['active']:
				await client.vote(poll, interaction.user, value)
				qid = f"*{poll['question']}* ({poll['id']})" if poll['show_question'] else f"`{poll['id']}`"

				if value != -1:
					if poll['show_options']:
						await interaction.followup.send(f"On the poll {qid}, you voted:\n{client.choiceformat(value)}: {poll['choices'][value]}", ephemeral = True)
					else:
						await interaction.followup.send(f"On the poll {qid}, you voted:\n{client.choiceformat(value)}", ephemeral = True)
				else:
					await interaction.followup.send(f"**Cleared** your vote on the poll {qid}", ephemeral = True)

				await client.add_to_thread(interaction, poll, value)

			else:
				await interaction.followup.send(f"This poll has ended!", ephemeral = True)


		class ChoiceButton(discord.ui.Button):
			def __init__(self, client, poll, vote, **kwargs):
				super().__init__(**kwargs)
				self.client = client
				self.poll = poll
				self.vote = vote
				self.value = int(self.custom_id) % 10

			async def callback(self, interaction: discord.Interaction):
				await self.vote(self.client, self.poll, interaction, self.value)


		class ChoiceOptions(discord.ui.Select):
			def __init__(self, client, poll, vote, *, placeholder = "Click here to vote", **kwargs):
				self.client = client
				self.poll = poll
				self.vote = vote

				options = []

				for c, n in zip(poll['choices'], range(len(poll['choices']))):
					label = c if poll['show_options'] else "Vote!"
					options.append(discord.SelectOption(
						emoji = client.choiceformat(n),
						value = str(n),
						label = label
						))

				super().__init__(
					placeholder = placeholder,
					min_values = 1, max_values = 1,
					options = options,
					**kwargs
					)

			async def callback(self, interaction: discord.Interaction):
				await self.vote(self.client, self.poll, interaction, int(self.values[0]))


		class ClearVoteButton(discord.ui.Button):
			def __init__(self, client, poll, vote, **kwargs):
				super().__init__(**kwargs)
				self.client = client
				self.poll = poll
				self.vote = vote

			async def callback(self, interaction: discord.Interaction):
				await self.vote(self.client, self.poll, interaction, int(self.custom_id))

		class InfoButton(discord.ui.Button):
			def __init__(self, client, poll, **kwargs):
				super().__init__(**kwargs)
				self.client = client
				self.poll = poll

			async def callback(self, interaction: discord.Interaction):
				await interaction.response.defer()

				await interaction.followup.send(embed = await self.client.pollfooterembed(self.poll, interaction.user), ephemeral = True)

	async def pollbuttons(self, poll_id, **kwargs):
		poll = await self.fetchpoll(poll_id)

		return self.PollView(self, poll, **kwargs)
		
	async def on_startup_buttons(self):
		polls = await self.bot.db.fetch("SELECT * FROM polls WHERE published = $1", True)
		polls.sort(key = lambda x: discord.utils.utcnow() - x['time'])
		polls.sort(key = lambda x: not x['active'])

		for poll in polls:
			view = await self.pollbuttons(poll['id'], active = poll['active'])
			self.bot.add_view(view)


	async def vote(self, poll, user, choice = None):
		vote = await self.bot.db.fetchrow("SELECT * FROM pollsvotes WHERE user_id = $1", user.id)
		if not vote:
			await self.bot.db.execute("INSERT INTO pollsvotes (user_id) VALUES ($1)", user.id)
			vote = await self.bot.db.fetchrow("SELECT * FROM pollsvotes WHERE user_id = $1", user.id)

		if poll['active'] and choice is not None:
			if choice == -1: choice = None
			await self.bot.db.execute("UPDATE pollsvotes SET \"{}\" = $2 WHERE user_id = $1".format(str(poll['id'])), user.id, choice)

			await self.updatepollmessage(poll)

			return choice
		else:
			return vote[str(poll['id'])]

	async def add_to_thread(self, interaction, poll = None, choice = None, show_vote = False):
		thread = interaction.message.guild.get_channel_or_thread(interaction.message.id)
		if thread and poll['thread_question']:
			try:
				try:
					await thread.fetch_member(interaction.user.id)
				except NotFound:
					# await thread.add_user(interaction.user)
					if choice is not None:
						embed = discord.Embed()
						embed.description = f"Discuss: *{poll['thread_question']}*"
						embed.set_footer(text = "See pins for the above question!")
						await thread.send(f"{interaction.user.mention}, thanks for voting!", embed=embed, delete_after=30)
			except Forbidden:
				pass
			finally:
				pass
				# if show_vote and poll and choice is not None:
				# 	embed = discord.Embed()
				# 	embed.description = f"{interaction.user.mention} voted for {self.choiceformat(choice)} *{poll['choices'][choice]}*\nIn this thread, discuss: {poll['thread_question']}"
				# 	await thread.send(embed=embed)



	class SelfAssignRoleView(discord.ui.View):
		def __init__(self, role_ids):
			super().__init__(timeout=None)
			role_ids.sort()

			self.add_item(self.SelfAssignButton(
				role_ids,
				label = "Get role!",
				custom_id = ",".join(str(i) for i in role_ids)
				))

		class SelfAssignButton(discord.ui.Button):
			def __init__(self, role_ids, **kwargs):
				super().__init__(**kwargs)
				self.role_ids = role_ids

			async def callback(self, interaction: discord.Interaction):
				user = interaction.user

				roles = []
				for r in self.role_ids:
					role = interaction.guild.get_role(r)
					if role: roles.append(role)

				rolepings = " ".join(r.mention for r in roles)

				if any(i not in user.roles for i in roles):
					await user.add_roles(*roles)
					return await interaction.response.send_message(f"Successfully **gave** you the roles: {rolepings}. Click again to remove.", ephemeral = True)
				else:
					await user.remove_roles(*roles)
					return await interaction.response.send_message(f"Sucessfully **removed** from you these roles: {rolepings}. Click again to re-add.", ephemeral = True)

	async def on_startup_selfassign(self):
		tags = await self.bot.db.fetch("SELECT * FROM pollstags WHERE end_message_self_assign = $1 and cardinality(end_message_role_ids) <> 0", True)

		for t in tags:
			view = self.SelfAssignRoleView(t['end_message_role_ids'])
			self.bot.add_view(view)


	class EditModal(discord.ui.Modal):
		def __init__(self, *, title, texts):
			super().__init__(title = title)

			self.texts = texts
			self.values = {}

			for k, v in self.texts.items():
				self.add_item(v)
		
		async def on_submit(self, interaction: discord.Interaction):
			self.values = {k: str(v) for k, v in self.texts.items()}
			await interaction.response.defer()
			self.interaction = interaction

		async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
				await interaction.response.send_message('Something broke!', ephemeral=True)
				traceback.print_tb(error.__traceback__)

	class EditView(discord.ui.View):
		def __init__(self, *, items, modal, groups, title):
			super().__init__(timeout=None)
			self.items = items
			self.modal = modal
			self.msg = None
			self.groups = groups
			self.title = title

			self.interaction = None
			self.status = False

			self.checks = []
			self.incomplete = {}

			self.add_check(
				lambda x: not any(i.required and not i.value for i in x.values()),
				"You have not completed all required fields"
			)

			for k, v in groups.items():
				self.add_item(self.EditButton(
					select=v, label=k,
					row=0
					))

			
			self.add_item(self.ConfirmButton(confirm=True, label="Confirm", style=discord.ButtonStyle.green)),
			self.add_item(self.ConfirmButton(confirm=False, label="Cancel", style=discord.ButtonStyle.red))

			self.check_confirm()


		class EditButton(discord.ui.Button):
			def __init__(self, *, select, **kwargs):
				super().__init__(**kwargs)
				self.select = select

			async def callback(self, interaction: discord.Interaction):
				modal = self.view.modal(title = self.view.title, texts={i: self.view.items[i].text_input() for i in self.select})
				await interaction.response.send_modal(modal)
				await modal.wait()
				for k, v in modal.values.items():
					self.view.items[k].value = v if v else None
				await self.view.update_message(self.view)
				self.view.check_confirm()
				await self.view.update_view()

		class ConfirmButton(discord.ui.Button):
			def __init__(self, *, confirm, **kwargs):
				super().__init__(**kwargs, custom_id=f'c-{confirm}')
				self.value = confirm

			async def callback(self, interaction: discord.Interaction):
				self.view.status = self.value
				self.view.interaction = interaction
				self.view.stop()

				for child in self.view.children:
					child.disabled = True

		class IncompleteButton(discord.ui.Button):
			def __init__(self, label):
				super().__init__(disabled = True, label = label)

		async def update_message(self):
			raise NotImplementedError()

		async def update_view(self):
			await self.msg.edit(view=self)

		def check_confirm(self):
			complete = True
			for check, error in self.checks:
				incomplete = not check(self.items)
				complete = complete and not incomplete
				if incomplete and error not in self.incomplete:
					self.incomplete[error] = next(i for i in self.add_item(self.IncompleteButton(error)).children if i.label == error)
				elif not incomplete and error in self.incomplete:
					self.remove_item(self.incomplete[error])
					self.incomplete.pop(error)

			# for child in [c for c in self.children if c.custom_id.split('-')[0] == 'c']:
			for child in [c for c in self.children if c.custom_id == "c-True"]:
				child.disabled = not complete

		def add_check(self, check, error):
			"""check() returns True if input is valid""" 
			self.checks.append([check, error])

	class EditItem():
		def __init__(self, *, name, value = None, placeholder = None, max_length = None, required = True, style = discord.TextStyle.short):
			self.name = name
			self.value = value
			self.placeholder = placeholder
			self.max_length = max_length
			self.required = required
			self.style = style

		def text_input(self):
			return discord.ui.TextInput(
				label = self.name,
				placeholder = self.placeholder,
				default = self.value,
				style = self.style,
				required = self.required,
				max_length = self.max_length
			)

	def editmodalembed(self, groups, items, *, title, description):
		embed = discord.Embed(title = title, description = description, colour = 0x2f3136)

		for k, v in groups.items():
			embed.add_field(name = k, value = "\n".join(f"**{items[i].name}**: {items[i].value if not items[i].required or items[i].value is not None else '__**REQUIRED**__'}" for i in v))

		if 'image' in items.keys() and items['image'].value:
			if items['image'].value.lower().startswith('http'):
				embed.set_image(url = items['image'].value)
			else:
				embed.add_field(name = "Invalid Image URL", value = "That doesn't look like a valid image URL! Make sure you've pasted the image URL correctly!")

		return embed



	@pollsgroup.command(name="create")
	@poll_manager_only()
	@valid_guild_only()
	@app_commands.describe(
		question = "Main Poll Question to ask.",
		description = "Additional notes/description about the question.",
		opt_1 = "Option 1.", opt_2 = "Option 2.", opt_3 = "Option 3.", opt_4 = "Option 4.", opt_5 = "Option 5.", opt_6 = "Option 6.", opt_7 = "Option 7.", opt_8 = "Option 8.",
		thread_question = "Question to ask in the accompanying Thread.",
		image = "Image to accompany Poll Question.",
		tag = "Tag categorising this Poll Question.",
		show_question = "Show question in poll message. Defaults to true.", show_options = "Show options in poll message. Defaults to true.", show_voting = "Show the current state of votes in poll message. Defaults to true."
		)
	async def pollcreate(self, interaction: discord.Interaction, 
			question: str = None, 
			opt_1: str = None, opt_2: str = None, 
			description: str = None,
			thread_question: str = None,
			image: Attachment = None,
			tag: str = None,
			opt_3: str = None, opt_4: str = None, opt_5: str = None, opt_6: str = None, opt_7: str = None, opt_8: str = None,
			show_question: bool = True, show_options: bool = True, show_voting: bool = True
		):
		"""Creates a poll question."""

		await interaction.response.defer()

		choices = [i for i in [opt_1, opt_2, opt_3, opt_4, opt_5, opt_6, opt_7, opt_8] if i]

		if image and image.content_type.split('/')[0] == 'image':
			image = image.url

		if tag:
			guild_id = await self.fetchguildid(interaction)
			tag = await self.validtag(tag, lambda x: x['guild_id'] == guild_id)
			if tag is None:
				return await interaction.followup.send("Please select an available tag.")
			tag = tag['id']

		while True:
			poll_id = random.randint(10000, 99999)
			if not await self.bot.db.fetchrow("SELECT id FROM polls WHERE id = $1", poll_id):
				break

		# id (int), num (int), time (datetime), message_id (int), question (str), thread_question (str), choices (str[]), votes (int[]), image (str), published (bool), duration (datetime), guild_id (int), description (str), tag (int), show_question (bool), show_options (bool), show_voting (bool), active (bool), crosspost_message_ids (int[])

		poll = {
			'id': poll_id,
			'question': question,
			'published': False,
			'active': False,
			'guild_id': interaction.guild_id,
			'choices': choices,
			'votes': None,
			'time': None,
			'duration': None,
			'num': None,
			'message_id': None,
			'crosspost_message_ids': None,
			'tag': tag,
			'image': image,
			'description': description,
			'thread_question': thread_question,
			'show_question': show_question,
			'show_options': show_options,
			'show_voting': show_voting,
		}


		if question is None or len(choices) < 2:
			groups = {
				'Edit info': ['question', 'description', 'thread_question', 'image'],
				'Edit options (1-4)': [f'opt_{i}' for i in range(1, 4 + 1)],
				'Edit options (5-8)': [f'opt_{i}' for i in range(5, 8 + 1)]
			}

			opt = lambda n, req: self.EditItem(
				name = f"Option #{n}",
				placeholder = f'Type option #{n} here...',
				value = poll['choices'][n - 1] if n <= len(poll['choices']) else None,
				style = discord.TextStyle.long,
				required = req,
				max_length = self.maxqlength
				)

			defaultlength = 500
			items = {
				'question': self.EditItem(
					name = 'Question',
					placeholder = 'Type your question here...',
					value = poll['question'],
					style = discord.TextStyle.long,
					max_length = self.maxqlength
				),

				'description': self.EditItem(
					name = 'Description',
					placeholder = 'Type your description here...',
					value = poll['description'],
					style = discord.TextStyle.long,
					required = False,
					max_length = defaultlength
				),

				'thread_question': self.EditItem(
					name = 'Thread Question',
					placeholder = 'Type your thread question here...',
					value = poll['thread_question'],
					style = discord.TextStyle.long,
					required = False,
					max_length = defaultlength
				),

				'image': self.EditItem(
					name = 'Image URL',
					placeholder = 'Paste your image URL here...',
					value = poll['image'],
					required = False
				),
			} | {f'opt_{n}': opt(n, n in [1, 2]) for n in range(1, 8 + 1)}

			view = self.EditView(
				items = items,
				modal = self.EditModal,
				groups = groups,
				title = f"Create Poll"
			)

			embedtxt = {
				'title': f"Creating Poll",
				'description': "`Tag`, `Show Question`, `Show Options`, and `Show Voting` can only be set via the slash command parameters. These can also be edited later with `/polls edit`."
			}

			editmodalembed = self.editmodalembed
			async def update_message(self):
				embed = editmodalembed(self.groups, self.items, **embedtxt)
				await self.msg.edit(embed=embed)

			view.update_message = update_message


			msg = await interaction.followup.send(embed=editmodalembed(groups, items, **embedtxt), view=view)
			view.msg = msg

			await view.wait()
			await msg.edit(view=view)


			interaction = view.interaction
			await interaction.response.defer()

			if not view.status:
				return await msg.edit(content = "Cancelled.")

			final = {k: v.value for k, v in view.items.items()}
			final['choices'] = []
			for n in range(1, 8 + 1):
				x = final.pop(f'opt_{n}')
				if x is not None:
					final['choices'].append(x)

			for k, v in final.items():
				poll[k] = v

			interaction = view.interaction

		if len(poll['question']) > self.maxqlength:
			return await interaction.followup.send_message(f"Question is too long! Must be less than {self.maxqlength} characters.")

		await self.bot.db.execute(f'''
				INSERT INTO polls
					({", ".join(poll.keys())})
				VALUES
					({", ".join(f"${i}" for i in range(1, len(poll) + 1))})
			''',
			*poll.values()
		)

		poll = await self.fetchpoll(poll_id)
		embed = await self.pollinfoembed(poll)

		await interaction.followup.send(f"Created new poll question: \"{poll['question']}\"", embed = embed)

	@pollcreate.autocomplete("tag")
	async def pollcreate_autocomplete_tag(self, interaction: discord.Interaction, current: str):
		return await self.autocomplete_tag(interaction, current)



	@pollsgroup.command(name="delete")
	@poll_manager_only()
	@valid_guild_only()
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

			findtag = lambda x: next(i for i in tags if i['id'] == x['tag'])

			recreate = ["/polls create", f"question: {poll['question']}"]
			recreate += [f"opt_{i}: {c}" for c, i in zip(poll['choices'], range(1, len(poll['choices']) + 1))]
			if poll['description']: recreate.append(f"question: {poll['description']}")
			if poll['thread_question']: recreate.append(f"thread_question: {poll['thread_question']}")
			if poll['image']: recreate.append(f"image: {poll['image']}")
			if poll['tag']: recreate.append(f"tag: {self.findtag(poll['tag']).name}")
			if poll['show_question'] is not None: recreate.append(f"show_question: {poll['show_question']}")
			if poll['show_options'] is not None: recreate.append(f"show_options: {poll['show_options']}")
			if poll['show_voting'] is not None: recreate.append(f"show_voting: {poll['show_voting']}")
			recreatemsg = ' '.join(recreate)

			await msg.edit(content = f"Deleted the poll question.\n\nTo recreate this poll, type:\n`{recreatemsg}", view = view)
		else:
			await msg.edit(content = "Cancelled.", view = view)

	@polldelete.autocomplete("poll_id")
	async def polldelete_autocomplete_poll_id(self, interaction: discord.Interaction, current: int):
		return await self.autocomplete_searchbypollid(interaction, current)



	@pollsgroup.command(name="edit")
	@poll_manager_only()
	@valid_guild_only()
	@app_commands.describe(
		poll_id = "5-digit ID of the poll to edit.",
		question = "Main Poll Question to ask.",
		description = "Additional notes/description about the question.",
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
			image: Attachment = None,
			tag: str = None,
			opt_1: str = None, opt_2: str = None, opt_3: str = None, opt_4: str = None, opt_5: str = None, opt_6: str = None, opt_7: str = None, opt_8: str = None,
			show_question: bool = None, show_options: bool = None, show_voting: bool = None
		):
		"""Edits a poll question. Type '-clear' to clear the current value. You must have a question and at least two options. Leave values empty to keep them the same."""

		await interaction.response.defer()

		poll = await self.fetchpoll(poll_id)

		if not poll or not await self.hasmanagerpermsbyuserandids(interaction.user, poll['guild_id'], interaction.channel_id):
			return await interaction.followup.send(f"Couldn't find a poll with the ID `{poll_id}`.")
		oldpoll = poll

		if poll['published'] and tag:
			return await interaction.followup.send("You can't edit tags once the poll's been published!")

		if tag:
			guild_id = await self.fetchguildid(interaction)
			tag = await self.validtag(tag, lambda x: x['guild_id'] == guild_id)
			if tag is None:
				return await interaction.followup.send("Please select an available tag.")
			else: tag = tag['id']


		if all(i is None for i in [question, description, thread_question, image, opt_1, opt_2, opt_3, opt_4, opt_5, opt_6, opt_7, opt_8]):

			groups = {
				'Edit info': ['question', 'description', 'thread_question', 'image'],
				'Edit options (1-4)': [f'opt_{i}' for i in range(1, 4 + 1)],
				'Edit options (5-8)': [f'opt_{i}' for i in range(5, 8 + 1)]
			}

			opt = lambda n, req: self.EditItem(
				name = f"Option #{n}",
				placeholder = f'Type option #{n} here...',
				value = poll['choices'][n - 1] if n <= len(poll['choices']) else None,
				style = discord.TextStyle.long,
				required = req,
				max_length = self.maxqlength
				)

			defaultlength = 500
			items = {
				'question': self.EditItem(
					name = 'Question',
					placeholder = 'Type your question here...',
					value = poll['question'],
					style = discord.TextStyle.long,
					max_length = self.maxqlength
				),

				'description': self.EditItem(
					name = 'Description',
					placeholder = 'Type your description here...',
					value = poll['description'],
					style = discord.TextStyle.long,
					required = False,
					max_length = defaultlength
				),

				'thread_question': self.EditItem(
					name = 'Thread Question',
					placeholder = 'Type your thread question here...',
					value = poll['thread_question'],
					style = discord.TextStyle.long,
					required = False,
					max_length = defaultlength
				),

				'image': self.EditItem(
					name = 'Image URL',
					placeholder = 'Paste your image URL here...',
					value = poll['image'],
					required = False
				),
			} | {f'opt_{n}': opt(n, n in [1, 2]) for n in range(1, 8 + 1)}

			view = self.EditView(
				items = items,
				modal = self.EditModal,
				groups = groups,
				title = f"Edit Poll ({poll['id']})"
			)

			embedtxt = {
				'title': f"Editing Poll {poll['id']}",
				'description': "`Tag`, `Show Question`, `Show Options`, and `Show Voting` can only be set via the slash command parameters. Click Confirm if you're only editing those parameters."
			}

			editmodalembed = self.editmodalembed
			async def update_message(self):
				embed = editmodalembed(self.groups, self.items, **embedtxt)
				await self.msg.edit(embed=embed)

			view.update_message = update_message


			msg = await interaction.followup.send(embed=editmodalembed(groups, items, **embedtxt), view=view)
			view.msg = msg

			await view.wait()
			await msg.edit(view=view)


			interaction = view.interaction
			await interaction.response.defer()

			if not view.status:
				return await msg.edit(content = "Cancelled.")

			final = {k: v.value for k, v in view.items.items()}
			final['choices'] = []
			for n in range(1, 8 + 1):
				x = final.pop(f'opt_{n}')
				if x is not None:
					final['choices'].append(x)

			for k, v in {'tag': tag, 'show_question': show_question, 'show_options': show_options, 'show_voting': show_voting}.items():
				if v is not None:
					final[k] = v

			txt = [f"{k} = ${i}" for k, i in zip(final.keys(), list(range(2, len(final) + 2)))]

			await self.bot.db.execute(f"UPDATE polls SET {', '.join(txt)} WHERE id = $1", poll_id, *final.values())


		else:
			clearvalue = "-clear"

			if image and image.content_type.split('/')[0] == 'image':
				image = image.url

			if question and len(question) > self.maxqlength:
				return await interaction.followup.send_message(f"Question is too long! Must be less than {self.maxqlength} characters.")

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

			if question is not None:
				append("question", question)
			if choices is not None:
				append("choices", choices)
			if description is not None:
				append("description", clear(description))
			if thread_question is not None:
				append("thread_question", clear(thread_question))
			if image is not None:
				append("image", clear(image))
			if tag is not None:
				append("tag", clear(tag))
			if show_question is not None:
				append("show_question", show_question)
			if show_options is not None:
				append("show_options", show_options)
			if show_voting is not None:
				append("show_voting", show_voting)

			await update(names, *values)



		newpoll = await self.fetchpoll(poll_id)

		guild = await self.fetchguildinfo(newpoll['guild_id'])
		tag = await self.fetchtag(newpoll['tag'])

		oldembed = await self.pollinfoembed(oldpoll, guild=guild, tag=tag)
		newembed = await self.pollinfoembed(newpoll, guild=guild, tag=tag)

		oldembed.title = f"[OLD] {oldembed.title}"
		newembed.title = f"[NEW] {newembed.title}"

		if poll['published']:
			await self.updatepollmessage(newpoll)

		await interaction.followup.send(f"Edited poll `{poll_id}`", embeds = [oldembed, newembed])

	@polledit.autocomplete("poll_id")
	async def polledit_autocomplete_poll_id(self, interaction: discord.Interaction, current: int):
		results = await self.autocomplete_searchbypollid(interaction, current, returnresults = True)
		results = [i for i in results if not i['published'] or (i['published'] and i['active'])]

		results.sort(key = lambda x: x['published'])

		choices = [app_commands.Choice(name = self.truncate(f"[{i['id']}] {i['question']}", f"{'{published}' if i['published'] else ''}"), value = i['id']) for i in results[:25]]
		return choices

	@polledit.autocomplete("tag")
	async def polledit_autocomplete_tag(self, interaction: discord.Interaction, current: str):
		return await self.autocomplete_tag(interaction, current, clear = "-clear")



	@pollsgroup.command(name="schedule")
	@poll_manager_only()
	@valid_guild_only()
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

		current = discord.utils.utcnow()

		if poll['published']:
			if schedule_time:
				return await interaction.followup.send(f"This poll has already been published, therefore the start time cannot be rescheduled.")
			else:
				# schedule_time = poll['time'].timestamp()
				schedule_time = current.timestamp()



		if not schedule_time and not poll['published']:
			if poll['time']:
				schedule_time = poll['time'].timestamp()

		if clearschedule:
			schedule_time = None
			scheduled = None

		if schedule_time:
			scheduled = datetime.datetime.fromtimestamp(schedule_time, datetime.timezone.utc)

			if end_time:
				end = datetime.datetime.fromtimestamp(end_time, datetime.timezone.utc)
				duration = end_time - scheduled.timestamp()

				if (end_time - schedule_time) < 0:
					return await interaction.followup.send(f"You're trying to end the poll before it starts! (Starting <t:{int(schedule_time)}:F> but ending <t:{int(end.timestamp())}:F>")
				elif (end_time - current.timestamp()) < 0:
					return await interaction.followup.send(f"You're trying to end the poll in the past! <t:{int(end_time)}:F>, <t:{int(end_time)}:R>")


			if (scheduled - current).total_seconds() < 0:
				return await interaction.followup.send(f"You're trying to schedule a message in the past! <t:{int(schedule_time)}:F>, <t:{int(schedule_time)}:R>")

		else:
			if end_time:
				return await interaction.followup.send("You can't set an end time without a start time!")

		if not poll['published'] and (schedule_time != poll['time'] or clearschedule):
			await self.bot.db.execute("UPDATE polls SET time = $1 WHERE id = $2", scheduled, poll_id)

			if poll['time']:
				if not clearschedule:
					await self.schedule_starts(timestamps = [schedule_time, poll['time'].timestamp()])
				else:
					await self.schedule_starts(timestamps = [poll['time'].timestamp()])
			elif not clearschedule:
				await self.schedule_starts(timestamps = [schedule_time])

		if duration:
			durationtimedelta = datetime.timedelta(seconds=duration)
			if poll['published']:
				durationtimedelta = durationtimedelta + (discord.utils.utcnow() - poll['time'])
			if duration == -1: durationtimedelta = None
			await self.bot.db.execute("UPDATE polls SET duration = $1 WHERE id = $2", durationtimedelta, poll_id)

			await self.schedule_ends(poll_ids = [poll_id])


		poll = await self.fetchpoll(poll_id)

		embed = discord.Embed(title = "Scheduled Poll", description = f"{poll['question']}", colour = await self.fetchcolourbyid(poll['guild_id'], poll['tag']), timestamp = discord.utils.utcnow())
		embed.set_footer(text = f"ID: {poll['id']}" + f'''{f" (#{poll['num']})" if poll['num'] else ""}''')
		embed.add_field(name = "Start time", value = f"<t:{int(poll['time'].timestamp())}:F>\n`{int(poll['time'].timestamp())}`" if poll['time'] else "No time scheduled.")
		embed.add_field(name = "End time", value = f"<t:{int((poll['time']+poll['duration']).timestamp())}:F> - lasts {self.strfduration(poll['duration'])}\n`{int(poll['duration'].total_seconds())}`" if poll['time'] and poll['duration'] else f"Lasts {poll['duration']}\n`{int(poll['duration'].total_seconds())}`" if poll['duration'] else "No end time scheduled.")

		return await interaction.followup.send(embed=embed)

	@pollschedule.autocomplete("poll_id")
	async def pollschedule_autocomplete_poll_id(self, interaction: discord.Interaction, current: int):
		results = await self.autocomplete_searchbypollid(interaction, current, returnresults = True)
		results = [i for i in results if not i['published'] or (i['published'] and i['active'])]

		results.sort(key = lambda x: x['time'].timestamp() if x['time'] is not None else -1)
		results.sort(key = lambda x: x['published'])

		choices = [app_commands.Choice(name = self.truncate(f"[{i['id']}] {i['question']}", f"{'{published}' if i['published'] else ('{scheduled}' if i['time'] else '')}"), value = i['id']) for i in results[:25]]
		return choices

	@pollschedule.autocomplete("duration")
	async def pollschedule_autocomplete_duration(self, interaction: discord.Interaction, current: float):
		return await self.autocomplete_duration(interaction, current, clear = -1)

	@pollschedule.autocomplete("schedule_time")
	async def pollschedule_autocomplete_schedule_time(self, interaction: discord.Interaction, current: int):
		choices = []
		if current.isdigit() and int(current) == -1 or not current:
			choices += [app_commands.Choice(name = f"Clear scheduled time.", value = -1)]
		timestamp = TimeCog.strtodatetime(TimeCog, current)
		choices += [app_commands.Choice(name = self.strf(t), value = int(t.timestamp())) for t in timestamp]
		return choices[:25]



	@pollsgroup.command(name="start")
	@poll_manager_only()
	@valid_guild_only()
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


		current = discord.utils.utcnow()
		end_time = duration if duration and duration >= current.timestamp() else None
		if end_time:
			end = datetime.datetime.fromtimestamp(end_time, datetime.timezone.utc)
			duration = end_time - current.timestamp()

			if duration < 0:
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
		return await self.autocomplete_duration(interaction, current)



	@pollsgroup.command(name="end")
	@poll_manager_only()
	@valid_guild_only()
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
	@valid_guild_only()
	@app_commands.describe(
		poll_id = "ID (5-digit or #) of the poll to search for.",
		keyword = "Keyword to search for. Searches the question and thread question. Case-insensitive.",
		sort = "Order to list results.",
		tag = "Tag to filter results by.",
		active = "List active or inactive questions only.",
		published = "List published or unpublished questions only. Unpublished polls are only visible to Poll Managers.",
		showextrainfo = "Shows all settings for the poll. Only useable by Poll Managers."
		)
	@app_commands.choices(sort=choices['sort'])
	async def pollsearch(self, interaction: discord.Interaction,
			poll_id: int = None,
			keyword: str = None,
			sort: Choice[str] = Sort.poll_id.name,
			tag: str = None,
			active: bool = None,
			published: bool = None,
			showextrainfo: bool = False,
		):
		"""Searches poll questions. Search by poll ID, or by keyword, and filter by tag."""

		await interaction.response.defer()

		sort = self.Sort.__members__[sort.value if not isinstance(sort, str) else sort]


		if poll_id:
			poll = await self.fetchpoll(poll_id)

			if not poll: poll = await self.bot.db.fetchrow("SELECT * FROM polls WHERE num = $1", poll_id)

			managerperms = await self.hasmanagerperms(interaction)

			if not poll or (not poll['published'] and not managerperms and await self.canview(poll, interaction.guild_id)):
				return await interaction.followup.send(f"Couldn't find a poll with the ID `{poll_id}`.")

			if showextrainfo:
				if not managerperms:
					showextrainfo = False

			if not showextrainfo:
				embed = await self.pollquestionembed(poll, interaction = interaction, showextra = True)
			else:
				embed = await self.pollinfoembed(poll)

			await interaction.followup.send(embed=embed)
			return

		else:
			notag = "-1"
			# if tag:
			# 	if (not tag.isdigit() or not await self.fetchtag(int(tag))) and not tag == notag:
			# 		return await interaction.followup.send("Please select an available tag.")
			# 	else:
			# 		tag = int(tag)
			if tag and tag != notag:
				tag = await self.validtag(tag)
				if tag is None:
					return await interaction.followup.send("Please select an available tag.")
				else: tag = tag['id']

			queries = []
			values = []
			text = []
			# keyword, tag, published
			if keyword:
				# queries.append("(question ~* ${} OR thread_question ~* ${} OR ${} ~! ANY(choices))")
				# values += [keyword, keyword, keyword]
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
				if not queries: polls = await self.bot.db.fetch("SELECT * FROM polls")
				else:
					polls = await self.bot.db.fetch(f"SELECT * FROM polls WHERE {' AND '.join(queries).format(*list(range(1, len(values) + 1)))}", *values)
				if keyword:
					polls = self.keywordsearch(keyword, polls)
			except asyncpg.exceptions.InvalidRegularExpressionError:
				return await interaction.followup.send(f"Your keyword input `{keyword}` seems to have failed. Please make sure to only search using alphanumeric characters.")

			polls = [i for i in polls if await self.canview(i, interaction.guild_id)]
			if not await self.hasmanagerperms(interaction):
				polls = [i for i in polls if i['published']]
			polls = self.sortpolls(polls, sort)

			if not polls:
				return await interaction.followup.send("No results found!")	

			msg = await interaction.followup.send("Searching...")

			class PollSearchPaginator(BaseButtonPaginator):
				text = None
				colour = None

				async def format_page(self, entries):
					embed = discord.Embed(title = "Polls Search", description = "\n".join(self.text), colour = self.colour, timestamp=discord.utils.utcnow())
					results = [f"""`{i['id']}`{f' (`#{i["num"]}`)' if i['num'] else ''}: {i['question']}{' (<t:'+str(int(i['time'].timestamp()))+':d>)' if i['time'] else ''}""" for i in entries]
					embed.add_field(name = "Results", value = '\n'.join(results))
					
					embed.set_footer(text=f'Page {self.current_page}/{self.total_pages} ({len(self.entries)} results)')
					
					return embed

			PollSearchPaginator.text = text
			PollSearchPaginator.colour = await self.fetchcolourbyid(await self.fetchguildid(interaction), None)

			paginator = await PollSearchPaginator.start(msg, entries=polls, per_page=10)
			await paginator.wait()

			for child in paginator.children:
				child.disabled = True
			paginator.stop()

			return await paginator.msg.edit(content="Timed out.", view=paginator)

	@pollsearch.autocomplete("poll_id")
	async def pollsearch_autocomplete_poll_id(self, interaction: discord.Interaction, current: int):
		return await self.autocomplete_searchbypollid(interaction, current, crosspost = True)

	@pollsearch.autocomplete("tag")
	async def pollsearch_autocomplete_tag(self, interaction: discord.Interaction, current: str):
		return await self.autocomplete_tag(interaction, current, clear = "-1", clearname = "No tag.")



	@pollsgroup.command(name="me")
	@valid_guild_only()
	@app_commands.describe(
		show_unvoted = "Shows all the polls you haven't voted on yet!",
		user = "Views history of a specified user.",
		poll_id = "Shows your vote on a specific poll."
		)
	async def pollsme(self, interaction: discord.Interaction, show_unvoted: bool = False, user: discord.User = None, poll_id: int = None):
		"""Shows your poll voting history"""

		await interaction.response.defer()

		msg = await interaction.followup.send("Searching...")

		op = True
		if user is None: user = interaction.user
		else: op = False

		votes = await self.bot.db.fetchrow("SELECT * FROM pollsvotes WHERE user_id = $1", user.id)
		if not votes:
			await self.bot.db.execute("INSERT INTO pollsvotes (user_id) VALUES ($1)", user.id)
			votes = await self.bot.db.fetchrow("SELECT * FROM pollsvotes WHERE user_id = $1", user.id)

		votes = {int(k): v for k, v in votes.items() if k != 'user_id'}

		if poll_id is None:
			voted = {'voted': [], 'unvoted': []}
			for k, v in votes.items():
				if v is not None:
					voted['voted'].append(k)
				else:
					voted['unvoted'].append(k)

			if not show_unvoted:
				poll_ids = voted['voted']

				polls = await self.bot.db.fetch("SELECT * FROM polls WHERE id = ANY($1::integer[])", poll_ids)
				polls = [i for i in polls if await self.canview(i, interaction.guild_id)]
				polls = self.sortpolls(polls, self.Sort.newest)

				entries = [[i, votes[i['id']]] for i in polls]

				if not entries:
					embed = discord.Embed(title = f"{user.name}'s Polls", colour = await self.fetchcolourbyid(await self.fetchguildid(interaction), None), timestamp = discord.utils.utcnow())
					embed.add_field(name = "No votes", value = f"{'''You haven't''' if op else f'''{user.name} hasn't'''} voted for anything yet!" + (f"Use `/pollsme show_unvoted: true` to see all the polls you're able to vote on!" if op else ''))
					embed.set_footer(text = f"Page 0/0 (0 results) | {user.id}")
					return await msg.edit(embed=embed)

				class PollsMePaginator(BaseButtonPaginator):
					async def format_page(self, entries):
						embed = discord.Embed(title = f"{self.user.name}'s Polls", colour = self.colour, timestamp = discord.utils.utcnow())
						for p, v in entries:
							embed.add_field(
								name = f"{p['id']}{(' (#' + str(p['num']) + ')') if p['num'] else ''}: {p['question']}",
								value = f"{'You' if self.op else self.user.name} voted: {self.client.choiceformat(v)} " + (f"*{p['choices'][v]}*" if p['show_options'] else ''),
								inline = False
								)
						embed.set_footer(text = f"Page {self.current_page}/{self.total_pages} ({len(self.entries)} results) | {self.user.id}")
						return embed


			else:
				poll_ids = voted['unvoted']

				polls = await self.bot.db.fetch("SELECT * FROM polls WHERE id = ANY($1::integer[])", poll_ids)
				polls = [i for i in polls if i['active'] and await self.canview(i, interaction.guild_id)]
				polls = self.sortpolls(polls, self.Sort.oldest)

				entries = polls

				if not entries:
					embed = discord.Embed(title = f"{user.name}'s Polls", colour = await self.fetchcolourbyid(await self.fetchguildid(interaction), None), timestamp = discord.utils.utcnow())
					embed.add_field(name = "All voted for!", value = f"{'''You've''' if op else f'''{user.name}'s'''} voted on all active polls!")
					embed.set_footer(text = f"Page 0/0 (0 results) | {user.id}")
					return await msg.edit(embed=embed)

				class PollsMePaginator(BaseButtonPaginator):
					async def format_page(self, entries):
						embed = discord.Embed(title = f"{self.user.name}'s Polls", colour = self.colour, timestamp = discord.utils.utcnow())
						for p in entries:
							guild = await self.client.fetchguildinfo(p['guild_id'])
							tag = await self.client.fetchtag(p['tag'])
							if interaction.guild_id == p['guild_id']:
								message = await self.client.bot.get_channel(self.client.fetchchannelid(guild, tag)).fetch_message(p['message_id'])
							else:
								i = tag['crosspost_servers'].index(interaction.guild_id)
								message = await self.client.bot.get_channel(tag['crosspost_channels'][i]).fetch_message(p['crosspost_message_ids'][i])
							embed.add_field(
								name = f"{p['id']}{(' (#' + str(p['num']) + ')') if p['num'] else ''}: {p['question']}",
								value = f"Vote [here](<{message.jump_url}>)!",
								inline = False
								)
						embed.set_footer(text = f"Page {self.current_page}/{self.total_pages} ({len(self.entries)} results) | {self.user.id}")
						return embed



			PollsMePaginator.user = user
			PollsMePaginator.colour = await self.fetchcolourbyid(await self.fetchguildid(interaction), None)
			PollsMePaginator.op = op
			PollsMePaginator.interaction = interaction
			PollsMePaginator.client = self

			paginator = await PollsMePaginator.start(msg, entries=entries, per_page=15)

			await paginator.wait()

			for child in paginator.children:
				child.disabled = True
			paginator.stop()

			return await paginator.msg.edit(content="Timed out.", view=paginator)

		else:
			poll = await self.fetchpoll(poll_id)
			if not poll:
				return await interaction.followup.send(f"Couldn't find a poll with the ID `{poll_id}`.")


			embed = discord.Embed(title = f"{user.name}'s Polls", colour = await self.fetchcolourbyid(await self.fetchguildid(interaction), None), timestamp = discord.utils.utcnow())

			choice = votes[int(poll_id)]
			if choice is not None:
				value = f"{'You' if op else user.name} voted: {self.choiceformat(choice)} " + (f"*{poll['choices'][choice]}*" if poll['show_options'] else '')
			else:
				value = f"{'''You haven't''' if op else f'''{user.name} hasn't'''} voted on this poll yet!"

			embed.add_field(
				name = f"{poll['id']}{(' (#' + str(poll['num']) + ')') if poll['num'] else ''}: {poll['question']}",
				value = value,
				inline = False
				)

			embed.set_footer(text = str(user.id))

			await msg.edit(content = '', embed=embed)

	@pollsme.autocomplete("poll_id")
	async def pollsme_autocomplete_poll_id(self, interaction: discord.Interaction, current: int):
		return await self.autocomplete_searchbypollid(interaction, current, published = True, crosspost = True)



	@pollsadmingroup.command(name="sync")
	@app_commands.describe(all_messages = "Update all messages, including inactive polls.")
	@owner_only()
	async def polladminsync(self, interaction: discord.Interaction, all_messages: bool = False):
		"""Force sync all automated poll routines"""
		await interaction.response.defer()

		print("~~~ Running SYNC ~~~")



		tasks = {k: {"txt": v, "status": False} for k, v in {
			"start_schedule": "Start schedules",
			"end_schedule": "End schedules",
			"update_votes": "Update votes",
			"update_msg": "Update poll messages",
			"update_selfassign": "Update self-assign buttons"
			}.items()}

		async def update():
			await msg.edit(content = generate_txt())

		def generate_txt():
			txt = ["Syncing..."]
			x = {
				True: "x",
				False: "-",
				None: "~"
			}
			for t in tasks.values():
				txt.append(f"`{x[t['status']]}` {t['txt']}")
			return '\n'.join(txt)

		def start(key):
			tasks[key]['status'] = None
		def end(key):
			tasks[key]['status'] = True


		async def task(function, key):
			start(key)
			await update()

			await function()

			end(key)
			await update()


		msg = await interaction.followup.send(generate_txt())



		refreshpolls = lambda: self.searchpollsbykeyword("")
		polls = await refreshpolls()


		await task(self.schedule_starts, "start_schedule")

		await task(self.schedule_ends, "end_schedule")


		async def update_votes():
			columns = await self.bot.db.fetch("SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' and table_name = 'pollsvotes' and column_name != 'user_id'")
			columns = [i['column_name'] for i in columns]

			polls = await self.bot.db.fetch("SELECT * FROM polls")
			pollids = [i['id'] for i in polls if i['published']]

			for c in columns:
				if int(c) not in pollids:
					await self.bot.db.execute("ALTER TABLE pollsvotes DROP COLUMN \"{}\"".format(c))

			for pid in pollids:
				if str(pid) not in columns:
					await self.bot.db.execute("ALTER TABLE pollsvotes ADD \"{}\" integer".format(str(pid)))

			votes = await self.bot.db.fetch("SELECT * FROM pollsvotes")
			for poll in polls:
				if not poll['active']: continue
				v = [i[str(poll['id'])] for i in votes]
				total = [v.count(i) for i in range(len(poll['choices']))]

				if total != poll['votes']:
					await self.bot.db.execute("UPDATE polls SET votes = $2 WHERE id = $1", poll['id'], total)
		await task(update_votes, "update_votes")


		async def update_msg():
			pollfilter = 'published' if all_messages else 'active'
			filtered = [i for i in polls if i[pollfilter]]
			filtered.sort(key = lambda x: discord.utils.utcnow() - x['time'])
			filtered.sort(key = lambda x: not x['active'])
			for poll in filtered:
				await self.do_updatepollmessage(poll, force = poll['active'])
		await task(update_msg, "update_msg")


		async def update_selfassign():
			await self.on_startup_selfassign()
		await task(update_selfassign, "update_selfassign")


		# polls = await refreshpolls()


		print("~~~ End SYNC ~~~")



	@pollsadmintaggroup.command(name="create")
	@app_commands.describe(
		name = "Name of the tag.",
		channel = "Main channel that the tag sends polls to. Cannot be edited.",
		num = "Starting value of incrementally labelled polls.",
		colour = "Colour of the poll messages. Must be a hex code (e.g. #7298da)",
		end_message = "Message to send after each poll. Required for role pings and self-assignment. Leave empty to ignore.",
		ping_role = "Role to ping and self-assign after each poll. More roles can be added with /pollsadmin tag pingrole.",
		do_ping = "Ping the role after each poll.",
		do_role_assign = "Let users self-assign the ping role with a button.",
		recycle_end_message = "Delete old end-messages when new end-message is sent."
		)
	@owner_only()
	async def pollsadmintagcreate(self, interaction: discord.Interaction,
		name: str,
		channel: discord.TextChannel,
		num: int = None,
		colour: str = None,
		end_message: str = None,
		ping_role: discord.Role = None,
		do_ping: bool = False,
		do_role_assign: bool = False,
		recycle_end_message: bool = True,
		):
		"""Creates a new tag."""

		await interaction.response.defer()

		if colour:
			try:
				colour = colour.strip("#")
				colour = int(colour, 16)
				if not (0 <= colour <= 16777215):
					raise ValueError
			except ValueError:
				return await interaction.followup.send("Please provide a valid colour hex code!")

		if ping_role and not end_message:
			return await interaction.followup.send("You must set an end-message for role pings and self-assignment to function.")

		while True:
			tag_id = random.randint(100, 999)
			if not await self.bot.db.fetchrow("SELECT id FROM polls WHERE id = $1", tag_id):
				break

		insert = {
			'id': tag_id,
			'name': name,
			'guild_id': interaction.guild_id,
			'channel_id': channel.id,
			'crosspost_channels': [],
			'crosspost_servers': [],
			'num': num,
			'colour': colour,
			'end_message': end_message,
			'end_message_latest_ids': [],
			'end_message_replace': recycle_end_message,
			'end_message_role_ids': [ping_role.id] if ping_role else [],
			'end_message_ping': do_ping,
			'end_message_self_assign': do_role_assign,
		}


		embed = discord.Embed(
			title = name,
			description = '\n'.join([
				f"{channel.mention} in *{interaction.guild.name}*",
				f"Counting from **{num}**" if num else f"Not counting polls.",
				f"Colour: #{hex(colour).strip('0x').upper()}" if colour else f"No colour.",
				f"End-message:\n> {end_message}" if end_message else f"No end-message.",
				"",
				f"Recycle end-message: {recycle_end_message}",
				f"Pinging role: {do_ping}",
				f"Self-assigning role: {do_role_assign}"
				]),
			timestamp = discord.utils.utcnow(),
			colour = colour
			)

		view = self.Confirm()

		msg = await interaction.followup.send(
			f"Do you want to create this tag? **It cannot be deleted, and you cannot change the default channel or guild once set.**",
			embed = embed,
			view = view
			)

		await view.wait()

		for child in view.children:
			child.disabled = True

		if view.value is None:
			await msg.edit(content = "Timed out.", view = view)
		elif view.value:
			await self.bot.db.execute(f'''
					INSERT INTO pollstags
						({", ".join(insert.keys())})
					VALUES
						({", ".join(f"${i}" for i in range(1, len(insert) + 1))})
				''',
				*insert.values()
			)

			await msg.edit(content = "Successfully created new tag.", view = None)


		else:
			await msg.edit(content = "Cancelled.", view = view)



	@pollsadmintaggroup.command(name="edit")
	@app_commands.describe(
		do_ping = "Ping the role after each poll.",
		do_role_assign = "Let users self-assign the ping role with a button.",
		recycle_end_message = "Delete old end-messages when new end-message is sent."
		)
	@owner_only()
	async def pollsadmintagedit(self, interaction: discord.Interaction,
		tag: str,
		do_ping: bool = None,
		do_role_assign: bool = None,
		recycle_end_message: bool = None,
		):
		"""Edits a tag."""

		await interaction.response.defer()

		tag = await self.validtag(tag)
		if tag is None:
			return await interaction.followup.send("Please select an available tag.")

		groups = {'Edit tag': ['name', 'end_message', 'colour', 'num']}

		items = {
			'name': self.EditItem(
				name = 'Tag Name',
				placeholder = 'Type your tag name here...',
				value = tag['name'],
				max_length = 100
			),

			'end_message': self.EditItem(
				name = 'End Message',
				placeholder = 'Type your end message here... empty to ignore',
				value = tag['end_message'],
				style = discord.TextStyle.long,
				max_length = 500,
				required = False
			),

			'colour': self.EditItem(
				name = 'Colour Hex Code',
				placeholder = 'Paste your colour hex code here... e.g. 7289da',
				value = hex(tag['colour']).strip('0x').upper(),
				max_length = 6,
				required = False
			),

			'num': self.EditItem(
				name = 'Next Poll Number',
				placeholder = 'Type your poll number here... empty to ignore',
				value = tag['num'],
				required = False
			),
		}

		view = self.EditView(
			items = items,
			modal = self.EditModal,
			groups = groups,
			title = f"Edit Tag ({tag['id']})"
		)

		embedtxt = {
			'title': f"Editing Tag {tag['id']}",
			'description': "`Do Ping`, `Do Role Assign`, and `Recycle End Message` can only be set via the slash command parameters. Click Confirm if you're only editing those parameters."
		}

		editmodalembed = self.editmodalembed

		async def update_message(self):
			embed = editmodalembed(self.groups, self.items, **embedtxt)
			await self.msg.edit(embed=embed)

		view.update_message = update_message

		view.add_check(lambda x: x['num'].value is None or (x['num'].value.isdigit() and int(x['num'].value) >= 0), "Next Poll Number must be a positive integer")

		def colour_check(x):
			colour = x['colour'].value
			if colour is None: return True
			try:
				colour = colour.strip("#")
				colour = int(colour, 16)
				if not (0 <= colour <= 16777215):
					raise ValueError
			except ValueError:
				return False
			else:
				return True
		view.add_check(colour_check, "Colour must be a valid hex code between 000000 and FFFFFF")



		msg = await interaction.followup.send(embed=editmodalembed(groups, items, **embedtxt), view=view)
		view.msg = msg

		await view.wait()
		await msg.edit(view=view)


		interaction = view.interaction
		await interaction.response.defer()

		if not view.status:
			return await msg.edit(content = "Cancelled.")

		view.items['colour'].value = int(view.items['colour'].value, 16) if view.items['colour'].value else None
		view.items['num'].value = int(view.items['num'].value) if view.items['num'].value else None
		final = {k: v.value for k, v in view.items.items()}

		for k, v in {'end_message_ping': do_ping, 'end_message_self_assign': do_role_assign, 'end_message_replace': recycle_end_message}.items():
			if v is not None:
				final[k] = v

		txt = [f"{k} = ${i}" for k, i in zip(final.keys(), list(range(2, len(final) + 2)))]

		await self.bot.db.execute(f"UPDATE pollstags SET {', '.join(txt)} WHERE id = $1", tag['id'], *final.values())

		oldtag = tag
		newtag = await self.fetchtag(tag['id'])

		embed = lambda x: discord.Embed(
			title = x['name'],
			description = '\n'.join([
				f"Counting from **{x['num']}**" if x['num'] else f"Not counting polls.",
				f"Colour: #{hex(x['colour']).strip('0x').upper()}" if x['colour'] else f"No colour.",
				f"End-message:\n> {x['end_message']}" if x['end_message'] else f"No end-message.",
				"",
				f"Recycle end-message: {x['end_message_replace']}",
				f"Pinging role: {x['end_message_ping']}",
				f"Self-assigning role: {x['end_message_self_assign']}",
				]),
			timestamp = discord.utils.utcnow(),
			colour = x['colour'] if x['colour'] else None
			)

		oldembed = embed(oldtag)
		newembed = embed(newtag)

		oldembed.title = f"[OLD] {oldembed.title}"
		newembed.title = f"[NEW] {newembed.title}"

		await interaction.followup.send(f"Edited tag `{tag['id']}`", embeds = [oldembed, newembed])

	@pollsadmintagedit.autocomplete("tag")
	async def pollsadmintagedit_autocomplete_tag(self, interaction: discord.Interaction, current: str):
		return await self.autocomplete_tag(interaction, current, local = False)



	@pollsadmintaggroup.command(name="pingrole")
	@owner_only()
	async def pollsadmintagpingrole(self, interaction: discord.Interaction, 
		tag: str,
		ping_role: discord.Role
		):
		"""Adds/removes role from tag."""

		await interaction.response.defer()

		tag = await self.validtag(tag)
		if tag is None:
			return await interaction.followup.send("Please select an available tag.")

		roles = tag['end_message_role_ids']

		if ping_role.id in roles:
			roles.remove(ping_role.id)
			txt = ["removed", "from"]
		else:
			roles.append(ping_role.id)
			txt = ["added", "to"]

		await self.bot.db.execute("UPDATE pollstags SET end_message_role_ids = $2 WHERE id = $1", tag['id'], roles)

		await interaction.followup.send(
			f"Successfully **{txt[0]}** {ping_role.mention} {txt[1]} the **{tag['name']}** ({tag['id']}) tag.",
			allowed_mentions = discord.AllowedMentions.none())

	@pollsadmintagpingrole.autocomplete("tag")
	async def pollsadmintagpingrole_autocomplete_tag(self, interaction: discord.Interaction, current: str):
		return await self.autocomplete_tag(interaction, current, local = False)



	@pollsadmincrosspostgroup.command(name="link")
	@app_commands.describe(
		tag="The tag to crosspost from.",
		channel="The channel to crosspost to.")
	@owner_only()
	async def pollsadmincrosspostlink(self, interaction, tag: str, channel: discord.TextChannel):
		"""Links a channel to crossposts from a tag."""

		await interaction.response.defer()

		tag = await self.validtag(tag)
		if tag is None:
			return await interaction.followup.send("Please select an available tag.")

		if channel.id == tag['channel_id']:
			return await interaction.followup.send(f"{channel.mention} is already the host channel!")

		channels = tag['crosspost_channels']
		guilds = tag['crosspost_servers']

		if channel.id in channels:
			return await interaction.followup.send(f"{channel.mention} is already receiving crossposts!")

		channels.append(channel.id)
		guilds.append(channel.guild.id)

		await self.bot.db.execute("UPDATE pollstags SET crosspost_channels = $2, crosspost_servers = $3 WHERE id = $1", tag['id'], channels, guilds)

		await interaction.followup.send(f"Linked {channel.mention} to crossposts from *{tag['name']}* (`{tag['id']}`)")

	@pollsadmincrosspostlink.autocomplete("tag")
	async def pollsadmincrosspostlink_autocomplete_tag(self, interaction: discord.Interaction, current: str):
		return await self.autocomplete_tag(interaction, current, local = False)



	@pollsadmincrosspostgroup.command(name="unlink")
	@app_commands.describe(
		tag="The tag to remove the crosspost from.",
		channel="The channel to remove the crosspost from.")
	@owner_only()
	async def pollsadmincrosspostunlink(self, interaction, tag: str, channel: discord.TextChannel):
		"""Unlinks a channel from crossposts from a tag."""

		await interaction.response.defer()

		tag = await self.validtag(tag)
		if tag is None:
			return await interaction.followup.send("Please select an available tag.")

		if channel.id == tag['channel_id']:
			return await interaction.followup.send(f"{channel.mention} is the host channel!")

		channels = tag['crosspost_channels']
		guilds = tag['crosspost_servers']

		if channel.id not in channels:
			return await interaction.followup.send(f"{channel.mention} already isn't receiving crossposts!")

		index = channels.index(channel.id)
		channels.pop(index)
		guilds.pop(index)

		await self.bot.db.execute("UPDATE pollstags SET crosspost_channels = $2, crosspost_servers = $3 WHERE id = $1", tag['id'], channels, guilds)

		await interaction.followup.send(f"Unlinked {channel.mention} from crossposts from *{tag['name']}* (`{tag['id']}`)")

	@pollsadmincrosspostunlink.autocomplete("tag")
	async def pollsadmincrosspostunlink_autocomplete_tag(self, interaction: discord.Interaction, current: str):
		return await self.autocomplete_tag(interaction, current, local = False)



async def setup(bot):
	await bot.add_cog(PollsCog(bot))