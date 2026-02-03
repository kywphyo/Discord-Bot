import os
import random
import discord
from dotenv import load_dotenv
from discord.ext import commands
from discord import app_commands
import yt_dlp 
import asyncio
from collections import deque

#load the env variables from .env
load_dotenv()

SONG_QUEUES = {}
#get variables from the .env file
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')

async def search_ytdlp_async(query, ydl_opts):
   loop = asyncio.get_running_loop()
   return await loop.run_in_executor(None, lambda: _extract(query, ydl_opts))

def _extract(query, ydl_opts):
   with yt_dlp.YoutubeDL(ydl_opts) as ydl:
      return ydl.extract_info(query, download=False)

#defining intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

client = discord.Client(intents = intents)
bot = commands.Bot(command_prefix='e!', intents=intents)

#YLDLP option for audio extraction 

YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist': 'True', "youtube_include_dash_manifest": False, "youtube_include_hls_manifest": False}
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
#event handler(listener)
@bot.event
async def on_ready():
  #find the guild with discord library search 
  guild = discord.utils.get(bot.guilds, name=GUILD)
  print(f'{bot.user} has connected to Discord!\n'
        f'{guild.name}(id: {guild.id})')
  #list of members 
  members ='\n -'.join([member.name for member in guild.members])
  print(f'Guild Members:\n - {members}')

@bot.event
async def on_member_join(member):
  await member.create_dm()
  await member.dm_channel.send(
    f'Hi {member.name}, Welcome to {member.guild.name}'
  )

@bot.event
async def on_error(event, *args, **kwargs):
  with open('err.log', 'a') as f:
    if event == 'on message':
      f.write(f'Unhandled message: {args[0]}\n')
    else:
      raise

@bot.command(name ='ping', help="Respond with pong!")
async def on_message(ctx):
  response ='pong!'
  await ctx.send(response)

#play music from youtube
@bot.command(name="p", help="Play a song")
async def play(ctx, name: str):
    if not ctx.author.voice:
        await ctx.send("You must be in a voice channel!")
        return

    # Join the voice channel
    channel = ctx.author.voice.channel
    voice_client = ctx.voice_client or await channel.connect()
   
   #first search result from youtube   
    query = "ytsearch1: " + name
    results = await search_ytdlp_async(query, YDL_OPTIONS)
    tracks = results.get("entries", [])

    if tracks is None:
       await ctx.send("No results found.")
       return
    
    first_track = tracks[0]
    audio_url = first_track["url"]
    title = first_track.get("title", "Untitled")
    
    guild_id = str(ctx.guild.id)

    if SONG_QUEUES.get(guild_id) is None:
       SONG_QUEUES[guild_id] = deque()
    
    SONG_QUEUES[guild_id].append((audio_url, title))

    if voice_client.is_playing() or voice_client.is_paused():
       await ctx.send(f"Added to queue: **{title}**")

    else:
       #await ctx.send(f"Now playing: **{title}**")
       await play_next_song(voice_client, guild_id, ctx.channel)

@bot.command(name="skip", help="Skip the current song playing")
async def skip(ctx):
   if ctx.guild.voice_client and (ctx.guild.voice_client.is_playing() or ctx.guild.voice_client.is_paused()):
      ctx.guild.voice_client.stop()
      await ctx.send("Skipped the current song")
   else:
      await ctx.response.send_message("Not playing anything to skip")
async def play_next_song(voice_client, guild_id, channel):
   if SONG_QUEUES[guild_id]:
      audio_url, title = SONG_QUEUES[guild_id].popleft()

      source = discord.FFmpegOpusAudio(audio_url, **FFMPEG_OPTIONS)

      def after_play(error):
        if error:
          print(f"Error playing {title}: {error}")
        asyncio.run_coroutine_threadsafe(play_next_song(voice_client,guild_id, channel), bot.loop)
      
      voice_client.play(source, after=after_play)
      asyncio.create_task(channel.send(f"Now Playing: **{title}**"))
   
   else:
      await voice_client.disconnect()
      SONG_QUEUES[guild_id] = deque()





@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()


@bot.command(name='osk', help="Send a random photo of osk")
async def randompic(ctx):
   images_dir = os.path.join(os.path.dirname(__file__), 'images')
   if not os.path.isdir(images_dir):
      await ctx.send("Images folder not found. Create an 'images' folder next to bot.py and add image files.")
      return
   files = [f for f in os.listdir(images_dir) if os.path.isfile(os.path.join(images_dir, f)) and f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))]
   if not files:
      await ctx.send("No images found in the images folder.")
      return
   chosen = random.choice(files)
   path = os.path.join(images_dir, chosen)
   await ctx.send(file=discord.File(path))

@bot.command(name='upload', help="Upload an image to the images folder. Usage: e!upload (with image attachment)")
async def upload_image(ctx):
   images_dir = os.path.join(os.path.dirname(__file__), 'images')
   
   # Create images folder if it doesn't exist
   if not os.path.isdir(images_dir):
      os.makedirs(images_dir)
      await ctx.send("Created images folder.")
   
   # Check if message has attachments
   if not ctx.message.attachments:
      await ctx.send("Please attach an image file to upload. Usage: `e!upload` (with image attachment)")
      return
   
   uploaded_files = []
   valid_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tiff')
   
   for attachment in ctx.message.attachments:
      # Validate file extension
      if not attachment.filename.lower().endswith(valid_extensions):
         await ctx.send(f"❌ **{attachment.filename}** - Invalid file type. Supported: PNG, JPG, JPEG, GIF, WEBP, BMP, TIFF")
         continue
      
      # Check file size (max 10MB)
      if attachment.size > 10 * 1024 * 1024:
         await ctx.send(f"❌ **{attachment.filename}** - File too large (max 10MB)")
         continue
      
      try:
         # Save file to images folder
         file_path = os.path.join(images_dir, attachment.filename)
         await attachment.save(file_path)
         uploaded_files.append(attachment.filename)
      except Exception as e:
         await ctx.send(f"❌ Error uploading **{attachment.filename}**: {str(e)}")
   
   # Send confirmation message
   if uploaded_files:
      files_list = "\n".join([f"✅ {f}" for f in uploaded_files])
      await ctx.send(f"Successfully uploaded {len(uploaded_files)} image(s):\n{files_list}")
   
   if not uploaded_files and ctx.message.attachments:
      await ctx.send("No valid images were uploaded.")

bot.run(TOKEN)

