import base64
import tempfile
import logging
from .Utils import *
from .MsgDeco import *
import re
import pydub
import json
from lxml import etree

from ehforwarderbot import utils as efb_utils
from ehforwarderbot.message import Message

def MsgProcess(msg : dict , chat) -> Message:

    if msg["type"] == "text":
        at_list = {}
        try:
            if "<atuserlist>" in msg["extrainfo"]:
                at_user = re.search("<atuserlist>(.*)<\/atuserlist>", msg["extrainfo"]).group(1)
                if msg["self"] in at_user:
                    msg["message"] = "@me " + msg["message"]
                    at_list[(0 , 4)] = chat.self
        except:
            ...
        if at_list:
            return efb_text_simple_wrapper(msg['message'] , at_list)
        return efb_text_simple_wrapper(msg['message'])

    elif msg["type"] == "sysmsg":
        if "<revokemsg>" in msg["message"]:  # 重复的撤回通知，不在此处处理
            return                            
        return efb_text_simple_wrapper(msg['message'])

    elif msg["type"] == "image":
        file = wechatimagedecode(msg["filepath"])
        return efb_image_wrapper(file)

    elif msg["type"] == "animatedsticker":
        try:
            url = re.search("cdnurl\s*=\s*\"(.*?)\"", msg["message"]).group(1).replace("amp;", "")
            file = download_file(url)
            return efb_image_wrapper(file)
        except:
            return efb_text_simple_wrapper("Image received and download failed. Please check it on your phone.")

    elif msg["type"] == "share":
        if ("FileStorage" in msg["filepath"]) and ("Cache" not in msg["filepath"]):
            file = load_local_file_to_temp(msg["filepath"])
            return efb_file_wrapper(file , msg["filepath"].split("/")[-1])
        return efb_share_link_wrapper(msg['message'])

    elif msg["type"] == "voice":
        file = convert_silk_to_mp3(load_local_file_to_temp(msg["filepath"]))
        return efb_voice_wrapper(file , file.name + ".ogg")

    elif msg["type"] == "video":
        file = load_local_file_to_temp(msg["filepath"])
        return efb_video_wrapper(file)
    
    elif msg["type"] == "location":
        return efb_location_wrapper(msg["message"])

    elif msg["type"] == "voip":
        if "<status>1</status>" in msg["message"]:
            return efb_text_simple_wrapper("[语音/视频聊天]\n  - - - - - - - - - - - - - - - \n语音邀请")
        if "<status>2</status>" in msg["message"]:
            return efb_text_simple_wrapper("[语音/视频聊天]\n  - - - - - - - - - - - - - - - \n语音挂断")

    elif msg["type"] == "other":
        if 'sysmsg type="voipmt"' in msg["message"] or 'sysmsg type="multivoip"' in msg["message"]:
            return efb_unsupported_wrapper("[收到/取消 群语音邀请]")
        elif '<sysmsg type="delchatroommember">' in msg['message']:
            xml = etree.fromstring(msg['message'])
            content = xml.xpath('//plain/text()')[0].strip("<![CDATA[").strip("]]>")
            return efb_text_simple_wrapper(content)
        elif "群公告" in msg["message"] and "群待办" in msg["message"]:
            return efb_text_simple_wrapper("[发布了群待办]")
        elif "<mmchatroombarannouncememt>" in msg["message"]:
            return
        elif '<sysmsg type="functionmsg">' in msg['message']:
            return
        elif '<sysmsg type="modtextstatus">' in msg['message']:
            return
        elif '<sysmsg type="ClientCheckConsistency">' in msg['message']:
            return
        else:
            return efb_text_simple_wrapper("Unsupported message type: " + msg['type'] + "\n" + str(msg))

    elif msg["type"] == "phone":
        return

    else:
        return efb_text_simple_wrapper("Unsupported message type: " + msg['type'] + "\n" + str(msg))
