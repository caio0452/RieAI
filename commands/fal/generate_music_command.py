import httpx
import discord
from discord import app_commands
from discord.ext import commands
from reynard_ai.util.rate_limits import RateLimit
from commands.fal.fal_common import BaseFalCommand
from reynard_ai.bot_data.bot_profile import Profile

class MusicGenCommand(BaseFalCommand):
    def __init__(self, discord_bot: commands.Bot, bot_profile: Profile) -> None:
        super().__init__(
            discord_bot, 
            bot_profile, 
            RateLimit(n_messages=2, seconds=120)
        )

    async def _fal_ai_request_music(self, style: str, lyrics: str):
        url = "https://fal.run/fal-ai/minimax-music/v2"
        headers = {
            "Authorization": f"Key {self.fal_config.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "prompt": style,
            "lyrics_prompt": lyrics,
            "audio_setting": {
                "format": "mp3"
            }
        }
        async with httpx.AsyncClient(timeout=120) as client:
            return await client.post(url, headers=headers, json=data)

    @app_commands.command(name="generate_music", description="Generate a song with certain lyrics")
    @app_commands.describe(
        style="Music genre and description",
        lyrics="Lyrics"
    )
    async def generate_music(self, interaction: discord.Interaction, style: str, lyrics: str) -> None:
        if len(style) < 10 or len(lyrics) < 10:
            await interaction.response.send_message("⚠️ Style and lyrics must have at least 10 characters each")
            return

        async def logic():
            req = await self._fal_ai_request_music(style, lyrics)
            req.raise_for_status()
            data = req.json()
            
            audio_data = data.get("audio", {})
            url = audio_data.get("url")
            
            if not url:
                raise ValueError("ERROR: Missing audio URL in API response")

            return await self._download_media(url, "generated_song.mp3")

        display_prompt = f"**Style:** {style}\n**Lyrics:** {lyrics[:50]}..."
        await self._execute_generation(
            interaction=interaction,
            prompt=display_prompt,
            generation_coroutine=logic
        )