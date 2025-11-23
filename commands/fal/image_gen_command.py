import httpx
import discord

from discord import app_commands
from discord.ext import commands
from reynard_ai.util.rate_limits import RateLimit
from commands.fal.fal_common import BaseFalCommand
from reynard_ai.bot_data.bot_profile import Profile

class ImageGenCommand(BaseFalCommand):
    def __init__(self, discord_bot: commands.Bot, bot_profile: Profile) -> None:
        super().__init__(
            discord_bot, 
            bot_profile, 
            RateLimit(n_messages=3, seconds=60)
        )

    async def _fal_ai_request_image(self, request: str):
        url = "https://fal.run/fal-ai/realistic-vision"
        headers = {
            "Authorization": f"Key {self.fal_config.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "prompt": request,
            "model_name": "SG161222/RealVisXL_V4.0",
            "negative_prompt": "Bad anatomy, ugly, low quality, low detail, blurry",
            "enable_safety_checker": True,
            "num_images": 1
        }
        async with httpx.AsyncClient(timeout=60) as client:
            return await client.post(url, headers=headers, json=data)

    @app_commands.command(name="generate_image", description="Generate an image")
    async def generate_image(self, interaction: discord.Interaction, query: str) -> None:
        
        async def logic():
            req = await self._fal_ai_request_image(query)
            req.raise_for_status()
            data = req.json()
            image_url = data["images"][0]["url"]
            return await self._download_media(image_url, "image1.png")

        await self._execute_generation(
            interaction=interaction,
            prompt=query,
            generation_coroutine=logic
        )
