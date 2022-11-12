FROM python:alpine AS venv

RUN set -ex; \
    apk --update upgrade; \
    apk --update add --no-cache python3-dev py3-pillow py3-ruamel.yaml libmagic ffmpeg git gcc zlib-dev jpeg-dev musl-dev libffi-dev openssl-dev libwebp-dev
RUN python -m venv --copies /app/venv; \
    . /app/venv/bin/activate; \
    pip3 install git+https://github.com/QQ-War/efb-telegram-master.git; \
    pip3 install ehforwarderbot python-telegram-bot; \
    pip3 install git+https://github.com/0honus0/python-comwechatrobot-http.git; \
    pip3 install git+https://github.com/0honus0/efb-wechat-comwechat-slave.git; \
    pip3 install git+https://github.com/QQ-War/efb-keyword-reply.git; \
    pip3 install git+https://github.com/QQ-War/efb_message_merge.git; \
    pip3 install --no-deps --force-reinstall Pillow; \
    pip3 install --ignore-installed PyYAML TgCrypto
    
FROM python:alpine AS prod

LABEL org.opencontainers.image.source https://github.com/0honus0/efb-wechat-comwechat-slave

ENV LANG C.UTF-8
ENV TZ Asia/Shanghai

COPY --from=venv /app/venv /app/venv/
ENV PATH /app/venv/bin:$PATH

COPY config-example.yaml /root/.ehforwarderbot/profiles/default/config.yaml

RUN set -ex; \
    apk --update upgrade; \
    apk --update add --no-cache tzdata libmagic ffmpeg; \
    rm -rf /tmp/* /var/cache/apk/* /var/lib/apk/lists/*; \
    ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime; \
    echo "Asia/Shanghai" > /etc/timezone; \
    mkdir -p /root/.ehforwarderbot/profiles/default/blueset.telegram /root/.ehforwarderbot/modules/

VOLUME /root/.ehforwarderbot/profiles/default/blueset.telegram

ENTRYPOINT ["ehforwarderbot"]