import discord
from discord import *
from discord.ext.commands import *
from discord.app_commands import *
from discord.app_commands.tree import _log


class FunCog(Cog, name="Fun"):
    """Fun commands"""

    def __init__(self, bot):
        self.bot: Bot = bot

        self.bot.tree.on_error = self.on_app_command_error

        self.shrink = str.maketrans("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_",
                                    "⁰¹²³⁴⁵⁶⁷⁸⁹ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖᵠʳˢᵗᵘᵛʷˣʸᶻᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖᵠʳˢᵗᵘᵛʷˣʸᶻ‾")

    async def on_app_command_error(self, interaction: Interaction, error: AppCommandError):
        await interaction.followup.send("Something broke!")
        _log.error('Ignoring exception in command %r', interaction.command.name, exc_info=error)

    @app_commands.command(name="shrinktext")
    @app_commands.describe(text="Text to shrink", show="Show shrunk text to everyone")
    async def shrinktext(self, interaction: discord.Interaction, text: str, show: bool = False):
        """Shrink your text!"""
        await interaction.response.send_message(text.translate(self.shrink), ephemeral=not show)


async def setup(bot):
    await bot.add_cog(FunCog(bot))
