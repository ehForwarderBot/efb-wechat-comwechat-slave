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

    elif msg["type"] == "sysmsg":
        if "<revokemsg>" in msg["message"]:
            return efb_text_simple_wrapper(msg['message'].replace("<revokemsg>","").replace("</revokemsg>",""))
        # 修改群名为 | 收到红包 | 拍了拍 | 邀请 | 与群里其他人都不是朋友关系，请注意隐私安全 | 对方未添加你为朋友。对方添加后，才能进行通话 |
        if "修改群名为" in msg["message"] or "收到红包" in msg["message"] or "拍了拍" in msg["message"] or "邀请" in msg["message"] or "与群里其他人都不是朋友关系，请注意隐私安全" in msg["message"] or "对方未添加你为朋友" in msg["message"] or "移出" in msg["message"]:
                return efb_text_simple_wrapper(msg['message'])
        else:  # 暂时用于分析，后继取消
            return efb_text_simple_wrapper("sys_msg :" + str(msg['message']))

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
        return efb_voice_wrapper(file)

    elif msg["type"] == "video":
        file = load_local_file_to_temp(msg["filepath"])
        return efb_video_wrapper(file)
    
    elif msg["type"].startswith("unhandled"):
        if "op id='2'" in msg["message"]:
            return efb_text_simple_wrapper("手机端进入本对话")

    elif msg["type"] == "voip":
        return efb_unsupported_wrapper("语音/视频聊天\n  - - - - - - - - - - - - - - - \n不支持的消息类型, 请在微信端查看")

    elif msg["type"] == "other":
        if 'sysmsg type="voipmt"' in msg["message"] or 'sysmsg type="multivoip"' in msg["message"]:
            return efb_unsupported_wrapper("收到/取消 群语音邀请")
        elif '<sysmsg type="delchatroommember">' in msg['message']:
            xml = etree.fromstring(msg['message'])
            content = xml.xpath('//plain/text()')[0].strip("<![CDATA[").strip("]]>")
            return efb_text_simple_wrapper(content)
        else:
            return efb_text_simple_wrapper("Unsupported message type: " + msg['type'] + "\n" + str(msg))


    else:
        return efb_text_simple_wrapper("Unsupported message type: " + msg['type'] + "\n" + str(msg))
