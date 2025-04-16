import lark_oapi as lark
from lark_oapi.api.im.v1 import *
import json, os
from dotenv import load_dotenv as _load_dotenv

_load_dotenv()

os.environ["FEISHU_BASE_DOMAIN"] = os.getenv("FEISHU_BASE_DOMAIN")
os.environ["FEISHU_APP_ID"] = os.getenv("FEISHU_APP_ID")
os.environ["FEISHU_APP_SECRET"] = os.getenv("FEISHU_APP_SECRET")

processed_message_ids = set()

# 注册接收消息事件，处理接收到的消息。
# Register event handler to handle received messages.
# https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/im-v1/message/events/receive
def do_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
    message_id = data.event.message.message_id
    if message_id in processed_message_ids:
        # logger.info(f"重复消息，已忽略: {message_id}")
        return
    processed_message_ids.add(message_id)

    res_content = ""
    if data.event.message.message_type == "text":
        res_content = json.loads(data.event.message.content)["text"]
        print("text=============", res_content)
    else:
        res_content = "解析消息失败，请发送文本消息\nparse message failed, please send text message"

    content = json.dumps(
        {
            "text": "收到你发送的消息：" + res_content
        }
    )

    if data.event.message.chat_type == "p2p":
        print("p2p=============",content)
        request = (
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(data.event.message.chat_id)
                .msg_type("text")
                .content(content)
                .build()
            )
            .build()
        )
        # 使用OpenAPI发送消息
        # Use send OpenAPI to send messages
        # https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/im-v1/message/create
        response = client.im.v1.chat.create(request)

        if not response.success():
            raise Exception(
                f"client.im.v1.chat.create failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}"
            )
    # else:
    #     request: ReplyMessageRequest = (
    #         ReplyMessageRequest.builder()
    #         .message_id(data.event.message.message_id)
    #         .request_body(
    #             ReplyMessageRequestBody.builder()
    #             .content(content)
    #             .msg_type("text")
    #             .build()
    #         )
    #         .build()
    #     )
        # 使用OpenAPI回复消息
        # Reply to messages using send OpenAPI
        # https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/im-v1/message/reply
        # response: ReplyMessageResponse = client.im.v1.message.reply(request)
        # if not response.success():
        #     raise Exception(
        #         f"client.im.v1.message.reply failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}"
        #     )


# 注册事件回调
# Register event handler.
event_handler = (
    lark.EventDispatcherHandler.builder("", "")
    .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1)
    .build()
)


# 创建 LarkClient 对象，用于请求OpenAPI, 并创建 LarkWSClient 对象，用于使用长连接接收事件。
# Create LarkClient object for requesting OpenAPI, and create LarkWSClient object for receiving events using long connection.
client = lark.Client.builder().app_id(os.getenv("FEISHU_APP_ID")).app_secret(os.getenv("FEISHU_APP_SECRET")).build()
wsClient = lark.ws.Client(
    os.getenv("FEISHU_APP_ID"),
    os.getenv("FEISHU_APP_SECRET"),
    event_handler=event_handler,
    log_level=lark.LogLevel.DEBUG,
)


def main():
    #  启动长连接，并注册事件处理器。
    #  Start long connection and register event handler.
    wsClient.start()



if __name__ == "__main__":
    main()
