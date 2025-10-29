import io
import json
import httpx
import asyncio 
import discord
import requests
import traceback

from discord import app_commands
from discord.ext import commands
from reynard_ai.bot_data.bot_profile import Profile
from reynard_ai.util.rate_limits import RateLimit, RateLimiter
from reynard_ai.ai_apis.client import LLMClient, LLMRequestParams

class VideoGenCommand(commands.Cog):
    def __init__(self, discord_bot: commands.Bot, bot_profile: Profile) -> None:
        self.discord_bot = discord_bot
        self.bot_profile = bot_profile
        self.fal_config = bot_profile.fal_image_gen_config # Assuming video uses the same config/key
        self.video_gen_rate_limiter = RateLimiter(RateLimit(n_messages=1, seconds=60))

    async def _is_blocked_prompt(self, prompt: str) -> bool:
        blocked_words = ["nsfw", "naked", "bikini", "lingerie", "sexy", "penis", "fuck", "murder", "blood"]
        NAME = "NSFW_IMAGE_PROMPT_FILTER"
        nsfw_filter_prompt = self.bot_profile.prompts[NAME]
        nsfw_filter_provider = self.bot_profile.providers[NAME]
        nsfw_filter_llm = LLMClient.from_provider(nsfw_filter_provider)

        for word in blocked_words:
            if word in prompt:
                return True

        response = await nsfw_filter_llm.send_request(
            prompt=nsfw_filter_prompt,
            params=LLMRequestParams(
                model_name="gpt-4.1-mini",
                temperature=0
            )
        )
        response_data = json.loads(response.message.content)
        if response_data["mentions_sexual_content"] or response_data["violent_content"] == "high" or response_data["graphic_content"] == "high":
            return True
        return False

    async def _fal_ai_submit_video_request(self, prompt: str) -> str:
        url = "https://queue.fal.run/fal-ai/longcat-video/distilled/text-to-video/480p"
        headers = {
            "Authorization": f"Key {self.fal_config.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "prompt": prompt,
            "enable_safety_checker": True,
            "num_frames": 45
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

    @app_commands.command(
        name="generate_video", 
        description="Generate a short video from a text prompt"
    )
    async def generate_video(self, interaction: discord.Interaction, query: str) -> None:
        user_id = interaction.user.id
        await interaction.response.defer()

        try:
            if await self._is_blocked_prompt(query):
                await interaction.followup.send(":x: Prompt flagged as inappropriate.")
                return
            
            if self.video_gen_rate_limiter.is_rate_limited(user_id):
                await interaction.followup.send(":x: You are being rate limited (1 / min). Please wait.")
                return
            
            self.video_gen_rate_limiter.register_request(user_id)
            await interaction.followup.send(f"Generating video for your prompt:...")
            request_id = await self._fal_ai_submit_video_request(query)
            result_data = await self._fal_ai_poll_for_video_result(request_id)  
            video_url = result_data["video"]["url"]
            video_content = requests.get(video_url).content
            video_file = discord.File(io.BytesIO(video_content), filename="generated_video.mp4")

            await interaction.followup.send(
                content=f"<@{user_id}> Your video is ready!\n`PROMPT:` **{query}**", 
                file=video_file
            )

        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(
                f":x: There was an error generating the video: {str(e)}")