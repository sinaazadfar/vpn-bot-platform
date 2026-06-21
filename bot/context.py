from dataclasses import dataclass

from bot.config import Settings
from bot.db import Database
from bot.marzban import MarzbanClient


@dataclass(slots=True)
class AppContext:
    settings: Settings
    database: Database
    marzban: MarzbanClient
