from typing import Optional, Dict

from ehforwarderbot.channel import SlaveChannel


class EFBGroupChat(Dict):
    channel: str
    uid: str
    name: str


class EFBPrivateChat(EFBGroupChat):
    alias: str


class EFBGroupMember(Dict):
    name: str
    uid: str
    alias: str


class EFBSystemUser(Dict):
    uid: str
    name: str