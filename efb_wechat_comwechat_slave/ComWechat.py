import logging, tempfile
import time
import threading
from traceback import print_exc
from pydub import AudioSegment
# import qrcode TODO
import os

import re
import time
import json
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
from ehforwarderbot.status import MessageRemoval

from .ChatMgr import ChatMgr
from .CustomTypes import EFBGroupChat, EFBPrivateChat, EFBGroupMember, EFBSystemUser
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
    
    time_out : int = 120
    cache =  TTLCache(maxsize=200, ttl= time_out)  # 缓存发送过的消息ID
    file_msg : Dict = {}                           # 存储待修改的文件类消息 {path : msg}
    delete_file : Dict = {}                        # 存储待删除的消息 {path : time}

    __version__ = version.__version__
    logger: logging.Logger = logging.getLogger("comwechat")
    logger.setLevel(logging.DEBUG)

    #MsgType.Voice
    supported_message_types = {MsgType.Text, MsgType.Sticker, MsgType.Image , MsgType.Link , MsgType.File , MsgType.Video , MsgType.Animation, MsgType.Voice}

    def __init__(self, instance_id: InstanceID = None):
        super().__init__(instance_id=instance_id)
        self.logger.info("ComWeChat Slave Channel initialized.")
        self.logger.info("Version: %s" % self.__version__)
        self.config = load_config(efb_utils.get_config_path(self.channel_id))
        self.dir = self.config["dir"]
        self.bot = WeChatRobot()
        self.wxid = self.bot.GetSelfInfo()["data"]["wxId"]
        self.base_path = self.bot.get_base_path()
        ChatMgr.slave_channel = self

        @self.bot.on("self_msg")
        def on_self_msg(msg : Dict):
            self.logger.debug(f"self_msg:{msg}")
            sender = msg["sender"]

            try:
                name = self.contacts[sender] if self.contacts[sender] else sender
            except:
                data = self.bot.GetContactBySql(wxid = sender)
                if data:
                    name = data[3]
                    if name == "":
                        name = sender
                else:
                    name = sender

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
                if sender.startswith('gh_'):
                    chat.vendor_specific = {'is_mp' : True}
                author = chat.self

            self.handle_msg(msg , author , chat)

        @self.bot.on("friend_msg")
        def on_friend_msg(msg : Dict):
            self.logger.debug(f"friend_msg:{msg}")
            sender = msg['sender']

            try:
                name = self.contacts[sender]
            except KeyError:
                data = self.bot.GetContactBySql(wxid = sender)
                if data:
                    name = data[3]
                    if name == "":
                        name = sender
                else:
                    name = sender

            chat = ChatMgr.build_efb_chat_as_private(EFBPrivateChat(
                    uid= sender,
                    name= name,
            ))
            if sender.startswith('gh_'):
                chat.vendor_specific = {'is_mp' : True}
                self.logger.debug(f'modified_chat:{chat}')
            author = chat.other
            self.handle_msg(msg, author, chat)
            
        @self.bot.on("group_msg")
        def on_group_msg(msg : Dict):
            self.logger.debug(f"group_msg:{msg}")
            sender = msg["sender"]
            wxid  =  msg["wxid"] 

            if sender in self.contacts.keys():
                chatname = self.contacts[sender]
                if chatname == "":
                    chatname = sender
            else:
                chatname = sender
                
            chat = ChatMgr.build_efb_chat_as_group(EFBGroupChat(
                uid = sender,
                name = chatname,
            ))

            try:
                name = self.contacts[wxid]
            except:
                name = wxid

            author = ChatMgr.build_efb_chat_as_member(chat, EFBGroupMember(
                uid = wxid,
                name = name,
                alias = self.group_members.get(sender,{}).get(wxid , None),
            ))
            self.handle_msg(msg, author, chat)

        @self.bot.on("revoke_msg")
        def on_revoked_msg(msg : Dict):
            self.logger.debug(f"revoke_msg:{msg}")
            sender = msg["sender"]
            if "@chatroom" in sender:
                wxid  =  msg["wxid"] 

            if sender in self.contacts.keys():
                chatname = self.contacts[sender]
                if chatname == "":
                    chatname = sender
            else:
                chatname = sender

            if "@chatroom" in sender:
                chat = ChatMgr.build_efb_chat_as_group(EFBGroupChat(
                    uid = sender,
                    name = chatname,
                ))
            else:
                chat = ChatMgr.build_efb_chat_as_private(EFBPrivateChat(
                    uid = sender,
                    name = chatname,
                ))

            newmsgid = re.search("<newmsgid>(.*?)<\/newmsgid>", msg["message"]).group(1)

            efb_msg = Message(chat = chat , uid = newmsgid)
            coordinator.send_status(
                MessageRemoval(source_channel=self, destination_channel=coordinator.master, message=efb_msg)
            )

    def system_msg(self, msg):
        self.logger.debug(f"system_msg:{msg}")
        sender = msg["sender"]
        name  = '\u2139 System' 
        msg["msgid"] = int(time.time())

        chat = ChatMgr.build_efb_chat_as_system_user(EFBSystemUser(
            uid = sender,
            name = name
        ))

        try:
            author = chat.get_member(SystemChatMember.SYSTEM_ID)
        except KeyError:
            author = chat.add_system_member()

        self.handle_msg(msg, author, chat)

    def handle_msg(self , msg : Dict[str, Any] , author : 'ChatMember' , chat : 'Chat'):
        efb_msgs = []

        emojiList = re.findall('\[[\w|！|!| ]+\]' , msg["message"])
        for emoji in emojiList:
            try:
                msg["message"] = msg["message"].replace(emoji, WC_EMOTICON_CONVERSION[emoji])
            except:
                pass

        if msg["msgid"] not in self.cache:
            self.cache[msg["msgid"]] = None
        else:
            return

        try:
            if ("FileStorage" in msg["filepath"]) and ("Cache" not in msg["filepath"]):
                msg["timestamp"] = int(time.time())
                msg["filepath"] = msg["filepath"].replace("\\","/")
                msg["filepath"] = f'''{self.dir}{msg["filepath"]}'''
                self.file_msg[msg["filepath"]] = ( msg , author , chat )
                return
            if msg["type"] == "video":
                msg["timestamp"] = int(time.time())
                msg["filepath"] = msg["thumb_path"].replace("\\","/").replace(".jpg", ".mp4")
                msg["filepath"] = f'''{self.dir}{msg["filepath"]}'''
                self.file_msg[msg["filepath"]] = ( msg , author , chat )
                return
        except:
            ...

        if msg["type"] == "voice":
            file_path = re.search("clientmsgid=\"(.*?)\"", msg["message"]).group(1) + ".amr"
            msg["timestamp"] = int(time.time())
            msg["filepath"] = f'''{self.dir}{msg["self"]}/{file_path}'''
            self.file_msg[msg["filepath"]] = ( msg , author , chat )
            return

        efb_msg = MsgProcess(msg , chat)
        if not efb_msg:
            return
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
            else:
                for path in list(self.file_msg.keys()):
                    flag = False
                    msg = self.file_msg[path][0]
                    author = self.file_msg[path][1]
                    chat = self.file_msg[path][2]
                    if os.path.exists(path):
                        flag = True
                    else:
                        if (int(time.time()) - msg["timestamp"]) > self.time_out:
                            msg_type = msg["type"]
                            msg['message'] = f"[{msg_type} 下载超时,请在手机端查看]"
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

            if len(self.delete_file):
                for k in list(self.delete_file.keys()):
                    file_path = k
                    begin_time = self.delete_file[k]
                    if  (int(time.time()) - begin_time) > self.time_out:
                        try:
                            os.remove(file_path)
                        except:
                            pass
                        del self.delete_file[file_path]  

    # 定时任务
    def scheduled_job(self):
        count = 1
        while True: 
            time.sleep(1)
            if count % 1800 == 0:
                self.GetGroupListBySql()
                self.GetContactListBySql()
                count = 1
            else:
                count += 1

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
            pass     # todo

        if msg.type == MsgType.Voice:
            f = tempfile.NamedTemporaryFile(prefix='voice_message_', suffix=".mp3")
            AudioSegment.from_ogg(msg.file.name).export(f, format="mp3")
            msg.file = f
            msg.file.name = f.name
            msg.type = MsgType.Video
            msg.filename = f.name.split("/")[-1]
        
        if msg.type in [MsgType.Text]:
            if msg.text.startswith('/changename'):
                newname = msg.text.strip('/changename ')
                res = self.bot.SetChatroomName(chatroom_id = chat_uid , chatroom_name = newname)
            elif msg.text.startswith('/getmemberlist'):
                memberlist = self.bot.GetChatroomMemberList(chatroom_id = chat_uid)
                message = '群组成员包括：'
                for wxid in memberlist['members'].split('^G'):
                    try:
                        name = self.contacts[wxid]
                    except:
                        try:
                            name = self.bot.GetChatroomMemberNickname(chatroom_id = chat_uid, wxid = wxid)
                        except:
                            name = wxid
                    message += '\n' + wxid + ' : ' + name
                self.system_msg({'sender':chat_uid, 'type':'text', 'message':message})
            elif msg.text.startswith('/getstaticinfo'):
                info = msg.text[15::]
                if info == 'friends':
                    message = str(self.friends)
                elif info == 'groups':
                    message = str(self.groups)
                elif info == 'group_members':
                    message = json.dumps(self.group_members)
                elif info == 'contacts':
                    message = json.dumps(self.contacts)
                else:
                    message = '当前仅支持查询friends, groups, group_members, contacts'
                self.system_msg({'sender':chat_uid, 'type':'text', 'message':message})
            elif msg.text.startswith('/search'):
                keyword = msg.text[8::]
                message = 'result:'
                for key, value in self.contacts.items():
                    if keyword in value:
                        message += '\n' + str(key) + " : " + str(value)
                self.system_msg({'sender':chat_uid, 'type':'text', 'message':message})
            elif msg.text.startswith('/addtogroup'):
                users = msg.text[12::]
                res = self.bot.AddChatroomMember(chatroom_id = chat_uid, wxids = users)
            elif msg.text.startswith('/at'):
                users = msg.text[4::]
                res = self.bot.SendAt(chatroom_id = chat_uid, wxids = users, msg = '')
            else:
                res = self.bot.SendText(wxid = chat_uid , msg = msg.text)
        elif msg.type in [MsgType.Link]:
            self.bot.SendText(wxid = chat_uid , msg = msg.text)
        elif msg.type in [MsgType.Image , MsgType.Sticker]:
            name = msg.file.name.replace("/tmp/", "")
            local_path =f"{self.dir}{self.wxid}/{name}"
            load_temp_file_to_local(msg.file, local_path)
            img_path = self.base_path + "\\" + self.wxid + "\\" + local_path.split("/")[-1]
            res = self.bot.SendImage(receiver = chat_uid , img_path = img_path)
            self.delete_file[local_path] = int(time.time())
        elif msg.type in [MsgType.File , MsgType.Video]:
            name = msg.file.name.replace("/tmp/", "")
            local_path = f"{self.dir}{self.wxid}/{name}"
            load_temp_file_to_local(msg.file, local_path)
            file_path = self.base_path + "\\" + self.wxid + "\\" + local_path.split("/")[-1]
            if msg.filename:
                os.rename(local_path , f"{self.dir}{self.wxid}/{msg.filename}")
                local_path = f"{self.dir}{self.wxid}/{msg.filename}"
                file_path = self.base_path + "\\" + self.wxid + "\\" + msg.filename
            res = self.bot.SendFile(receiver = chat_uid , file_path = file_path)                   # {'msg': 0, 'result': 'OK'} SendFail
            self.delete_file[local_path] = int(time.time())
        elif msg.type in [MsgType.Animation]:
            name = msg.file.name.replace("/tmp/", "")
            local_path = f"{self.dir}{self.wxid}/{name}"
            load_temp_file_to_local(msg.file, local_path)
            file_path = self.base_path + "\\" + self.wxid + "\\" + local_path.split("/")[-1]
            res = self.bot.SendEmotion(wxid = chat_uid , img_path = file_path)
            self.delete_file[local_path] = int(time.time())

        try:
            if str(res["msg"]) == "0":
                self.system_msg({'sender':chat_uid, 'type':'text', 'message':"发送失败，请在手机端确认"})
        except:
            ...
        return msg

    def get_chat_picture(self, chat: 'Chat') -> BinaryIO:
        wxid = chat.uid
        result = self.bot.GetPictureBySql(wxid = wxid)
        if result:
            return download_file(result)
        else:
            return None

    def poll(self):
        timer = threading.Thread(target = self.scheduled_job)
        timer.daemon = True
        timer.start()

        self.bot.run(main_thread = False)

        t = threading.Thread(target = self.handle_file_msg)
        t.daemon = True
        t.start()

    def send_status(self, status: 'Status'):
        ...

    def stop_polling(self):
        ...

    def get_message_by_id(self, chat: 'Chat', msg_id: MessageID) -> Optional['Message']:
        ...

    #定时更新 Start
    def GetContactListBySql(self):
        self.groups = []
        self.friends = []
        contacts = self.bot.GetContactListBySql()
        for contact in contacts:
            data = contacts[contact]
            name = (f"{data['remark']}({data['nickname']})") if data["remark"] else data["nickname"]

            self.contacts[contact] = name
            if data["type"] == 0 or data["type"] == 4:
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

    
