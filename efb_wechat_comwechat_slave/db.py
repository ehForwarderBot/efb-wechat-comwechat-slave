import logging

from peewee import (
    CharField,
    DoesNotExist,
    Model,
    TextField,
)
from playhouse.sqliteq import SqliteQueueDatabase
from ehforwarderbot import utils

database = SqliteQueueDatabase(None, autostart=False)


class BaseModel(Model):
    class Meta:
        database = database


class GroupChatInfo(BaseModel):
    group_uid = CharField()
    wxid = CharField()
    group_alias = TextField()

    class Meta:
        indexes = (
            (('group_uid', 'wxid'), True),  # Unique index on group_uid and wxid
        )


class DatabaseManager:
    logger = logging.getLogger(__name__)

    def __init__(self, channel: "ComWeChatChannel"):
        base_path = utils.get_data_path(channel.channel_id)

        self.logger.debug("Loading database...")
        database.init(str(base_path / "wxdata.db"))
        database.start()
        database.connect()
        self.logger.debug("Database loaded.")

        self.logger.debug("Checking database migration...")
        self._create()
        self.logger.debug("Database migration finished...")

    def stop_worker(self):
        database.stop()

    @staticmethod
    def _create():
        """
        Initializing tables.
        """
        database.create_tables([GroupChatInfo], safe=True)

    @staticmethod
    def get_all_group_aliases():
        return list(GroupChatInfo.select())

    @staticmethod
    def update_group_alias(group_uid, wxid, alias):
        return GroupChatInfo.replace(
            group_uid = group_uid,
            wxid = wxid,
            group_alias = alias,
        ).execute()
