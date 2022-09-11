import datetime, discord, math
from config import *
from discord import *
from discord.ext import commands
from discord.app_commands import *
from discord.app_commands.tree import _log


"""
- /timestamp generate <written time>
x /timestamp repeat <timestamp>
"""


class TimeCog(discord.ext.commands.Cog, name = "Time"):
	"""Time commands"""

	def __init__(self, bot):
		self.bot = bot

		self.bot.tree.on_error = self.on_app_command_error


	datetosql = lambda self, x: x.strftime('%Y-%m-%d %H:%M:%S')
	strf = lambda self, x: x.strftime('%a, %b %d, %Y ~ %I:%M:%S %p %Z').replace(" 0", " ")
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


	async def on_app_command_error(self, interaction: Interaction, error: AppCommandError):
		await interaction.followup.send("Something broke!")
		_log.error('Ignoring exception in command %r', interaction.command.name, exc_info=error)


	guild_ids = None if global_slashies else [288896937074360321, 1010550869391065169]

	timestampgroup = app_commands.Group(name="timestamp", description="Timestamp creation commands", guild_ids=guild_ids)


	async def autocomplete_timestamp(self, interaction: discord.Interaction, current: int):
		try:
			current = int(current)
		except ValueError:
			return []

		try:
			time = datetime.datetime.fromtimestamp(current, datetime.timezone.utc)
			return [app_commands.Choice(name = f"{self.strf(time)}", value = int(current))]
		except (OSError, OverflowError):
			return []

	async def autocomplete_duration(self, interaction: discord.Interaction, current: int, *, defaults = []):
		try:
			if current != "":
				current = float(current)
		except ValueError:
			return []

		ranges = {
			"seconds": "second",
			"minutes": "minute",
			"hours": "hour",
			"days": "day",
			"weeks": "week"
		}
		times = []

		if current != "":
			for k, v in ranges.items():
				try:
					times.append([datetime.timedelta(**{k: current}), current, v])
				except OverflowError:
					continue
		else:
			for t, n in defaults:
				try:
					times.append([datetime.timedelta(**{n: t}), t, ranges[n]])
				except OverflowError:
					continue

		choices = []
		for t in times:
			secs = int(round(t[0].total_seconds(), 0))
			if 15 <= secs <= 60480000: # Between 15s and 100w
				f = lambda x: x if isinstance(x, int) else (int(x) if x.is_integer() else x)
				choices.append(app_commands.Choice(name = f"{f(t[1])} {t[2]}{self.s(f(t[1]))}", value = int(secs)))
		return choices


	@timestampgroup.command(name="repeat")
	@app_commands.describe(
		starting_timestamp = "Timestamp to build upon.",
		interval = "The length of time between timestamps.",
		amount = "The number of timestamps to generate (including starting timestamp)."
		)
	async def timestamprepeat(self, interaction: discord.Interaction, starting_timestamp: int, interval: int, amount: int, raw: bool = False):
		"""Lists following timestamps at constant intervals."""
		await interaction.response.defer()

		if amount > 100:
			return await interaction.followup.send("Please set an amount less than 100.")

		timestamps = [starting_timestamp + interval * i for i in range(amount)]
		times = [f"<t:{t}:F> `{t}`" for t in timestamps]

		if not raw:
			embed = discord.Embed(
				title = f"Recurring every {self.strfduration(datetime.timedelta(seconds=interval))}",
				description = '\n'.join(times)
				)
			await interaction.followup.send(embed=embed)
		else:
			await interaction.followup.send('\n'.join([str(i) for i in timestamps]))
		

	@timestamprepeat.autocomplete("starting_timestamp")
	async def timestamprepeat_autocomplete_starting_timestamp(self, interaction: discord.Interaction, current: int):
		return await self.autocomplete_timestamp(interaction, current)

	@timestamprepeat.autocomplete("interval")
	async def timestamprepeat_autocomplete_interval(self, interaction: discord.Interaction, current: int):
		return await self.autocomplete_duration(interaction, current,
			defaults = [
				[1, "weeks"],
				[1, "days"],
				[12, "hours"],
				[6, "hours"],
				[1, "hours"],
				[30, "minutes"]
			])



	@timestampgroup.command(name="event")
	async def timestampevent(self, interaction: discord.Interaction, event: str):
		await interaction.response.defer()

		try:
			event = interaction.guild.get_scheduled_event(int(event))
			if event is None:
				raise ValueError
		except ValueError:
			return await interaction.followup.send("Event could not be found in this server.")

		await interaction.followup.send(event)



		



async def setup(bot):
	await bot.add_cog(TimeCog(bot))