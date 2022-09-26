import base64
import tempfile
import logging
from .Utils import download_file , wechatimagedecode , load_config
from .MsgDeco import efb_text_simple_wrapper, efb_text_delete_wrapper, efb_image_wrapper, efb_video_wrapper, efb_share_link_wrapper, efb_location_wrapper, efb_file_wrapper , efb_unsupported_wrapper , efb_voice_wrapper , efb_qqmail_wrapper , efb_miniprogram_wrapper
import re
import pilk
import pydub
import json
from lxml import etree

from ehforwarderbot import utils as efb_utils

logger :logging.Logger = logging.getLogger(__name__)

class MsgProcess:

    @staticmethod
    def text_msg(msg: dict , chat):
        msg['message'] = str(msg['message'])
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

    @staticmethod
    def sys_msg(msg: dict , chat):
        if "<revokemsg>" in msg["message"]:
            return efb_text_simple_wrapper(msg['message'].replace("<revokemsg>","").replace("</revokemsg>",""))
        if "修改群名为" in msg["message"]:
            return efb_text_simple_wrapper(msg['message'])

    @staticmethod
    def image_msg(msg: dict , chat):
        url = msg['message']
        print(url)
        try:
            f = download_file(url)
        except Exception as e:
            logger.warning(f"Failed to download the image! {e}")
            return efb_text_simple_wrapper("Image received and download failed. Please check it on your phone.")
        else:
            return efb_image_wrapper(f)

    @staticmethod
    def animatedsticker_msg(msg : dict , chat):
        try:
            url = re.search("cdnurl = \"(.*)\"", msg["message"]).group(1).replace("amp;", "")
            f = download_file(url)
            return efb_image_wrapper(f)
        except:
            return efb_text_simple_wrapper("Image received and download failed. Please check it on your phone.")

    # @staticmethod
    # def video_msg(msg : dict):
    #     url = msg['msg']
    #     try:
    #         f = download_file(url)
    #     except Exception as e:
    #         logger.warning(f"Failed to download the video_msg! {e}")
    #         return efb_text_simple_wrapper("Video_msg received and download failed. Please check it on your phone.")
    #     else:
    #         return efb_video_wrapper(f)

    # @staticmethod
    # def file_msg(msg : dict):
    #     url = msg['msg']
    #     try:
    #         f = download_file(url)
    #     except Exception as e:
    #         logger.warning(f"Failed to download the file! {e}")
    #         return efb_text_simple_wrapper("File received and download failed. Please check it on your phone.")
    #     else:
    #         if 'dat' in url:
    #             f = wechatimagedecode(f)
    #             return efb_image_wrapper(f)
    #         return efb_file_wrapper(f , filename= url.split('/')[-1])

    # @staticmethod
    # def share_link_msg(msg: dict):
    #     try:
    #         type = re.search('<type>(\d+)<\/type>' , msg['msg']).group(1)
    #         if str(type) in ['8'] and msg['event'] == 'EventSendOutMsg':
    #             return
    #     except:
    #         pass
    #     return efb_share_link_wrapper(msg['msg'])
    
    # @staticmethod
    # def location_msg(msg: dict):
    #     return efb_location_wrapper(msg['msg'])
    
    # @staticmethod
    # def qqmail_msg(msg: dict):
    #     return efb_qqmail_wrapper(msg['msg'])
    
    # @staticmethod
    # def miniprogram_msg(msg: dict):
    #     return efb_miniprogram_wrapper(msg['content'])
    
    # @staticmethod
    # def other_msg(msg: dict):
    #     if '<banner>' in msg['msg']:
    #         msg['msg'] = '收到/取消 群语音邀请'
    #     elif 'notifydata' in msg['msg']:
    #         return None
    #     elif '拍了拍' in msg['msg'] or 'tickled' in msg['msg']:
    #         return None
    #     elif 'ClientCheckConsistency' in msg['msg']:
    #         msg['msg'] = '客户端一致性检查'
    #     elif 'mmchatroombarannouncememt' in msg['msg']:
    #         return None
    #     elif 'bizlivenotify' in msg['msg']:    #暂时处理，未确认
    #         msg['msg'] = '收到直播通知'
    #     elif 'roomtoolstips' in msg['msg'] and '撤回' in msg['msg']:
    #         msg['msg'] = '  - - - - - - - - - - - - - - - \n撤回了一个群待办'
    #     elif 'roomtoolstips' in msg['msg'] and '撤回' not in msg['msg']:
    #         msg['msg'] = '  - - - - - - - - - - - - - - - \n发布/完成 了一个群待办'
    #     elif 'ShareExtensionSend' in msg['msg']:
    #         msg['msg'] = '  - - - - - - - - - - - - - - - \n分享成功消息'
    #     elif 'ChatSync' in msg['msg']:
    #         msg['msg'] = '  - - - - - - - - - - - - - - - \n系统消息 : 消息同步'
    #     elif '邀请你加入了群聊，并分享了$history$' in msg['msg']:
    #         xml = etree.fromstring(msg['msg'])
    #         inviter = xml.xpath("//link[@name='username']/memberlist/member/nickname/text()")[0]
    #         others = xml.xpath("//link[@name='others']/plain/text()")[0]
    #         history = xml.xpath("//link[@name='history']/title/text()")[0]
    #         msg['msg'] = f'{inviter}邀请你加入了群聊，并分享了{history}，群聊参与人还有：{others}'
    #     return efb_text_simple_wrapper(msg['msg'])

    # @staticmethod
    # def unsupported_msg(msg: dict):
    #     mag_type = {'voip' : '语音/视频聊天' , 'card' : '微信联系人名片分享'}
    #     msg['msg'] = '%s\n  - - - - - - - - - - - - - - - \n不支持的消息类型, 请在微信端查看' % mag_type[msg['type']]
    #     return efb_unsupported_wrapper(msg['msg'])
    
    # @staticmethod
    # def revoke_msg(msg: dict):
    #     pat = "['|\"]msg_type['|\"]: (\d+),"
    #     try:
    #         msg_type = re.search(pat , str(msg['msg'])).group(1)
    #     except:
    #         msg_type = None
    #     if msg_type in ['1']:
    #         msg['msg'] = '「撤回了一条消息」 \n  - - - - - - - - - - - - - - - \n' + msg['msg']['revoked_msg']['content']
    #     else:
    #         msg['msg'] = '「撤回了一条消息」 \n  - - - - - - - - - - - - - - - \n不支持的消息类型'
    #     return efb_text_simple_wrapper(msg['msg'])

    # @staticmethod
    # def voice_msg( msg : dict , chat):
    #     try:
    #         input_file = download_file(msg['msg'] )
    #     except Exception as e:
    #         logger.warning(f"Failed to download the voice! {e}")
    #         msg['msg'] = '语音消息\n  - - - - - - - - - - - - - - - \n不支持的消息类型, 请在微信端查看'
    #         return efb_unsupported_wrapper(msg['msg'])
    #     else:
    #         f = tempfile.NamedTemporaryFile()
    #         input_file.seek(0)
    #         silk_header = input_file.read(10)
    #         input_file.seek(0)
    #         if b"#!SILK_V3" in silk_header:
    #             pilk.decode(input_file.name, f.name)
    #             input_file.close()
    #             pydub.AudioSegment.from_raw(file= f , sample_width=2, frame_rate=24000, channels=1) \
    #                 .export( f , format="ogg", codec="libopus",
    #                         parameters=['-vbr', 'on'])
    #             return efb_voice_wrapper(f , filename= f.name + '.ogg')
    #         input_file.close()
    #         msg['msg'] = '语音消息\n  - - - - - - - - - - - - - - - \n不支持的消息类型, 请在微信端查看'
    #         return efb_unsupported_wrapper(msg['msg'])
            
    # @staticmethod
    # def group_announcement_msg( msg : dict ):
    #     msg['msg'] = '「群公告」 \n  - - - - - - - - - - - - - - - \n ' + msg['msg']
    #     return efb_text_simple_wrapper(msg['msg'])

    # @staticmethod
    # def event_notify_msg( msg : dict ):
    #     if msg['event'] == 'EventGroupMemberAdd':
    #         new = msg['msg']['guest']['nickname']
    #         inviter = msg['msg']['inviter']['nickname']
    #         msg['msg'] = f'「群成员增加」 \n  - - - - - - - - - - - - - - - \n{inviter} 邀请 {new} 加入了群聊'
    #     elif msg['event'] == 'EventGroupMemberDecrease':
    #         msg['msg'] = '「群成员减少」 \n  - - - - - - - - - - - - - - - \n "' + msg['msg']['member_nickname'] + '" 离开了群聊'
    #     return efb_text_simple_wrapper(msg['msg'])

    # @staticmethod
    # def transfer_msg( msg : dict ):
    #     msg['msg'] = '「转账」 \n  - - - - - - - - - - - - - - - \n ' + str(json.loads(msg['money'])) + ' 元'
    #     return efb_text_simple_wrapper(msg['msg'])

    # @staticmethod
    # def scanmoney_msg( msg : dict ):
    #     msg['msg'] = msg['msg']['scene_desc']
    #     return efb_text_simple_wrapper(msg['msg'])