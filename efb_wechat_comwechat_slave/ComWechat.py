import logging, tempfile
import threading
from traceback import print_exc
from pydub import AudioSegment
import qrcode

import re
import time
from ehforwarderbot.chat import PrivateChat , SystemChatMember
from typing import Optional, Collection, BinaryIO, Dict, Any , Union
from datetime import datetime

from ehforwarderbot import MsgType, Chat, Message, Status, coordinator
from wechatrobot import WeChatRobot

from . import __version__ as version

from ehforwarderbot.channel import SlaveChannel
from ehforwarderbot.types import MessageID, ChatID, InstanceID
from ehforwarderbot import utils as efb_utils
from ehforwarderbot.exceptions import EFBException
from ehforwarderbot.message import MessageCommand, MessageCommands

from .ChatMgr import ChatMgr
from .CustomTypes import EFBGroupChat, EFBPrivateChat, EFBGroupMember
from .MsgDeco import efb_text_simple_wrapper
from .MsgProcess import MsgProcess
from .Utils import download_file , emoji_telegram2wechat , emoji_wechat2telegram , load_config

TYPE_HANDLERS = {
    'text'              : MsgProcess.text_msg,
    'image'             : MsgProcess.image_msg,
    'video'             : MsgProcess.video_msg,
    'voice'             : MsgProcess.voice_msg,
    'qqmail'            : MsgProcess.qqmail_msg,
    'share'             : MsgProcess.share_link_msg,
    'location'          : MsgProcess.location_msg,
    'other'             : MsgProcess.other_msg,
    'animatedsticker'   : MsgProcess.image_msg,
    'unsupported'       : MsgProcess.unsupported_msg,
    'revokemsg'         : MsgProcess.revoke_msg,
    'file'              : MsgProcess.file_msg,
    'transfer'          : MsgProcess.transfer_msg,
    'groupannouncement' : MsgProcess.group_announcement_msg,
    'eventnotify'       : MsgProcess.event_notify_msg,
    'miniprogram'       : MsgProcess.miniprogram_msg,
    'scancashmoney'     : MsgProcess.scanmoney_msg,
}

class ComWeChatChannel(SlaveChannel):
    channel_name : str = "ComWechatChannel"
    channel_emoji : str = "💻"
    channel_id : str = "honus.comwechat"

    config : Dict = {}

    friends : EFBPrivateChat = []
    groups : EFBGroupChat    = []

    contacts : Dict = {}            # {wxid : {alias : str , remark : str, nickname : str , type : int}} -> {wxid : name(after handle)}
    group_members : Dict = {}       # {"group_id" : { "wxID" : "displayName"}}

    __version__ = version.__version__
    logger: logging.Logger = logging.getLogger("comwechat")
    logger.setLevel(logging.DEBUG)
    supported_message_types = {MsgType.Text, MsgType.Sticker, MsgType.Image, MsgType.Video,
        MsgType.File, MsgType.Link, MsgType.Voice, MsgType.Animation}

    def __init__(self, instance_id: InstanceID = None):
        super().__init__(instance_id=instance_id)
        self.logger.info("ComWeChat Slave Channel initialized.")
        self.logger.info("Version: %s" % self.__version__)
        self.config = load_config(efb_utils.get_config_path(self.channel_id))
        self.bot = WeChatRobot()
        ChatMgr.slave_channel = self

        @self.bot.on("self_msg")
        def on_self_msg(msg : Dict):
            self.logger.debug(msg)
            ...

        @self.bot.on("friend_msg")
        def on_friend_msg(msg : Dict):
            self.logger.debug(msg)
            sender = msg['sender']

            name = self.contacts[sender] if self.contacts[sender] else sender
            chat = ChatMgr.build_efb_chat_as_private(EFBPrivateChat(
                    uid= sender,
                    name= name,
            ))
            author = chat.other
            self.handle_msg(msg, author, chat)
            

        @self.bot.on("group_msg")
        def on_group_msg(msg : Dict):
            self.logger.debug(msg)
            sender = msg["sender"]
            wxid  =  msg["wxid"] 

            chatname = self.contacts[sender] if self.contacts[sender] else sender
            chat = ChatMgr.build_efb_chat_as_group(EFBGroupChat(
                uid = sender,
                name = chatname,
            ))

            author = ChatMgr.build_efb_chat_as_member(chat, EFBGroupMember(
                uid = wxid,
                name = self.contacts[wxid] if self.contacts[wxid] else wxid,
                alias = self.group_members.get(sender,{}).get(wxid , None),
            ))
            self.handle_msg(msg, author, chat)

        @self.bot.on("public_msg")
        def on_public_msg(msg : Dict):
            self.logger.debug(msg)
            ...

    def handle_msg(self , msg : Dict[str, Any] , author : 'ChatMember' , chat : 'Chat'):
        efb_msgs = []

        efb_msgs.append(TYPE_HANDLERS['text'](msg , chat))

        for efb_msg in efb_msgs:
            efb_msg.author = author
            efb_msg.chat = chat
            efb_msg.uid = msg["msgid"]
            efb_msg.deliver_to = coordinator.master
            coordinator.send_message(efb_msg)
            if efb_msg.file:
                efb_msg.file.close()


    #获取全部联系人
    def get_chats(self) -> Collection['Chat']:
        if not self.friends:
            self.GetContactList()
        return self.groups + self.friends

    #获取联系人
    def get_chat(self, chat_uid: ChatID) -> 'Chat':
        if not self.contacts:
            self.GetContactList()
        
        if "@chatroom" in chat_uid:
            for group in self.groups:
                if group.uid == chat_uid:
                    return group
        else:
            for friend in self.friends:
                if friend.uid == chat_uid:
                    return friend
        ...

    #发送消息
    def send_message(self, msg : Message) -> Message:
        chat_uid = msg.chat.uid

        if msg.edit:
            pass  # todo
        
        if msg.type in [MsgType.Text , MsgType.Link]:
            self.bot.SendText(wxid = chat_uid , msg = msg.text)

        return msg

    def get_chat_picture(self, chat: 'Chat') -> BinaryIO:
        wxid = chat.uid
        result = self.bot.GetPictureBySql(wxid = wxid)
        if result:
            return download_file(result['data'][1][1])
        else:
            return None

    def poll(self):
        self.bot.run(main_thread = False)

    def send_status(self, status: 'Status'):
        pass

    def stop_polling(self):
        pass

    def get_message_by_id(self, chat: 'Chat', msg_id: MessageID) -> Optional['Message']:
        pass

    #定时更新 Start
    def GetContactList(self):
        self.groups = []
        self.friends = []
        contacts = self.bot.GetContactListBySql()
        for contact in contacts:
            data = contacts[contact]
            name = (f"{data['remark']}({data['nickname']})") if data["remark"] else data["nickname"]

            self.contacts[contact] = name
            if data["type"] == 0 or data["type"] == 4 or name == "":
                continue

            if "@chatroom" in contact:
                new_entity = EFBGroupChat(
                    uid=contact,
                    name=name
                )
                self.groups.append(ChatMgr.build_efb_chat_as_group(new_entity))
            else:
                new_entity = EFBPrivateChat(
                    uid=contact,
                    name=name
                )
                self.friends.append(ChatMgr.build_efb_chat_as_private(new_entity))
            

    def GetGroupList(self):
        self.group_members = self.bot.GetAllGroupMembersBySql()
    #定时更新 End

        

# ['wxid_t7ff4y937bqm22', 'Majinchuan-Snoopy', '马进川', '执念']
# ['19259553564@chatroom', '', '', '软件五科']

    