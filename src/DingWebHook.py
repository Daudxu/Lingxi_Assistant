#!/usr/bin/env python
import lark_oapi as lark
from lark_oapi.api.im.v1 import *
from src.Agents import AgentClass
from src.Storage import add_user
from dotenv import load_dotenv as _load_dotenv
import os
import json
import logging

_load_dotenv()

os.environ["FEISHU_BASE_DOMAIN"] = os.getenv("FEISHU_BASE_DOMAIN")
os.environ["FEISHU_APP_ID"] = os.getenv("FEISHU_APP_ID")
os.environ["FEISHU_APP_SECRET"] = os.getenv("FEISHU_APP_SECRET")


def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("dingtalk_connection.log", encoding="utf-8")
        ]
    )
    return logging.getLogger("Feishu")

logger = setup_logging()

def handle_message(data: P2ImMessageReceiveV1):
    """
    处理飞书消息事件
    """
    try:
        logger.info("收到消息事件")
        # 解析文本内容
        res_content = ""
        if data.event.message.message_type == "text":
            try:
                content_dict = json.loads(data.event.message.content)
                res_content = content_dict.get("text", "").strip() if isinstance(content_dict, dict) else str(content_dict).strip()
            except Exception as e:
                logger.error(f"消息内容解析失败: {e}")
                res_content = ""
        else:
            res_content = "解析消息失败，请发送文本消息\nparse message failed, please send text message"

        # 获取用户ID，优先 open_id
        sender_id = getattr(data.event.sender.sender_id, "open_id", None) or getattr(data.event.sender.sender_id, "user_id", None) or "unknown"
        add_user("userid", sender_id)
        logger.info(f"用户 {sender_id} 已添加到存储中")

        # 调用智能体处理消息
        try:
            msg = AgentClass().run_agent(res_content)
            logger.info(f"AI回复: {msg}")
            if isinstance(msg, dict) and msg.get('output'):
                reply_text = msg['output']
            else:
                logger.error(f"AI返回内容异常，msg: {msg}")
                reply_text = "抱歉，AI未能生成有效回复"
        except Exception as e:
            logger.error(f"AI处理异常: {e}")
            reply_text = "抱歉，AI处理消息时发生异常"
        content = json.dumps({"text": reply_text})

        # 统一消息发送
        def send_message(request_func, request_obj, error_msg):
            try:
                response = request_func(request_obj)
                if not response.success():
                    logger.error(
                        f"{error_msg}, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}"
                    )
            except Exception as e:
                logger.error(f"发送消息异常: {e}")

        if data.event.message.chat_type == "p2p":
            chat_id = data.event.message.chat_id or ""
            request = (
                CreateMessageRequest.builder()
                .receive_id_type("chat_id")
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type("text")
                    .content(content)
                    .build()
                )
                .build()
            )
            send_message(client.im.v1.chat.create, request, "client.im.v1.chat.create failed")
        else:
            message_id = data.event.message.message_id or ""
            request = (
                ReplyMessageRequest.builder()
                .message_id(message_id)
                .request_body(
                    ReplyMessageRequestBody.builder()
                    .content(content)
                    .msg_type("text")
                    .build()
                )
                .build()
            )
            send_message(client.im.v1.message.reply, request, "client.im.v1.message.reply failed")
    except Exception as e:
        logger.error(f"处理消息时发生异常: {e}", exc_info=True)

def do_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
    """
    飞书事件回调入口
    """
    handle_message(data)

# 注册事件回调
event_handler = (
    lark.EventDispatcherHandler.builder("", "")
    .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1)
    .build()
)

# 创建 LarkClient 和 wsClient
client = lark.Client.builder().app_id(os.getenv("FEISHU_APP_ID")).app_secret(os.getenv("FEISHU_APP_SECRET")).build()
wsClient = lark.ws.Client(
    os.getenv("FEISHU_APP_ID"),
    os.getenv("FEISHU_APP_SECRET"),
    event_handler=event_handler,
    log_level=lark.LogLevel.DEBUG,
)

def main():
    logger.info("启动 Feishu 客户端")
    try:
        wsClient.start()
    except Exception as e:
        logger.error(f"连接飞书时出错: {e}", exc_info=True)

if __name__ == "__main__":
    main()