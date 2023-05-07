import discord
from discord.ext import commands


class ModPingCog(discord.ext.commands.Cog, name="ModPing"):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if 895625499496308776 in [i.id for i in message.role_mentions]:
            modrole = message.guild.get_role(281649289397141505)
            pagemsgs = {
                "header": "Paging Watchers...",
                "online": "Pinging all **online/idle** moderators... ",
                "offline": "No online/idle moderators - pinging **all** moderators... ",
                "repeated": "Pinging all moderators... ",
                "repeat": "\nIf necessary, reply to **this** message with the <@&895625499496308776> ping to ping **all** moderators.",
                "already": "All moderators have already been pinged."
            }
            embed = discord.Embed(title=pagemsgs["header"], colour=0xe61c23)
            # embed.set_thumbnail(url="https://i.imgur.com/5iXSNmz.png")
            embed.set_thumbnail(url="https://i.imgur.com/E28dqYe.png")
            embed.set_footer(text=f"Pinged by {str(message.author)} ({message.author.id})")

            if message.reference:
                reply = await message.channel.fetch_message(message.reference.message_id)
                if reply.author.id == self.bot.user.id and reply.embeds and reply.embeds[0].title == pagemsgs["header"]:
                    if pagemsgs["repeat"] not in reply.embeds[0].description:
                        return await message.reply(pagemsgs["already"])
                    else:
                        embed.description = pagemsgs["repeated"]
                        if reply.reference: embed.description = embed.description + f"[Jump Link]({reply.reference.jump_url})"
                        return await message.reply(modrole.mention, embed=embed)

            mods = modrole.members
            online = [i for i in mods if
                      not isinstance(i.status, str) and i.status in [discord.Status.online, discord.Status.idle]]
            if online:
                ping = " ".join([i.mention for i in online])
                msg = pagemsgs["online"]
                if message.reference: msg += f"[Jump Link]({message.reference.jump_url})"
                msg += pagemsgs["repeat"]
            else:
                ping = modrole.mention
                msg = pagemsgs["offline"]
                if message.reference: msg += f"[Jump Link]({message.reference.jump_url})"
            embed.description = msg

            return await message.reply(ping, embed=embed)


async def setup(bot):
    await bot.add_cog(ModPingCog(bot))
