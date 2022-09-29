import logging, tempfile
import threading
from traceback import print_exc
from pydub import AudioSegment
import qrcode
import os

import re
import time
from ehforwarderbot.chat import PrivateChat , SystemChatMember
from typing import Optional, Collection, BinaryIO, Dict, Any , Union , List
from datetime import datetime
from cachetools import TTLCache

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
from .Utils import download_file , load_config , load_temp_file_to_local , WC_EMOTICON_CONVERSION

class ComWeChatChannel(SlaveChannel):
    channel_name : str = "ComWechatChannel"
    channel_emoji : str = "💻"
    channel_id : str = "honus.comwechat"

    bot : WeChatRobot = None
    config : Dict = {}

    friends : EFBPrivateChat = []
    groups : EFBGroupChat    = []

    contacts : Dict = {}            # {wxid : {alias : str , remark : str, nickname : str , type : int}} -> {wxid : name(after handle)}
    group_members : Dict = {}       # {"group_id" : { "wxID" : "displayName"}}
    
    cache =  TTLCache(maxsize=100, ttl=300)  # 缓存发送过的消息ID
    file_msg : Dict = {}                     # 存储待修改的文件类消息 {path : msg}

    __version__ = version.__version__
    logger: logging.Logger = logging.getLogger("comwechat")
    logger.setLevel(logging.DEBUG)

    # MsgType.File , MsgType.Video
    supported_message_types = {MsgType.Text, MsgType.Sticker, MsgType.Image,
        MsgType.Link, MsgType.Voice, MsgType.Animation}

    def __init__(self, instance_id: InstanceID = None):
        super().__init__(instance_id=instance_id)
        self.logger.info("ComWeChat Slave Channel initialized.")
        self.logger.info("Version: %s" % self.__version__)
        self.config = load_config(efb_utils.get_config_path(self.channel_id))
        self.dir = self.config["dir"]
        self.bot = WeChatRobot()
        self.base_path = self.bot.get_base_path()
        ChatMgr.slave_channel = self

        @self.bot.on("self_msg")
        def on_self_msg(msg : Dict):
            self.logger.debug(f"self_msg:{msg}")
            sender = msg["sender"]

            name = self.contacts[sender] if self.contacts[sender] else sender
            if "@chatroom" in sender:
                chat = ChatMgr.build_efb_chat_as_group(EFBGroupChat(
                    uid = sender,
                    name = name,
                ))
                author = chat.self
            else:
                chat = ChatMgr.build_efb_chat_as_private(EFBPrivateChat(
                    uid = sender,
                    name = name,
                ))
                author = chat.self

            self.handle_msg(msg , author , chat)

        @self.bot.on("friend_msg")
        def on_friend_msg(msg : Dict):
            self.logger.debug(f"friend_msg:{msg}")
            sender = msg['sender']

            if sender == "":  #eventnotify
                return
            name = self.contacts[sender] if self.contacts[sender] else sender
            chat = ChatMgr.build_efb_chat_as_private(EFBPrivateChat(
                    uid= sender,
                    name= name,
            ))
            author = chat.other
            self.handle_msg(msg, author, chat)
            
        @self.bot.on("group_msg")
        def on_group_msg(msg : Dict):
            self.logger.debug(f"group_msg:{msg}")
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

        # @self.bot.on("public_msg")
        # def on_public_msg(msg : Dict):
        #     self.logger.debug(f"public_msg:{msg}")
        #     ...

    def handle_msg(self , msg : Dict[str, Any] , author : 'ChatMember' , chat : 'Chat'):
        efb_msgs = []

        emojiList = re.findall('\[[\w|！|!| ]+\]' , msg["message"])
        for emoji in emojiList:
            try:
                msg["message"] = msg["message"].replace(emoji, WC_EMOTICON_CONVERSION[emoji])
            except:
                pass
        
        try:
            if "FileStorage" in msg["filepath"]:
                if msg["msgid"] not in self.cache:
                    self.cache[msg["msgid"]] = None
                else:
                    return
                msg["timestamp"] = int(time.time())
                msg["filepath"] = msg["filepath"].replace("\\","/")
                msg["filepath"] = f'''{self.dir}{msg["filepath"]}'''
                self.file_msg[msg["filepath"]] = ( msg , author , chat )
                return
        except:
            ...

        if msg["type"] == "voice":
            file_path = re.search("clientmsgid=\"(.*?)\"", msg["message"]).group(1) + ".amr"
            msg["filepath"] = f'''{self.dir}{msg["self"]}/{file_path}'''
            self.file_msg[msg["filepath"]] = ( msg , author , chat )
            return

        efb_msg = MsgProcess(msg , chat)
        efb_msg.author = author
        efb_msg.chat = chat
        efb_msg.uid = msg["msgid"]
        efb_msg.deliver_to = coordinator.master
        coordinator.send_message(efb_msg)
        if efb_msg.file:
            efb_msg.file.close()

    def handle_file_msg(self):
        while True:
            if len(self.file_msg) == 0:
                time.sleep(1)
                continue
            else:
                for path in list(self.file_msg.keys()):
                    flag = False
                    msg = self.file_msg[path][0]
                    author = self.file_msg[path][1]
                    chat = self.file_msg[path][2]
                    if os.path.exists(path):
                        flag = True
                    else:
                        if (int(time.time()) - msg["timestamp"]) > 60:
                            msg['message'] = "文件下载超时,请在手机端查看"
                            msg["type"] = "text"
                            flag = True
                    
                    if flag:
                        del self.file_msg[path]
                        efb_msg = MsgProcess(msg , chat)
                        efb_msg.author = author
                        efb_msg.chat = chat
                        efb_msg.uid = msg["msgid"]
                        efb_msg.deliver_to = coordinator.master
                        coordinator.send_message(efb_msg)
                        if efb_msg.file:
                            efb_msg.file.close()
                    time.sleep(0.5)

    # 定时任务
    def scheduled_job(self , t_event):
        interval = 1800
        
        self.GetGroupListBySql()
        self.GetContactListBySql()

        if t_event is not None and not t_event.is_set():
            self.scheduled_job = threading.Timer(interval, self.scheduled_job, [t_event])
            self.scheduled_job.start()

    #获取全部联系人
    def get_chats(self) -> Collection['Chat']:
        if not self.friends and not self.groups:
            self.GetContactListBySql()
        return self.groups + self.friends

    #获取联系人
    def get_chat(self, chat_uid: ChatID) -> 'Chat':
        if not self.friends and not self.groups:
            self.GetContactListBySql()
        
        if "@chatroom" in chat_uid:
            for group in self.groups:
                if group.uid == chat_uid:
                    return group
        else:
            for friend in self.friends:
                if friend.uid == chat_uid:
                    return friend

    #发送消息
    def send_message(self, msg : Message) -> Message:
        chat_uid = msg.chat.uid

        if msg.edit:
            pass  # todo
        
        if msg.type in [MsgType.Text , MsgType.Link]:
            self.bot.SendText(wxid = chat_uid , msg = msg.text)
        elif msg.type in [MsgType.Image , MsgType.Sticker]:
            name = msg.file.name.replace("/tmp/", "")
            local_path = f"{self.dir}{name}"
            load_temp_file_to_local(msg.file, local_path)
            img_path = self.base_path + "\\" + local_path.split("/")[-1]
            self.bot.SendImage(receiver = chat_uid , img_path = img_path)
            try:
                os.remove(img_path)
            except:
                ...
        elif msg.type in [MsgType.File , MsgType.Video]:
            ...
            # name = msg.file.name.replace("/tmp/", "")
            # local_path = f"{self.dir}{name}"
            # load_temp_file_to_local(msg.file, local_path)
            # file_path = self.base_path + "\\" +local_path.split("/")[-1]
            # self.bot.SendFile(receiver = chat_uid , file_path = file_path)
            # try:
            #     os.remove(file_path)
            # except:
            #     ...
        return msg

    def get_chat_picture(self, chat: 'Chat') -> BinaryIO:
        wxid = chat.uid
        result = self.bot.GetPictureBySql(wxid = wxid)
        if result:
            return download_file(result['data'][1][1])
        else:
            return None

    def poll(self):
        timer = threading.Event()
        self.scheduled_job(timer)

        self.bot.run(main_thread = False)

        t = threading.Thread(target = self.handle_file_msg)
        t.daemon = True
        t.start()

    def send_status(self, status: 'Status'):
        pass

    def stop_polling(self):
        pass

    def get_message_by_id(self, chat: 'Chat', msg_id: MessageID) -> Optional['Message']:
        pass

    #定时更新 Start
    def GetContactListBySql(self):
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

    def GetGroupListBySql(self):
        self.group_members = self.bot.GetAllGroupMembersBySql()
    #定时更新 End

    