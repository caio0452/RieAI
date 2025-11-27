import httpx
import discord
import asyncio

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

    async def _fal_ai_request_image(self, request: str, amount: int):
        url = "https://fal.run/fal-ai/z-image/turbo"
        headers = {
            "Authorization": f"Key {self.fal_config.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "prompt": request,
            "enable_safety_checker": True,
            "num_images": amount
        }
        async with httpx.AsyncClient(timeout=60) as client:
            return await client.post(url, headers=headers, json=data)

    @app_commands.command(name="generate_image", description="Generate one or more images")
    async def generate_image(self, interaction: discord.Interaction, query: str) -> None:
        async def logic():
            req = await self._fal_ai_request_image(query, 3)
            req.raise_for_status()
            data = req.json()
            
            tasks = []
            for index, img_data in enumerate(data["images"]):
                url = img_data["url"]
                filename = f"image_{index + 1}.png"
                tasks.append(self._download_media(url, filename))
            
            files = await asyncio.gather(*tasks)
            return files

        await self._execute_generation(
            interaction=interaction,
            prompt=query,
            generation_coroutine=logic
        )