import asyncio, discord, re
from discord import *
from discord.app_commands import *
from discord.app_commands.tree import _log
from discord.ext import commands
from config import *

# url_regex = "(https?:\/\/)?([\da-z\.-]+)\.([a-z\.]{2,6})([\/\w \.-]*)"
url_regex = "(https?:\/\/)([\da-z\.-]+)\.([a-z\.]{2,6})([\/\w\.\-\?]*)(#?[\/\w\.\-\&\=\%\?]*)?"


class EmbedCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        self.bot.loop.create_task(self.on_startup_scheduler())

        self.embed_visible = app_commands.ContextMenu(
            name='Embed Links',
            callback=self.embed_links_visible,
        )
        self.bot.tree.add_command(self.embed_visible)

        self.embed_silent = app_commands.ContextMenu(
            name='Embed Links (silent)',
            callback=self.embed_links_silent,
        )
        self.bot.tree.add_command(self.embed_silent)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.embed_visible.name, type=self.embed_visible.type)
        self.bot.tree.remove_command(self.embed_silent.name, type=self.embed_silent.type)

    async def on_startup_scheduler(self):
        await self.bot.wait_until_ready()
        self.bot.add_view(self.CloseView())
        self.bot.add_view(self.VisibleView(self.embed_links))

    class CloseView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(label="X", style=discord.ButtonStyle.red, custom_id="close")
        async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
            link_msg = interaction.message
            embedder_id = int(link_msg.content.split('\n')[1].split(' ')[-1].strip('<@>'))
            op_msg = await link_msg.channel.fetch_message(
                int(link_msg.content.split('\n')[0].split(' ')[-1].split('/')[-1]))
            op = op_msg.author

            user = interaction.user

            if user.id not in [embedder_id, op.id] and not link_msg.channel.permissions_for(user).manage_messages:
                return await interaction.response.send_message("You don't have permissions to do that!",
                                                               ephemeral=True)
            await link_msg.delete()

    class VisibleView(discord.ui.View):
        def __init__(self, embed_links):
            super().__init__(timeout=None)

            self.embed_links = embed_links

        @discord.ui.button(label="Make Visible", style=discord.ButtonStyle.green, custom_id="visible")
        async def visible(self, interaction: discord.Interaction, button: discord.ui.Button):
            link_msg = interaction.message
            op_msg = await link_msg.channel.fetch_message(
                int(link_msg.content.split('\n')[0].split(' ')[-1].split('/')[-1]))

            await self.embed_links(interaction, op_msg, visible=True)

    async def embed_links_visible(self, interaction: discord.Interaction, message: discord.Message) -> None:
        await self.embed_links(interaction, message, visible=True)

    async def embed_links_silent(self, interaction: discord.Interaction, message: discord.Message) -> None:
        await self.embed_links(interaction, message, visible=False)

    async def embed_links(self, interaction: discord.Interaction, message: discord.Message,
                          *, visible: bool = False) -> None:
        if visible and not message.channel.permissions_for(interaction.user).embed_links:
            return await interaction.response.send_message("You need Embed Links permissions to do this.",
                                                           ephemeral=True)

        matches = [i for i in re.finditer(url_regex, message.content)]
        if not matches:
            return await interaction.response.send_message("Couldn't identify any links in this message.",
                                                           ephemeral=True)
        if len(message.embeds) == len(matches):
            return await interaction.response.send_message("All the links are already embedded!", ephemeral=True)

        view = None
        if visible:
            view = self.CloseView()
        elif message.channel.permissions_for(interaction.user).embed_links:
            view = self.VisibleView(self.embed_links)

        txt = f"### Embedding links from {message.jump_url}\n{{0}}" + '\n'.join(f"- {link.group()}" for link in matches)
        if visible:
            await message.reply(
                txt.format(f"Triggered by {interaction.user.mention}\n"),
                view=view,
                allowed_mentions=AllowedMentions.none()
            )
            await interaction.response.send_message("Embedding...", ephemeral=True)
        else:
            await interaction.response.send_message(
                txt.format(""),
                ephemeral=True,
                view=view
            )


async def setup(bot):
    await bot.add_cog(EmbedCog(bot))
