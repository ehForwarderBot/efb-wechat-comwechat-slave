# coding: utf-8
import contextlib
import logging
from typing import Dict, Optional, List

from ehforwarderbot.channel import SlaveChannel
from ehforwarderbot.chat import GroupChat, PrivateChat, ChatMember, SystemChat

from .CustomTypes import EFBGroupChat, EFBGroupMember, EFBPrivateChat, EFBSystemUser

logger = logging.getLogger(__name__)


class ChatMgr:
    slave_channel = None

    @staticmethod
    def build_efb_chat_as_group(group: EFBGroupChat,
                                members: Optional[List[EFBGroupMember]] = None) -> GroupChat:
        """
        Build EFB GroupChat object from EFBGroupChat Dict
        :return: GroupChat from group_id
        :param group: EFBGroupChat object, see CustomTypes.py
        :param members: Optional, the member list for the specific group, None by default
                        Each object in members (if not None) must follow the syntax of GroupChat.add_members
        """
        efb_chat: GroupChat = GroupChat(
            channel=ChatMgr.slave_channel,
            **group
        )
        if members:
            for member in members:
                efb_chat.add_member(
                    **member
                )
        return efb_chat

    @staticmethod
    def build_efb_chat_as_private(private: EFBPrivateChat) -> PrivateChat:
        """
        Build EFB PrivateChat object from EFBPrivateChat
        :return: GroupChat from group_id
        :param private: EFBPrivateChat object, see CustomTypes.py
        """
        efb_chat: PrivateChat = PrivateChat(
            channel=ChatMgr.slave_channel,
            **private
        )
        return efb_chat

    @staticmethod
    def build_efb_chat_as_member(chat: GroupChat, member: EFBGroupMember) -> ChatMember:
        """
        Build EFB ChatMember object from GroupChat and EFBGroupMember.
        It'll try to get member from GroupChat, if one is not found then a new member is added.
        :param chat: Original GroupChat
        :param member: EFBGroupMember object, see CustomTypes.py
        :return: Newly built ChatMember
        """
        with contextlib.suppress(KeyError):
            return chat.get_member(str(member.get('uid', '')))
        efb_chat: ChatMember = chat.add_member(
            **member
        )
        return efb_chat

    @staticmethod
    def build_efb_chat_as_system_user(chat: EFBSystemUser):
        return SystemChat(channel=ChatMgr.slave_channel,
                          **chat)