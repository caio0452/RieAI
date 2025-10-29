import discord
import logging
import reynard_ai.util.logging_setup as logs

from dotenv import load_dotenv
from discord.ext import commands
from commands.sync_command_tree import SyncCommand
from commands.image_gen_command import ImageGenCommand
from commands.video_gen_command import VideoGenCommand

from reynard_ai.bot_data.ai_bot import AIBot
from reynard_ai.bot_data.bot_profile import Profile
from reynard_ai.ai_apis.providers import ProviderDataStore
from reynard_ai.chat.base_chat_handler import AsyncEventBus
from reynard_ai.chat.discord_events_bridge import DiscordBridge
from reynard_ai.util.environment_vars import get_environment_var
from reynard_ai.chat.discord_chat_handler import DiscordChatHandler
from reynard_ai.bot_data.knowledge import KnowledgeIndex, LongTermMemoryIndex

logs.setup()
load_dotenv()

class DiscordBot:
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix='r!', intents=intents)
        self.profile = Profile.from_file("profile.json")
        self.bot.event(self.on_ready)
        self.ai_bot_data: AIBot | None = None

    def run(self):
        bot_token = get_environment_var('AI_BOT_TOKEN', required=True)
        self.bot.run(bot_token)

    async def setup_chatbot(self):
        embeddings_provider = self.profile.providers["EMBEDDINGS"]
        self.knowledge = await KnowledgeIndex.from_provider(embeddings_provider)
        if self.profile.memory_settings.enable_long_term_memory:
            self.long_term_memory: LongTermMemoryIndex | None = await LongTermMemoryIndex.from_provider(embeddings_provider)
        else:
            self.long_term_memory = None

        provider_list = [self.profile.providers[k] for k, v in self.profile.providers.items()]
        provider_store = ProviderDataStore(
            providers=provider_list
        ) # TODO: There should be required providers
        if self.bot.user is None:
            raise RuntimeError("Could not initialize bot: bot user is None")
        event_bus = AsyncEventBus()
        bridge = DiscordBridge(self.bot, bus=event_bus, known_chatrooms=[])
        await self.bot.add_cog(
            bridge,
        )
        self.ai_bot_data = AIBot(
            name=self.profile.options.botname, 
            profile=self.profile, 
            provider_store=provider_store,
            long_term_memory=self.long_term_memory,
            knowledge=self.knowledge,
            account_id=self.bot.user.id,
            memory_length=50            
        )
        self.chat_handler = DiscordChatHandler(
            event_bus, 
            self.ai_bot_data
        )
        event_bus.start()

    async def setup_commands(self):
        await self.bot.add_cog(SyncCommand(bot=self.bot))
        
        if bot.profile.fal_image_gen_config.enabled:
            await self.bot.add_cog(ImageGenCommand(discord_bot=self.bot, bot_profile=self.profile))
            await self.bot.add_cog(VideoGenCommand(discord_bot=self.bot, bot_profile=self.profile))
        else:
            logging.info("Image generation using FAL.AI is disabled")
    

    async def on_ready(self):
        logging.info("Creating chatbot...")
        await self.setup_chatbot()
        logging.info("Setting up commands...")
        await self.setup_commands()
        logging.info("Indexing knowledge...")
        await self.knowledge.index_from_folder("brain_content/knowledge")
        logging.info(f'Logged in as {self.bot.user}')

bot = DiscordBot()
bot.run()