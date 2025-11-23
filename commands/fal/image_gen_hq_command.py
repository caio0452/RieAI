import httpx
import discord

from discord import app_commands
from discord.ext import commands
from reynard_ai.util.rate_limits import RateLimit
from commands.fal.fal_common import BaseFalCommand
from reynard_ai.bot_data.bot_profile import Profile

class ImageGenHqCommand(BaseFalCommand):
    def __init__(self, discord_bot: commands.Bot, bot_profile: Profile) -> None:
        super().__init__(
            discord_bot, 
            bot_profile, 
            RateLimit(n_messages=1, seconds=60)
        )

    async def _fal_ai_request_image(self, request: str):
        url = "https://fal.run/fal-ai/fal-ai/nano-banana-pro"
        headers = {
            "Authorization": f"Key {self.fal_config.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "prompt": request,
            "model_name": "fal-ai/nano-banana-pro",
            "enable_safety_checker": True,
            "num_images": 1
        }
        async with httpx.AsyncClient(timeout=60) as client:
            return await client.post(url, headers=headers, json=data)

    @app_commands.command(name="generate_image_hq", description="Generate a high-quality image (Nano Banana Pro)")
    async def generate_image_hq(self, interaction: discord.Interaction, query: str) -> None:
        
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
