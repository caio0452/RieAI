import httpx
import asyncio
import discord

from discord import app_commands
from discord.ext import commands
from reynard_ai.util.rate_limits import RateLimit
from commands.fal.fal_common import BaseFalCommand
from reynard_ai.bot_data.bot_profile import Profile

class VideoGenCommand(BaseFalCommand):
    def __init__(self, discord_bot: commands.Bot, bot_profile: Profile) -> None:
        super().__init__(
            discord_bot, 
            bot_profile, 
            RateLimit(n_messages=1, seconds=60)
        )

    async def _fal_ai_submit_video_request(self, prompt: str) -> str:
        url = "https://queue.fal.run/fal-ai/bytedance/seedance/v1/pro/fast/text-to-video"
        headers = {
            "Authorization": f"Key {self.fal_config.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "prompt": prompt,
            "aspect_ratio": "16:9",
            "resolution": "480p",
            "duration": "3",
            "enable_safety_checker": True
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, headers=headers, json=data)
            response.raise_for_status()
            response_data = response.json()
            if "request_id" not in response_data:
                raise ValueError(f"API did not return a request_id. Response: {response_data}")
            return response_data["request_id"]

    async def _fal_ai_poll_for_video_result(self, request_id: str) -> dict:
        status_url = f"https://queue.fal.run/fal-ai/longcat-video/requests/{request_id}/status"
        result_url = f"https://queue.fal.run/fal-ai/longcat-video/requests/{request_id}"
        headers = { "Authorization": f"Key {self.fal_config.api_key}" }
        
        async with httpx.AsyncClient(timeout=180) as client:
            while True:
                status_response = await client.get(status_url, headers=headers)
                status_response.raise_for_status()
                status_data = status_response.json()

                status = status_data.get("status")
                if status == "COMPLETED":
                    break
                elif status in ["IN_PROGRESS", "IN_QUEUE"]:
                    await asyncio.sleep(5)
                else:
                    error_info = status_data.get('error', 'Unknown error')
                    raise RuntimeError(f"Video generation failed with status '{status}': {error_info}")
            
            result_response = await client.get(result_url, headers=headers)
            result_response.raise_for_status()
            return result_response.json()

    @app_commands.command(name="generate_video", description="Generate a short video from a text prompt")
    async def generate_video(self, interaction: discord.Interaction, query: str) -> None:
        
        async def logic():
            await interaction.followup.send(f"Generating video for your prompt:...")
            request_id = await self._fal_ai_submit_video_request(query)
            result_data = await self._fal_ai_poll_for_video_result(request_id)
            video_url = result_data["video"]["url"]
            return await self._download_media(video_url, "generated_video.mp4")

        await self._execute_generation(
            interaction=interaction,
            prompt=query,
            generation_coroutine=logic,
            success_message=f"<@{interaction.user.id}> Your video is ready!\n`PROMPT:` **{query}**"
        )
