#!/usr/bin/env python
import lark_oapi as lark
from lark_oapi.api.im.v1 import *
from src.Agents import AgentClass
from src.Storage import add_user
from dotenv import load_dotenv as _load_dotenv
import os
import json
import logging
import uuid

_load_dotenv()

os.environ["FEISHU_BASE_DOMAIN"] = os.getenv("FEISHU_BASE_DOMAIN")
os.environ["FEISHU_APP_ID"] = os.getenv("FEISHU_APP_ID")
os.environ["FEISHU_APP_SECRET"] = os.getenv("FEISHU_APP_SECRET")


def setup_logging():
    """设置日志配置"""
    logger = logging.getLogger("Feishu")
    if not logger.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler("dingtalk_connection.log", encoding="utf-8")
            ]
        )
    return logger

logger = setup_logging()
logger.info(f"服务启动唯一ID: {uuid.uuid4()}")

# 新增：已处理消息ID集合
processed_message_ids = set()

# 可选：用 Redis 存储已处理消息ID，防止多实例重复回复
# from redis import Redis
# redis_client = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

def handle_message(data: P2ImMessageReceiveV1):
    """
    处理飞书消息事件
    """
    try:
        # 新增：记录并检查 message_id，防止重复处理
        message_id = getattr(data.event.message, "message_id", None)
        if message_id:
            # 单实例用 set，集群用 redis
            # if redis_client.get(f"msgid:{message_id}"):
            #     logger.warning(f"消息 {message_id} 已处理，跳过")
            #     return
            # redis_client.setex(f"msgid:{message_id}", 3600, "1")
            if message_id in processed_message_ids:
                logger.warning(f"消息 {message_id} 已处理，跳过")
                return
            processed_message_ids.add(message_id)
        logger.info(f"收到消息事件，message_id={message_id}")
        
        # 统一消息发送函数 - 将此函数定义移到前面
        def send_message(request_func, request_obj, error_msg):
            try:
                response = request_func(request_obj)
                if not response.success():
                    logger.error(
                        f"{error_msg}, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}"
                    )
            except Exception as e:
                logger.error(f"发送消息异常: {e}")
                
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
        sender_id = getattr(data.event.sender.sender_id, "open_id", None) or getattr(data.event.sender.sender_id, "union_id", None) or "unknown"
        add_user("userid", sender_id)
        logger.info(f"用户 {sender_id} 已添加到存储中")

        # 调用智能体处理消息
        try:
            msg = AgentClass().run_agent(res_content)
            logger.info(f"AI回复: {msg}")
            reply_text = msg.get('output', '') if isinstance(msg, dict) else str(msg)
            if not reply_text:
                logger.warning(f"run_agent 返回 output 为空，原始返回: {msg}")
                reply_text = "抱歉，我暂时无法理解您的问题，可以换个问法试试吗？"
        except Exception as e:
            logger.error(f"AI处理异常: {e}")
            reply_text = "抱歉，AI处理消息时发生异常"

        content = json.dumps({"text": reply_text})

        # 在这里可以安全调用 send_message 函数
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
            # 修正：只用 message.create 发送消息
            send_message(client.im.v1.message.create, request, "client.im.v1.message.create failed")

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