import discord
from discord import *
from discord._types import ClientT
from discord.ext.commands import *
from discord.app_commands import *
from discord.app_commands.tree import _log
from discord.ui import Modal, TextInput as TI


class FunCog(Cog, name="Fun"):
    """Fun commands"""

    def __init__(self, bot):
        self.bot: Bot = bot

        self.bot.tree.on_error = self.on_app_command_error

        self.shrink = str.maketrans(
            "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_",
            "⁰¹²³⁴⁵⁶⁷⁸⁹ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖᵠʳˢᵗᵘᵛʷˣʸᶻᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖᵠʳˢᵗᵘᵛʷˣʸᶻ‾",
        )

    async def on_app_command_error(
        self, interaction: Interaction, error: AppCommandError
    ):
        await interaction.followup.send("Something broke!")
        _log.error(
            "Ignoring exception in command %r", interaction.command.name, exc_info=error
        )

    @app_commands.command(name="shrinktext")
    @app_commands.describe(text="Text to shrink", show="Show shrunk text to everyone")
    async def shrinktext(
        self, interaction: discord.Interaction, text: str, show: bool = False
    ):
        """Shrink your text!"""
        await interaction.response.send_message(
            text.translate(self.shrink), ephemeral=not show
        )

    # fake tweet builder

    def create_twitter_snowflake(self, snowflake: int) -> int:
        timestamp = (snowflake >> 22) + 1420070400000
        internal_worker_id = (snowflake & 0x3E0000) >> 17
        internal_process_id = (snowflake & 0x1F000) >> 12
        increment = snowflake & 0xFFF

        timestamp += 131235425343

        new_snowflake = (
            (timestamp - 1420070400000) << 22
            | internal_worker_id << 17
            | internal_process_id << 12
            | increment
        )

        return new_snowflake

    @app_commands.command(name="fake-tweet")
    @app_commands.describe(
        channel="Channel to send the tweet in",
        troll_link="Link to troll with (optional)",
    )
    @guilds(281648235557421056)
    async def fake_tweet(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        troll_link: str = None,
    ):
        """Create a fake tweet"""
        modal = FunCog.FakeTweetModal()
        await interaction.response.send_modal(modal)
        timeout = await modal.wait()

        if timeout:
            return

        author_name = modal.author_name.value
        author_handle = modal.author_handle.value
        text = modal.text.value
        image = modal.image.value
        snowflake_timestamp = (
            int(modal.timestamp.value) if modal.timestamp.value else None
        )

        snowflake = self.create_twitter_snowflake(snowflake_timestamp or interaction.id)

        timestamp = discord.Object(snowflake_timestamp or interaction.id).created_at

        link_url = f"{author_handle}/status/{snowflake}"
        link = troll_link or "https://twitter.com/" + link_url

        embed = Embed(
            title=f"{author_name} (@{author_handle}) on X",
            url=link,
            color=0x1DA0F2,
            timestamp=timestamp,
            description=text,
        )
        embed.set_footer(
            icon_url="https://abs.twimg.com/icons/apple-touch-icon-192x192.png",
            text="Twitter",
        )
        if image:
            embed.set_image(url=image)

        await channel.send(
            (
                f"<https://twitter.com/>[{link_url}](<{link}>)"
                if troll_link
                else f"<{link}>"
            ),
            embed=embed,
        )

    class FakeTweetModal(Modal):
        def __init__(self):
            super().__init__(title="Create a fake tweet", timeout=300)

            self.author_name = TI(label="Author name", required=True)
            self.author_handle = TI(label="Author handle", required=True)
            self.text = TI(label="Tweet text", required=True, style=TextStyle.long)
            self.image = TI(label="Image URL", required=False)
            self.timestamp = TI(
                label="Message ID to set timestamp (blank for rn)",
                required=False,
            )

            self.add_item(self.author_name)
            self.add_item(self.author_handle)
            self.add_item(self.text)
            self.add_item(self.image)
            self.add_item(self.timestamp)

        async def on_submit(self, interaction: Interaction[ClientT], /) -> None:
            await interaction.response.send_message("Created tweet >:)", ephemeral=True)


async def setup(bot):
    await bot.add_cog(FunCog(bot))
