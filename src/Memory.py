from langchain.memory import ConversationBufferMemory
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from src.Prompt import PromptClass
from dotenv import load_dotenv
load_dotenv()
import os
import re
import json

redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
print(f"Redis URL: {redis_url}")

LONG_MEMORY_PATH = os.path.join(os.path.dirname(__file__), "memory.json")

def load_long_memory():
    """加载长期记忆（知识图谱），文件不存在则创建空文件"""
    if not os.path.exists(LONG_MEMORY_PATH):
        # 文件不存在则创建空文件
        with open(LONG_MEMORY_PATH, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
        return {}
    try:
        with open(LONG_MEMORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("加载长期记忆失败", e)
        return {}

def save_long_memory(data):
    """保存长期记忆（知识图谱），写入前确保文件存在"""
    # 如果文件不存在，先创建空文件
    if not os.path.exists(LONG_MEMORY_PATH):
        with open(LONG_MEMORY_PATH, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    try:
        with open(LONG_MEMORY_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("保存长期记忆失败", e)

def search_long_memory(query):
    """简单关键词检索长期记忆，返回相关内容"""
    long_mem = load_long_memory()
    # 简单遍历所有value，包含query的就返回
    results = []
    for k, v in long_mem.items():
        if query in k or (isinstance(v, str) and query in v):
            results.append(f"{k}: {v}")
    return results

def count_tokens(messages):
    """估算消息总token数（简单按字符数/4）"""
    return sum(len(m.content) // 4 for m in messages)

def fold_code_blocks(text, max_lines=10):
    """
    对 markdown 代码块内容做折叠，只保留前后各 max_lines//2 行
    """
    def replacer(match):
        code = match.group(0)
        lines = code.splitlines()
        if (len(lines) > max_lines):
            keep = max_lines // 2
            return '\n'.join(lines[:keep]) + '\n...\n' + '\n'.join(lines[-keep:])
        return code
    # 匹配 ``` 开头和结尾的代码块
    return re.sub(r"```[\s\S]+?```", replacer, text)

def is_code_message(content):
    """判断消息是否为代码块"""
    # 简单判断：以```开头或结尾，或内容大部分为代码
    return content.strip().startswith("```") or content.strip().endswith("```") or len(re.findall(r"```[\s\S]+?```", content)) > 0

class MemoryClass:
    def __init__(self, memorykey="chat_history", model=os.getenv("BASE_MODEL")):
        self.memorykey = memorykey
        self.memory = []
        self.chatmodel = ChatOpenAI(model=model)

    def summary_chain(self, store_message):
        try:
            # 新增：对代码块内容做折叠
            store_message = fold_code_blocks(store_message, max_lines=10)
            SystemPrompt = PromptClass().SystemPrompt.format(feelScore=5, who_you_are="")
            Moods = PromptClass().MOODS
            prompt = ChatPromptTemplate.from_messages([
                ("system", SystemPrompt + "\n这是一段你和用户的对话记忆，对其进行总结摘要，摘要使用第一人称'我'，并且提取其中的关键信息，以如下格式返回：\n 总结摘要 | 过去对话关键信息\n例如 用户张三问候我好，我礼貌回复，然后他问我langchain的向量库信息，我回答了他今年的问题，然后他又问了比特币价格。|Langchain, 向量库,比特币价格"),
                ("user", "{input}")
            ])
            chain = prompt | self.chatmodel
            summary = chain.invoke({"input": store_message, "who_you_are": Moods["default"]["roloSet"]})
            return summary
        except Exception as e:
            print("总结出错", e)
            return None

    def get_memory(self, session_id: str = "session1", query_long_memory: str = None):
        try:
            print("session_id:", session_id)
            print("redis_url:", redis_url)
            chat_message_history = RedisChatMessageHistory(
                url=redis_url, session_id=session_id
            )
            store_message = chat_message_history.messages
            # 新增：自动保存聊天内容到 memory.json
            if store_message:
                data = load_long_memory()
                # 以 session_id 为 key，保存消息文本列表
                data[session_id] = [m.content for m in store_message]
                save_long_memory(data)
            # 新增：只保留最近10轮
            if len(store_message) > 10:
                store_message = store_message[-10:]
            # 新增：融合长期记忆
            long_memory_context = ""
            if query_long_memory:
                long_results = search_long_memory(query_long_memory)
                if long_results:
                    long_memory_context = "\n".join(long_results)
            # 优化：按token数和消息数双重判断
            if len(store_message) > 80 or count_tokens(store_message) > 3000:
                str_message = ""
                for message in store_message:
                    # 针对代码消息做特殊处理
                    if is_code_message(message.content):
                        code_len = len(message.content)
                        str_message += f"{type(message).__name__}: [代码消息，已折叠，长度:{code_len}字符]\n"
                    else:
                        content = fold_code_blocks(message.content, max_lines=10)
                        str_message += f"{type(message).__name__}: {content}\n"
                # 合并长期记忆内容
                if long_memory_context:
                    str_message = f"[长期记忆]\n{long_memory_context}\n\n" + str_message
                summary = self.summary_chain(str_message)
                chat_message_history.clear()
                if summary:
                    chat_message_history.add_message(summary)
                print("添加摘要后:", chat_message_history.messages)
                return chat_message_history
            else:
                # 合并长期记忆内容
                if long_memory_context:
                    # 将长期记忆内容插入到消息历史最前面
                    from langchain_core.messages import SystemMessage
                    chat_message_history.messages.insert(0, SystemMessage(content=f"[长期记忆]\n{long_memory_context}"))
                print("go to next step")
                return chat_message_history
        except Exception as e:
            print("get_memory异常", e)
            return None

    def save_to_long_memory(self, key, value):
        """主动写入长期记忆"""
        data = load_long_memory()
        data[key] = value
        save_long_memory(data)

    def set_memory(self, session_id: str = "session1"):
        chat_memory = self.get_memory(session_id=session_id)
        if chat_memory is None:
            print("chat_memory is None, 创建默认RedisChatMessageHistory")
            chat_memory = RedisChatMessageHistory(url=redis_url, session_id=session_id)

        self.memory = ConversationBufferMemory(
            llm=self.chatmodel,
            human_prefix="user",
            ai_prefix="灵犀小助手",
            memory_key=self.memorykey,
            output_key="output",
            return_messages=True,
            max_token_limit=1000,
            chat_memory=chat_memory,
        )
        return self.memory