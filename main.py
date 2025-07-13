import asyncio
import logging
import os
import time
from datetime import datetime

import discord
import yaml
from dotenv import load_dotenv

from src.bot.helper import BotHelper
from src.config.cliargs import CLIArgs
from src.utils.commandline import CommandLine
from src.utils.summarizer import generate_meeting_summary, markdown_to_pdf

load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PLAYER_MAP_FILE_PATH = os.getenv("PLAYER_MAP_FILE_PATH")

logger = logging.getLogger()  # root logger


def configure_logging():
    logging.getLogger('discord').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('faster_whisper').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)

    # Ensure the directory exists
    log_directory = '.logs/transcripts'
    pdf_directory = '.logs/pdfs'
    os.makedirs(log_directory, exist_ok=True) 
    os.makedirs(pdf_directory, exist_ok=True)  

    # Get the current timestamp for the log file name
    current_timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    log_filename = os.path.join(log_directory, f"{current_timestamp}-transcription.log")

    # Custom logging format (date with milliseconds, message)
    log_format = '%(asctime)s %(name)s: %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S.%f'[:-3]  # Trim to milliseconds

    if CLIArgs.verbose:
        logger.setLevel(logging.DEBUG)
        logging.basicConfig(level=logging.DEBUG,
                            format=log_format,
                            datefmt=date_format)
    else:
        logger.setLevel(logging.INFO)
        logging.basicConfig(level=logging.INFO,
                            format=log_format,
                            datefmt=date_format)
    
    # Set up the transcription logger (will be configured per session)
    transcription_logger = logging.getLogger('transcription')
    transcription_logger.setLevel(logging.INFO)

