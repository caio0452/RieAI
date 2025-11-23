import io
import json
import httpx
import base64
import discord
import traceback

from discord.ext import commands
from typing import Callable, Optional
from reynard_ai.bot_data.bot_profile import Profile
from reynard_ai.util.rate_limits import RateLimit, RateLimiter
from reynard_ai.ai_apis.client import LLMClient, LLMRequestParams

class BaseFalCommand(commands.Cog):
    def __init__(self, discord_bot: commands.Bot, bot_profile: Profile, rate_limit: RateLimit) -> None:
        self.discord_bot = discord_bot
        self.bot_profile = bot_profile
        self.fal_config = bot_profile.fal_image_gen_config 
        self.rate_limiter = RateLimiter(rate_limit)

    async def _is_blocked_prompt(self, prompt: str) -> bool:
        blocked_words = ["nsfw", "naked", "bikini", "lingerie", "sexy", "penis", "fuck", "murder", "blood"]
        NAME = "NSFW_IMAGE_PROMPT_FILTER"
        
        for word in blocked_words:
            if word in prompt:
                return True

        try:
            nsfw_filter_prompt = self.bot_profile.prompts[NAME]
            nsfw_filter_provider = self.bot_profile.providers[NAME]
            nsfw_filter_llm = LLMClient.from_provider(nsfw_filter_provider)

            response = await nsfw_filter_llm.send_request(
                prompt=nsfw_filter_prompt,
                params=LLMRequestParams(model_name="gpt-4o-mini", temperature=0)
            )
            response_data = json.loads(response.message.content)

            if (response_data.get("mentions_sexual_content") or 
                response_data.get("violent_content") == "high" or 
                response_data.get("graphic_content") == "high"):
                return True
        except Exception:
            print("Error in NSFW LLM check")
            pass
        
        return False

    async def _download_media(self, url: str, filename: str) -> discord.File:
        if url.startswith("data:image"):
            header, encoded = url.split(",", 1)
            data = base64.b64decode(encoded)
            return discord.File(io.BytesIO(data), filename=filename)
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return discord.File(io.BytesIO(resp.content), filename=filename)

    async def _execute_generation(
        self, 
        interaction: discord.Interaction, 
        prompt: str, 
        generation_coroutine: Callable,
        success_message: Optional[str] = None
    ) -> None:
        user_id = interaction.user.id
        await interaction.response.defer()

        try:
            if await self._is_blocked_prompt(prompt):
                await interaction.followup.send(":x: Prompt flagged as inappropriate.")
                return

            if self.rate_limiter.is_rate_limited(user_id):
                first_limit = self.rate_limiter.limits[0]
                await interaction.followup.send(f":x: You are being rate limited ({first_limit.n_messages} / {first_limit.seconds}s).")
                return
            
            self.rate_limiter.register_request(user_id)
            result_file = await generation_coroutine()
            msg_content = success_message if success_message else f"`PROMPT:` **{prompt}**"
            await interaction.followup.send(content=msg_content, file=result_file)

        except Exception as e:
            traceback.print_exc()
            error_msg = str(e)[:1800]
            await interaction.followup.send(f":x: There was an error generating content: {error_msg}")
