import requests
import discord
from discord.ext import commands
import urllib.parse
import math
import aiohttp


# Création de l'instance du bot
bot = commands.Bot(command_prefix='/', intents=discord.Intents.all())
api_token = "RD TOKEN"


search_results = []
current_page = 0
items_per_page = 10

async def debrid_link(api_token, link):
    headers = {
        "Authorization": f"Bearer {api_token}"
    }
    url = "https://api.real-debrid.com/rest/1.0/unrestrict/link"
    data = {
        "link": link,
        "host": "real-debrid.com"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=data) as response:
            # Ensure to handle potential errors like non-JSON responses
            try:
                api_response = await response.json()
                if response.status == 200:
                    return api_response.get('download')
                else:
                    return None
            except Exception as e:
                print("Failed to parse JSON response:", e)
                return None


def addmagnet(api_token,magnet):
    headers = {
        "Authorization": f"Bearer {api_token}"
    }
    url = "https://api.real-debrid.com/rest/1.0/torrents/addMagnet"
    params = {
        "magnet": magnet,
        "host": "real-debrid.com"
    }
    response = requests.post(url,headers=headers,data=params)
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 201:
        postdata = {'files': "all"}
        r2=requests.post('https://api.real-debrid.com/rest/1.0/torrents/selectFiles/'+response.json()['id'], headers=headers, data=postdata)
        if r2.status_code == 204:
            r3=requests.get('https://api.real-debrid.com/rest/1.0/torrents/info/'+response.json()['id'],headers=headers)
            if r3.status_code == 200:
                torrent_info = r3.json()
                return torrent_info
    else:
        print("ya r")
        return None




def fetch_results(query):
    global search_results
    url = 'https://nyaaapi.onrender.com/nyaa'
    params = {'q': query, 'page': 1}
    headers = {'accept': 'application/json'}
    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()
        search_results = data['data']
    else:
        search_results = []

def generate_page_content(page):
    start = page * items_per_page
    end = start + items_per_page
    page_content = ""

    for i, item in enumerate(search_results[start:end], start=1):
        title = item.get('title')
        torrent = item.get('torrent')
        magnet = item.get('magnet')
        size = item.get('size')
        seeders = item.get('seeders')
        leechers = item.get('leechers')


        page_content += f"{i}. {title}\n"
        page_content += f"Size: {size} | Seeders: {seeders} | Leechers: {leechers}\n\n"


    return page_content

def generate_emotes(search_results, page):
    emotes = []
    start = page * items_per_page
    end = start + items_per_page
    for i, item in enumerate(search_results[start:end], start=1):
        torrent = item.get('torrent')
        magnet = item.get('magnet')
        emote = discord.ui.Button(label=f"Magnet {i}")
        
        async def callback(interaction: discord.Interaction, magnet=magnet):
            await interaction.response.send_message(f"Magnet link successfully sent")
            
            # Appel asynchrone de la fonction addmagnet
            torrent_info = addmagnet(api_token, magnet)
            
            if torrent_info and 'links' in torrent_info:
                download_links = []  # Initialize here to avoid reference before assignment
                message_lines = [f"**Title:** {torrent_info.get('filename', 'No title available')}"]  # Safe default

                for link in torrent_info['links']:
                    download_url = await debrid_link(api_token, link)
                    if download_url:
                        download_links.append(download_url)

                message_lines.extend([f"**Download Link:** {link}" for link in download_links])
                message_content = "\n".join(message_lines)

                parts = []
                current_part = ""

                for line in message_content.split("\n"):
                    if len(current_part) + len(line) + 1 > 2000:
                        parts.append(current_part)
                        current_part = line
                    else:
                        if current_part:
                            current_part += "\n" + line
                        else:
                            current_part = line

                if current_part:
                    parts.append(current_part)

                for part in parts:
                    await interaction.followup.send(part)
            else:
                await interaction.followup.send("Failed to retrieve torrent information or links.")

        emote.callback = callback
        emotes.append(emote)
    return emotes




@bot.hybrid_command(name='search', description='Search a torrent on Nyaa')
async def search(ctx: commands.Context, search: str):
    global current_page
    current_page = 0

    fetch_results(search)

    if not search_results:
        await ctx.send("Aucun résultat trouvé.")
        return

    page_content = generate_page_content(current_page)
    
    if len(page_content) > 4096:
        page_content_parts = [page_content[i:i+4096] for i in range(0, len(page_content), 4096)]
    else:
        page_content_parts = [page_content]

   # Génération des emotes avec les liens de téléchargement
    emotes = generate_emotes(search_results, current_page)

    # Envoi du premier embed
    view = discord.ui.View()
    for emote in emotes:
        view.add_item(emote)
    message = await ctx.send(embed=discord.Embed(
        title=f"Résultats pour '{search}' (Page {current_page + 1})",
        description=page_content_parts[0]
    ), view=view)

    await message.add_reaction("⬅️")
    await message.add_reaction("➡️")

# Gestionnaire d'événements pour les réactions
@bot.event
async def on_reaction_add(reaction, user):
    global current_page

    # Ignorer les réactions du bot lui-même
    if user == bot.user:
        return

    # Seules les réactions sur les messages du bot sont prises en compte
    if reaction.message.author != bot.user:
        return

    # Gérer les réactions pour changer de page
    if reaction.emoji == "⬅️":
        if current_page > 0:
            current_page -= 1
    elif reaction.emoji == "➡️":
        max_pages = math.ceil(len(search_results) / items_per_page)
        if current_page + 1 < max_pages:
            current_page += 1

    page_content = generate_page_content(current_page)
    emotes = generate_emotes(search_results, current_page)

    # Vérification de la longueur du contenu pour éviter de dépasser la limite
    if len(page_content) > 4096:
        page_content_parts = [page_content[i:i+4096] for i in range(0, len(page_content), 4096)]
    else:
        page_content_parts = [page_content]

    # Édition du message avec le nouveau contenu de la page
    view = discord.ui.View()
    for emote in emotes:
        view.add_item(emote)
    await reaction.message.edit(embed=discord.Embed(
        title=f"Résultats pour '{reaction.message.embeds[0].title}' (Page {current_page + 1})",
        description=page_content_parts[0]
    ),view=view)

    # Supprimer la réaction de l'utilisateur
    await reaction.remove(user)


@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    await bot.tree.sync()


# Lancer le bot avec le token
bot.run('BOT-TOKEN')