if __name__ == "__main__":
    args = CommandLine.read_command_line()
    CLIArgs.update_from_args(args)

    configure_logging()
    loop = asyncio.get_event_loop()
    
    from src.bot.volo_bot import VoloBot  
    
    bot = VoloBot(loop)

    @bot.event
    async def on_voice_state_update(member, before, after):
        if member.id == bot.user.id:
            # If the bot left the "before" channel
            if after.channel is None:
                guild_id = before.channel.guild.id
                helper = bot.guild_to_helper.get(guild_id, None)
                if helper:
                    helper.set_vc(None)
                    bot.guild_to_helper.pop(guild_id, None)

                bot._close_and_clean_sink_for_guild(guild_id)

    @bot.slash_command(name="connect", description="Connect Scribe to your voice channel.")
    async def connect(ctx: discord.context.ApplicationContext):
        if bot._is_ready is False:
            await ctx.respond("Connection error. Please try again shortly.", ephemeral=True)
            return
        author_vc = ctx.author.voice
        if not author_vc:
            await ctx.respond("Please join a voice channel first.", ephemeral=True)
            return
        # check if we are already connected to a voice channel
        if bot.guild_to_helper.get(ctx.guild_id, None):
            await ctx.respond("I'm already connected to a voice channel.", ephemeral=True)
            return
        await ctx.trigger_typing()
        try:
            guild_id = ctx.guild_id
            vc = await author_vc.channel.connect()
            helper = bot.guild_to_helper.get(guild_id, BotHelper(bot))
            helper.guild_id = guild_id
            helper.set_vc(vc)
            bot.guild_to_helper[guild_id] = helper
            await ctx.respond(f"Connected successfully. Ready to transcribe your meeting.", ephemeral=False)
            await ctx.guild.change_voice_state(channel=author_vc.channel, self_mute=True)
        except Exception as e:
            await ctx.respond(f"{e}", ephemeral=True)

    @bot.slash_command(name="scribe", description="Start transcribing the voice channel.")
    async def ink(ctx: discord.context.ApplicationContext):
        await ctx.trigger_typing()
        connect_command = next((cmd for cmd in ctx.bot.application_commands if cmd.name == "connect"), None)
        if not connect_command:
            connect_text = "`/connect`"
        else:
            connect_text = f"</connect:{connect_command.id}>"
        if not bot.guild_to_helper.get(ctx.guild_id, None):
            await ctx.respond(f"I'm not connected to your voice channel. Please use {connect_text} first.", ephemeral=True)
            return
        # check if we are already scribing
        if bot.guild_is_recording.get(ctx.guild_id, False):
            await ctx.respond("Already transcribing. Please wait for current session to complete.", ephemeral=True)
            return
        bot.start_recording(ctx)
        await ctx.respond("Transcription started. All audio will be recorded and transcribed.", ephemeral=False)
    
    @bot.slash_command(name="stop", description="Stop transcription and get results.")
    async def stop(ctx: discord.context.ApplicationContext):
        guild_id = ctx.guild_id
        helper = bot.guild_to_helper.get(guild_id, None)
        if not helper:
            await ctx.respond("I'm not connected to your voice channel.", ephemeral=True)
            return

        bot_vc = helper.vc
        
        if not bot_vc:
            await ctx.respond("I'm not connected to your voice channel.", ephemeral=True)
            return

        if not bot.guild_is_recording.get(guild_id, False):
            await ctx.respond("No active transcription session found.", ephemeral=True)
            return

        await ctx.trigger_typing()
        
        if bot.guild_is_recording.get(guild_id, False):
            await bot.get_transcription(ctx)
            bot.stop_recording(ctx)
            bot.guild_is_recording[guild_id] = False
            await ctx.respond("Transcription stopped. Session recorded successfully.", ephemeral=False)
            #await bot.get_transcription(ctx)
            bot.cleanup_sink(ctx)
        
    @bot.slash_command(name="disconnect", description="Disconnect from voice channel.")
    async def disconnect(ctx: discord.context.ApplicationContext):
        guild_id = ctx.guild_id
        id_exists = bot.guild_to_helper.get(guild_id, None)
        if not id_exists:
            await ctx.respond("I'm not connected to your voice channel.", ephemeral=True)
            return
        
        helper = bot.guild_to_helper[guild_id]    
        bot_vc = helper.vc
        
        if not bot_vc:
            await ctx.respond("Connection error. Please try reconnecting.", ephemeral=True)
            return
        
        await ctx.trigger_typing()
        await bot_vc.disconnect()
        helper.guild_id = None
        helper.set_vc(None)
        bot.guild_to_helper.pop(guild_id, None)

        await ctx.respond("Disconnected successfully. Thank you for using Scribe.", ephemeral=False)

    @bot.slash_command(name="summarize", description="Generate an AI summary of a transcription session.")
    async def summarize(ctx: discord.context.ApplicationContext, transcription_file: str):
        await ctx.trigger_typing()
        
        # Validate the transcription file path
        log_directory = '.logs/transcripts'
        if not transcription_file.endswith('.log'):
            transcription_file += '.log'
        
        transcription_path = os.path.join(log_directory, transcription_file)
        
        # Check if file exists
        if not os.path.exists(transcription_path):
            # List available files to help user
            try:
                available_files = [f for f in os.listdir(log_directory) if f.endswith('.log')]
                if available_files:
                    file_list = '\n'.join(available_files[:10])  # Show max 10 files
                    await ctx.respond(f"Transcription file not found. Available files:\n```\n{file_list}\n```", ephemeral=True)
                else:
                    await ctx.respond("No transcription files found.", ephemeral=True)
            except:
                await ctx.respond("Transcription file not found.", ephemeral=True)
            return
        
        try:
            # Generate the summary using OpenAI
            markdown_summary = await generate_meeting_summary(transcription_path)
            
            # Convert to PDF
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            pdf_filename = f"summary_{timestamp}.pdf"
            pdf_file_path = await markdown_to_pdf(markdown_summary, pdf_filename)
            
            # Send the PDF as an attachment
            if os.path.exists(pdf_file_path):
                try:
                    with open(pdf_file_path, "rb") as f:
                        discord_file = discord.File(f, filename=pdf_filename)
                        await ctx.respond("Here is the AI-generated meeting summary:", file=discord_file)
                except Exception as e:
                    await ctx.respond(f"Error sending PDF: {str(e)}", ephemeral=True)
            else:
                await ctx.respond("Failed to generate PDF summary.", ephemeral=True)
                
        except FileNotFoundError:
            await ctx.respond("Transcription file not found.", ephemeral=True)
        except ValueError as e:
            await ctx.respond(f"Error: {str(e)}", ephemeral=True)
        except Exception as e:
            await ctx.respond(f"Failed to generate summary: {str(e)}", ephemeral=True)




    @bot.slash_command(name="help", description="Show the help message.")
    async def help(ctx: discord.context.ApplicationContext):
        embed_fields = [
            discord.EmbedField(
                name="/connect", value="Connect to your voice channel.", inline=True),
            discord.EmbedField(
                name="/disconnect", value="Disconnect from your voice channel.", inline=True),
            discord.EmbedField(
                name="/scribe", value="Start voice transcription.", inline=True),
            discord.EmbedField(
                name="/stop", value="Stop transcription and save results.", inline=True),
            discord.EmbedField(
                name="/summarize", value="Generate AI summary of transcription file.", inline=True),
            discord.EmbedField(
                name="/help", value="Show this help message.", inline=True),
        ]

        embed = discord.Embed(title="Scribe Help 📝",
                              description="""Professional Voice Transcription Assistant 🎤 ➡️ 📄""",
                              color=discord.Color.blue(),
                              fields=embed_fields)

        await ctx.respond(embed=embed, ephemeral=True)



    try:
        loop.run_until_complete(bot.start(DISCORD_BOT_TOKEN))
    except KeyboardInterrupt:
        logger.info("^C received, shutting down...")
        asyncio.run(bot.stop_and_cleanup())
    finally:
        # Close all connections
        loop.run_until_complete(bot.close_consumers())

        tasks = [t for t in asyncio.all_tasks(loop) if not t.done()]
        for task in tasks:
            task.cancel()
        loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))

        # Close the loop
        loop.run_until_complete(bot.close())
        loop.close()