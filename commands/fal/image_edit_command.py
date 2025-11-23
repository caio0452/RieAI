import httpx
import discord
from typing import Any

from discord import app_commands
from discord.ext import commands
from reynard_ai.util.rate_limits import RateLimit
from commands.fal.fal_common import BaseFalCommand
from reynard_ai.bot_data.bot_profile import Profile

class ImageEditCommand(BaseFalCommand):
    def __init__(self, discord_bot: commands.Bot, bot_profile: Profile) -> None:
        super().__init__(
            discord_bot, 
            bot_profile, 
            RateLimit(n_messages=3, seconds=60)
        )
        self.fal_config = bot_profile.fal_image_gen_config

    async def _fal_ai_request_edit(self, image_url: str, request: str):
        url = "https://fal.run/fal-ai/flux-pro/kontext"
        headers = {
            "Authorization": f"Key {self.fal_config.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "prompt": request,
            "guidance_scale": 3.5,
            "safety_tolerance": "2",
            "num_images": 1,
            "output_format": "jpeg",
            "image_url": image_url,
            "sync_mode": True,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            return await client.post(url, headers=headers, json=data)

    @app_commands.command(name="edit_image", description="edit an image")
    async def edit_image(self, interaction: discord.Interaction, image_url: str, query: str) -> None:
        
        async def logic():
            req = await self._fal_ai_request_edit(image_url, query)
            req.raise_for_status()
            data = req.json()
            result_url = data["images"][0]["url"]
            return await self._download_media(result_url, "edited_image.png")

        await self._execute_generation(
            interaction=interaction,
            prompt=query,
            generation_coroutine=logic
        )