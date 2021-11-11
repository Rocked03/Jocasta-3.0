import discord
from discord.ext import commands

from bs4 import BeautifulSoup
import aiohttp, operator, datetime, html, asyncio, marvel, textwrap
from marvel.marvel import Marvel # pip install -U git+https://github.com/Rocked03/PyMarvel#egg=PyMarvel


class ComicsCog(commands.Cog, name = "Comics"):
    """General commands"""

    def __init__(self, bot):
        self.bot = bot
        self.bot.marvel = Marvel(self.bot.marvelKey_public, self.bot.marvelKey_private)
        self.bot.tasks['releases'] = self.bot.loop.create_task(self.releasesloop())

    @commands.command(name = "comicreleases", aliases = ['cr'])
    @commands.is_owner()
    async def comicreleases(self, ctx):
        """Lists the weekly comic releases"""
        async with ctx.typing():
            releases, date, attr = await self.releasescraper()
            embeds, compact = await self.releaseembedparse(releases, date, attr, link = True)

            date = date.strftime('%d %B %Y (%d/%m/%y)')
            header = await ctx.send(f'**Comics Release list __{date}__**')
            pins = await ctx.channel.pins()
            if len(pins) == 50:
                await pins[-1].unpin()
            await header.pin()
            await ctx.send("<@&407642845076389888>")

            msgs = {}
            # for embed in embeds: 
            for title, embed in embeds.items():
                msg = await ctx.send(embed = embed)
                await msg.add_reaction("comicpull:417460522993057804")
                # msgs.append(msg)
                msgs[title] = msg

            def rreplace(s, old, new, occurrence): return new.join(s.rsplit(old, occurrence))

            fieldno = []
            x = 0
            for embed in compact:
                for field in embed.fields: fieldno.append(x)
                x += 1

            z = 0
            allfields = []
            [allfields.extend(list(y.fields)) for y in compact]
            fn = 0
            for field, msg, n in zip(allfields, msgs.values(), fieldno):
                if n != fn: z = 0
                fn = n

                compact[n].set_field_at(z, name = field.name, value = rreplace(field.value, '#', msg.jump_url, 1), inline = False)
                
                z += 1

            for embed in compact:
                listmsg = await ctx.send(embed = embed)
                try:
                    await listmsg.publish()
                except Exception as e:
                    print(e)

            embed = discord.Embed(colour = self.bot.colours.comicreleases)
            embed.add_field(name="What will you be pulling this week?", value="React on the comics with <:comicpull:417460522993057804>!", inline=True)
            embed.add_field(name="Data is from the Marvel.com website. See the calendar here!", value="https://marvel.com/comics/calendar", inline=True)
            embed.add_field(name="Back to the start", value=f"Jump back to the top of this comic release list **[here]({header.jump_url})**")
            embed.add_field(name="Want the Comic Notify role?", value="Head over to <#614550469318148140> and self-assign yourself the role!", inline=True)
            embed.set_footer(text = "This bot was coded by Rocked03#3304, specifically for the Marvel Discord server.")
            await ctx.send(embed=embed)


            async with aiohttp.ClientSession() as cs:
                async with cs.get("https://marvel.com/comics/calendar/") as r:
                    page = await r.text()
            soup = BeautifulSoup(page, 'html.parser')

            releases = dict()
            releasedate = None

            scrapes = {}
            for link in soup.find_all('a', class_="meta-title"):
                plink = 'https:' + link.get('href').strip()

                async with aiohttp.ClientSession() as cs:
                    async with cs.get(plink) as r:
                        page = await r.text()
                soup = BeautifulSoup(page, 'html.parser')

                ctitle = soup.find_all('h1')[0].get_text().strip()

                descs = soup.find_all('p')
                if len(descs) >= 1:
                    cdesc = str(descs[1].get_text()).strip()
                    cdesc if cdesc[-4:] != 'more' else cdesc[:-26]
                else: cdesc = "None"
                if not cdesc: cdesc = "None"

                scrapes[ctitle] = cdesc

            for ct, m in msgs.items():
                if ct not in scrapes.keys():
                    continue

                embed = m.embeds[0]
                if embed.fields[0].value != "None":
                    continue

                n = embed.fields[0].name
                embed.set_field_at(0, name=n, value=scrapes[ct], inline=False)

                await m.edit(embed=embed)




    async def releasescraper(self):
        releases = dict()

        comicraw = await self.bot.marvel.get_comics(format = 'comic', noVariants = 'true', dateDescriptor = 'thisWeek', limit = 50)

        for comic in comicraw.data.results:
            releasedate = comic.dates[0].date
            attr = comicraw.dict['attributionText']

            releases[comic.title] = self.comicdictparse(comic)

        releasesalpha = {}
        for i in sorted(releases.items(), key=operator.itemgetter(0)): releasesalpha[i[0]] = i[1]

        return releasesalpha, releasedate, attr

    async def releaseembedparse(self, releases: dict, date: datetime.timedelta, attr, link = False):
        date = date.strftime('%d %B %Y (%d/%m/%y)')

        embeds = {}
        for k, v in releases.items():
            embed, title = await self.issueembed(v, attr, True)
            embed.colour = self.bot.colours.comicreleases
            # embeds.append(embed)
            embeds[title] = embed

        compact = discord.Embed(colour = self.bot.colours.comicreleases)
        # compact.set_author(name=f"Full Release List - {date}")
        # compact.set_thumbnail(url = 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/04/MarvelLogo.svg/1200px-MarvelLogo.svg.png')
        # compact.set_footer(text = attr)
        def jumplink(): return " ([Jump](#))" if link else ''

        for k, v in releases.items(): 
            compact.add_field(name = k, value = ', '.join([html.unescape(i['name']) for i in v['creators'] if i['role'] == 'writer']) + jumplink(), inline = False)
        for x, field in enumerate(compact.fields):
            if not field.value: compact.set_field_at(x, name = compact.fields[x].name, value = "None", inline = False)

        fields = dict()
        for k, v in releases.items(): 
            fields[k] = ', '.join([html.unescape(i['name']) for i in v['creators'] if i['role'] == 'writer']) + jumplink()
        for k, v in enumerate(fields.items()):
            if not v: fields[k] = "None"

        emptyembed = discord.Embed(colour = self.bot.colours.comicreleases)
        emptyembed.set_author(name=f"Full Release List - {date}")
        emptyembed.set_thumbnail(url = 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/04/MarvelLogo.svg/1200px-MarvelLogo.svg.png')

        cembeds = [emptyembed]

        for field in compact.fields:
            if len(''.join([i.name + i.value for i in cembeds[-1].fields])) > 4500 or len(cembeds[-1].fields) >= 25:
                cembeds.append(discord.Embed(color = self.bot.colours.comicreleases))
            cembeds[-1].add_field(name = field.name, value = field.value, inline = field.inline)

        cembeds[-1].set_footer(text = attr)



        return embeds, cembeds


    async def releasesloop(self):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(id=534457946046988288)
        while not self.bot.is_closed():
            now = datetime.datetime.utcnow()
            today = now.date()
            tmp1 = datetime.datetime.combine(today, datetime.time(0)) + datetime.timedelta(1 - today.weekday())
            result = tmp1 + datetime.timedelta(7) if tmp1 < now else tmp1
            sleepsecs = (result - datetime.datetime.utcnow()).total_seconds()
            print(f"Weekly Release list auto-command set to run in {result - datetime.datetime.utcnow()}")
            await asyncio.sleep(sleepsecs)

            try:
                ctxmsg = await channel.send('>>cr')
                ctx = await self.bot.get_context(ctxmsg)
                await ctx.message.delete()

                await ctx.invoke(next(x for x in self.bot.commands if x.name == "comicreleases"))

                print(f'Weekly Release list auto-command successful')
            except Exception as e:
                print(e)


    def creatorparse(self, creators):
        def sorting_key(person):
            priority = ["writer", "penciler", "inker", "colorist", "letterer", "editor"]
            try: return priority.index(person['role'])
            except ValueError: return len(priority)

        def s(x): return 's' if len(x) != 1 else ''

        craw = sorted(sorted(creators, key = lambda item: item['role']), key = sorting_key)
        c = {}
        for i in craw:
            try: c[i['role']]
            except KeyError: c[i['role']] = []
            c[i['role']].append(html.unescape(i['name']))

        ctxt = '\n'.join([f"**{k.title()}{s(v)}**: {', '.join(v)}" for k, v in c.items() if ' (cover)' not in k])

        if not ctxt: ctxt = 'None listed'

        return ctxt

    def comicdictparse(self, comic):
        urls = {}
        for url in comic.urls: urls[url['type']] = url['url']

        try: cover = comic.images[0].path + '/clean.jpg'
        except IndexError: cover = "https://i.annihil.us/u/prod/marvel/i/mg/b/40/image_not_available/clean.jpg"

        d = {
            'title': comic.title,
            'desc': comic.description,
            'creators': [{'name': i.name, 'role': i.role} for i in comic.creators.items],
            'cover': cover,
            'links': urls,
            'id': comic.id,
            'series': {
                'name': comic.series['name'], 
                'id': comic.series['resourceURI'].split('/')[-1],
            },
        }

        for k, v in d.items(): 
            if type(v) is str: d[k] = html.unescape(v)

        return d


    @commands.command(aliases = ['cnotify'], hidden = True)
    async def comicnotify(self, ctx):
        """Toggles Comic Notify role"""
        cn = ctx.guild.get_role(407642845076389888)
        if cn in ctx.author.roles: 
            await ctx.author.remove_roles(cn)
            await ctx.send(f"{ctx.author.mention}, removed the Comic Notify role!")
        else: 
            await ctx.author.add_roles(cn)
            await ctx.send(f"{ctx.author.mention}, gave you the Comic Notify role!")


    @commands.command(aliases = ['comics', 'search'])
    async def comic(self, ctx, *, query):
        """Searches for comics with the Marvel.com API"""
        query = list(filter(None, query.split('#')))
        if len(query) == 1: 
            comicname = query[0].strip()
            issue = None
        else: 
            comicname = ' '.join(query[:-1]).strip()
            issue = query[-1]

        try:
            if len(str(int(comicname))) >= 4: issueid = int(comicname)
            else: issueid = None
        except Exception:
            issueid = None

        if not issueid:
            comicfull = await self.bot.marvel.get_series(titleStartsWith = comicname, limit = 100, orderBy = "-startYear")
            comiccoll = await self.bot.marvel.get_series(titleStartsWith = comicname, limit = 100, orderBy = "-startYear", seriesType = 'collection')

            try: comicfullt = comicfull.data.dict['total']
            except KeyError: comicfullt = 0
            try: comiccollt = comiccoll.data.dict['total']
            except KeyError: comiccollt = 0

            limit = 10

            ntotal = comicfullt - comiccollt
            nresults = []
            oresults = [i.dict for i in comiccoll.data.results]
            x = 0
            for i in comicfull.data.results:
                if i.dict not in oresults: 
                    nresults.append(i.dict)
                    x += 1
                if x >= limit: break

            nwrapper = comicfull.dict
            nwrapper['data']['total'] = ntotal
            nwrapper['data']['count'] = len(nresults)
            nwrapper['data']['results'] = nresults

            comicraw = marvel.series.SeriesDataWrapper(self.bot.marvel, nwrapper)

        else:
            comicraw = await self.bot.marvel.get_single_series(issueid)

            # comic search with ID

        attr = comicraw.dict['attributionText']
        comicdata = comicraw.data

        totalcount = comicdata.dict['total']
        if totalcount == 1:
            if issue:
                results = comicdata.results[0]
                comicn = await self.bot.marvel.get_comics(
                    format = 'comic',
                    formatType = 'comic',
                    noVariants = 'true',
                    titleStartsWith = ' ('.join(results.title.split(' (')[:-1]),
                    startYear = results.startYear,
                    issueNumber = issue,
                )

                if comicn.data.results:
                    embed = await self.issueembed(self.comicdictparse(comicn.data.results[0]), attr)
                else: embed = await self.seriesembed(comicdata.results[0], attr, ctx)

            else: embed = await self.seriesembed(comicdata.results[0], attr, ctx)

        else: embed = await self.searchembed(comicdata.results, comicname, attr, (comicdata.dict['total'], comicdata.dict['count']), ctx)

        await ctx.send(embed = embed)

    async def searchembed(self, data, query, attr, count, ctx):
        embed = discord.Embed(color = self.bot.colours.marvel)
        embed.set_author(name = f'Search results for - "{query}"')

        for x, series in enumerate(data, 1):
            writers = [i.name for i in series.creators.items if i.role == 'writer']

            # issues = await series.get_comics(noVariants = 'true', orderBy = "-issueNumber", limit = 100)
            # issuecount = issuecount.data.dict['total']

            idcmd = ctx.prefix + str(ctx.command) + " #" + str(series.id)

            info = [
                f'Written by: {", ".join(writers)}',
                # f"{issuecount} issues",
                f"Type `{idcmd}` to see more info"
            ]


            embed.add_field(name = f"{x}: {series.title}", value = '\n'.join(info))

        embed.set_thumbnail(url = "https://upload.wikimedia.org/wikipedia/commons/thumb/0/04/MarvelLogo.svg/1200px-MarvelLogo.svg.png")

        embed.add_field(name = f"Showing {count[1]} of {count[0]} results", value = "For a more precise search, enter a more detailed search query, or search using the series/comic ID.")

        embed.set_footer(text = attr)

        return embed

    async def seriesembed(self, data, attr, ctx):
        series = data

        issues = await series.get_comics(noVariants = 'true', orderBy = "issueNumber", limit = 100)
        issuecount = issues.data.dict['total']
        results = sorted(issues.data.results, key = lambda item: item.issueNumber)
        issue1 = results[0]

        desc = issue1.description
        if not desc: desc = 'None'

        embed = discord.Embed(color = self.bot.colours.marvel)
        embed.set_author(name = f'{series.title}')
        embed.add_field(name = 'Info', value = textwrap.shorten(desc, width=1024, placeholder=' [...]'), inline = False)
        embed.add_field(name = 'Creators', value = self.creatorparse([{'name': i.name, 'role': i.role} for i in series.creators.items]), inline = False)
        embed.add_field(name = 'Issues', value = issuecount, inline = False)
        try: embed.set_image(url = issue1.images[0].path + '/clean.jpg')
        except IndexError: embed.set_image(url = "https://i.annihil.us/u/prod/marvel/i/mg/b/40/image_not_available/clean.jpg")
        embed.set_footer(text = f"{series.id} - {series.title} | {attr}")

        return embed

    async def issueembed(self, data, attr, fullimg = True):
        embed = discord.Embed(colour = self.bot.colours.marvel)
        embed.set_author(name = data['title'], url = data['links']['detail'])
        
        if not data['desc']: data['desc'] = 'None'
        desc = textwrap.shorten(data['desc'], width=1024, placeholder=' [...]') if data['desc'] else 'None'

        embed.add_field(name = 'Description', value = desc, inline = False)

        embed.add_field(name = 'Creators', value = self.creatorparse(data['creators']))
        links = f"View the comic on Marvel.com [here]({data['links']['detail']})"
        # try: links += f"\nPurchase the comic from Marvel [here]({data['links']['purchase']})"
        # except KeyError: pass
        embed.add_field(name = 'Links', value = links)
        series = data['series']['name'] + " (#" + data['series']['id'] + ")"
        embed.add_field(name = 'Series', value = series)
        if data['cover']: 
            if fullimg: embed.set_image(url = data['cover'])
            else: embed.set_thumbnail(url = data['cover'])
        embed.set_footer(text = f"{data['id']} - {data['title']} | {attr}")

        return embed, data['title'].strip()



    async def releasescraperold(self):
        async with aiohttp.ClientSession() as cs:
            async with cs.get("https://marvel.com/comics/calendar/") as r:
                page = await r.text()
        soup = BeautifulSoup(page, 'html.parser')

        releases = dict()
        releasedate = None

        for link in soup.find_all('a', class_="meta-title"):
            plink = 'https:' + link.get('href').strip()
            
            async with aiohttp.ClientSession() as cs:
                async with cs.get(plink) as r:
                    page = await r.text()
            soup = BeautifulSoup(page, 'html.parser')

            ctitle = soup.find_all('h1')[0].get_text()

            descs = soup.find_all('p')
            if len(descs) >= 1:
                cdesc = str(descs[1].get_text()).strip()
                cdesc if cdesc[-4:] != 'more' else cdesc[:-26]
            else: cdesc = "No description"
            if not cdesc: cdesc = "No description"

            cinfo = list(soup.find('div', class_='featured-item-meta').find_all("a"))
            try: cwriter = cinfo[0].get_text().replace('  ', ' ')
            except Exception: cwriter = "Writer not found"
            try: cpenciler = cinfo[1].get_text().replace('  ', ' ')
            except Exception: cpenciler = "Penciler not found"

            ccover = soup.find_all('img', class_='frame-img')[1].attrs['src']

            releasedate = soup.find('div', class_="featured-item-meta")[3].get_text()

            releases[ctitle] = {
                'title': ctitle,
                'desc': cdesc,
                'writer': cwriter,
                'penciler': cpenciler,
                'cover': ccover,
                'link': plink
            }

        releasesalpha = {}
        for i in sorted(releases.items(), key=operator.itemgetter(0)): releasesalpha[i[0]] = i[1]

        return releasesalpha, releasedate

    async def releaseembedparseold(self, releases: dict, date):
        embeds = []
        for k, v in releases.items():
            embed = discord.Embed(colour = self.bot.colours.comicreleases)
            embed.set_author(name = k, url = v['link'])
            embed.add_field(name = 'Description', value = v['desc'], inline = False)
            embed.add_field(name = 'Writer', value = v['writer'])
            embed.add_field(name = 'Penciler', value = v['penciler'])
            embed.set_thumbnail(url = v['cover'])
            embeds.append(embed)

        compact = discord.Embed(colour = self.bot.colours.comicreleases)
        compact.set_author(name=f"Full Release List - {date}")
        for k, v in releases.items(): compact.add_field(name = k, value = v['writer'], inline = False)
        compact.set_thumbnail(url='https://cdn.discordapp.com/attachments/284794057572745216/419656941388955649/Marvel-Logo.png')

        return embeds, compact


def setup(bot):
    bot.add_cog(ComicsCog(bot))
