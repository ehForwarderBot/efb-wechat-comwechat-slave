import base64
import tempfile
import logging
from .Utils import download_file , wechatimagedecode , load_config , load_local_file_to_temp
from .MsgDeco import efb_text_simple_wrapper, efb_text_delete_wrapper, efb_image_wrapper, efb_video_wrapper, efb_share_link_wrapper, efb_location_wrapper, efb_file_wrapper , efb_unsupported_wrapper , efb_voice_wrapper , efb_qqmail_wrapper , efb_miniprogram_wrapper
import re
import pilk
import pydub
import json
from lxml import etree

from ehforwarderbot import utils as efb_utils
from ehforwarderbot.message import Message

logger :logging.Logger = logging.getLogger(__name__)

def MsgProcess(msg : dict , chat) -> Message:

    if msg["type"] == "text":
        # at_list = {}
        # if "[@at," in msg['message']:
        #     text = msg['msg']
        #     at = re.findall(r"\[@at,(.+?)\]",text)
        #     content = re.sub(r'\[@at,nickname=(.+?)\]','',text)
        #     temp_msg = ""
        #     for each_people in list(set(at)):
        #         nickname = re.findall("^nickname=(.+),wxid",each_people)
        #         wxid = re.findall("wxid=(.+)$",each_people)
        #         if len(nickname)!=0:
        #             for i in nickname:
        #                 temp_msg += "@"+ i
        #         if len(wxid)!=0:
        #             for i in wxid:
        #                 if i == msg['robot_wxid']:
        #                     begin_index = len(temp_msg)
        #                     temp_msg += ' @me'
        #                     end_index = len(temp_msg)
        #                     at_list[(begin_index, end_index)] = chat.self
        #     temp_msg += ' ' + (content.strip())
        #     msg['msg'] = temp_msg
        
        # if at_list:
        #     return efb_text_simple_wrapper(msg['msg'] , at_list)
        return efb_text_simple_wrapper(msg['message'])

    elif msg["type"] == "sys_msg":
        if "<revokemsg>" in msg["message"]:
            return efb_text_simple_wrapper(msg['message'].replace("<revokemsg>","").replace("</revokemsg>",""))
        # 修改群名为 | 收到红包 | 拍了拍 | 邀请 | 与群里其他人都不是朋友关系，请注意隐私安全 | 对方未添加你为朋友。对方添加后，才能进行通话 |
        if "修改群名为" in msg["message"] or "收到红包" in msg["message"] or "拍了拍" in msg["message"] or "邀请" in msg["message"] or "与群里其他人都不是朋友关系，请注意隐私安全" in msg["message"] or "对方未添加你为朋友" in msg["message"]:
                return efb_text_simple_wrapper(msg['message'])
        else:  # 暂时用于分析，后继取消
            return efb_text_simple_wrapper("sys_msg :" + str(msg['message']))

    elif msg["type"] == "image":
        if msg["first"]:
            return efb_text_simple_wrapper("[接收到图片消息,等待下载完成]")
        else:
            file = wechatimagedecode(msg["filepath"])
            return efb_image_wrapper(file)

    elif msg["type"] == "animatedsticker":
        try:
            url = re.search("cdnurl = \"(.*?)\"", msg["message"]).group(1).replace("amp;", "")
            file = download_file(url)
            return efb_image_wrapper(file)
        except:
            return efb_text_simple_wrapper("Image received and download failed. Please check it on your phone.")
    elif msg["type"] == "share":
        if "FileStorage" in msg["filepath"]:
            if msg["first"]:
                return efb_text_simple_wrapper("[接收到文件消息,等待下载完成]")
            else:
                file = load_local_file_to_temp(msg["filepath"])
                return efb_file_wrapper(file , msg["filepath"].split("/")[-1])
        return efb_share_link_wrapper(msg['message'])
    else:
        return efb_text_simple_wrapper("Unsupported message type: " + msg['type'] + "\n" + str(msg))