# 导入必要的库和模块
from langchain.agents import AgentExecutor,create_tool_calling_agent
from langchain_openai import ChatOpenAI  # OpenAI聊天模型接口
from langchain_deepseek import ChatDeepSeek  # DeepSeek聊天模型接口
from langchain_core.runnables import ConfigurableField
from .Prompt import PromptClass  # 导入提示词管理类
from .Memory import MemoryClass  # 导入记忆管理类
from .Emotion import EmotionClass  # 导入情感分析类
from langchain_core.caches import InMemoryCache  # 内存缓存，用于加速响应
from .Storage import get_user  # 获取用户信息的函数

# 导入各种工具函数
from .Tools import search,get_info_from_local
from dotenv import load_dotenv as _load_dotenv
_load_dotenv()
import os


os.environ["LANGSMITH_TRACING"] = os.getenv("LANGSMITH_TRACING")
os.environ["LANGSMITH_ENDPOINT"] = os.getenv("LANGSMITH_ENDPOINT")
os.environ["LANGSMITH_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
os.environ["LANGSMITH_PROJECT"] = os.getenv("LANGSMITH_PROJECT")
# 设置环境变量，包括API密钥和API基础URL
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_API_BASE"] = os.getenv("OPENAI_API_BASE")
os.environ["DEEPSEEK_API_KEY"] = os.getenv("DEEPSEEK_API_KEY")
os.environ["DEEPSEEK_API_BASE"] = os.getenv("DEEPSEEK_API_BASE")

# 添加缓存以提高性能，避免重复请求相同内容时消耗额外的API调用
from langchain_core.globals import set_llm_cache
set_llm_cache(InMemoryCache())


class AgentClass:
    """
    AI代理类，负责处理用户输入并生成回复
    整合了语言模型、记忆系统、情感分析和各种工具功能
    """
    def __init__(self):
        # 设置备用模型，当主模型不可用时使用
        fallback_llm = ChatDeepSeek(model=os.getenv("BACKUP_MODEL"))
        
        # 获取主模型名称
        self.modelname = os.getenv("BASE_MODEL")
        
        # 创建主聊天模型，并配置备用模型
        self.chatmodel = ChatOpenAI(model=self.modelname).with_fallbacks([fallback_llm])
        
        # 设置可用的工具列表，这些工具可以被AI代理调用
        self.tools = [search,get_info_from_local]
        
        # 从环境变量获取记忆键名
        self.memorykey = os.getenv("MEMORY_KEY")
        
        # 初始化情感状态，默认中性(5分)
        self.feeling = {"feeling":"default","score":5}
        
        # 创建提示词结构
        self.prompt = PromptClass(memorykey=self.memorykey,feeling=self.feeling).Prompt_Structure()
        
        # 初始化记忆系统
        self.memory = MemoryClass(memorykey=self.memorykey,model=self.modelname)
        
        # 初始化情感分析系统
        self.emotion = EmotionClass(model=self.modelname)
        
        # 创建工具调用型代理
        self.agent = create_tool_calling_agent(
            self.chatmodel,  # 使用的聊天模型
            self.tools,      # 可用工具列表
            self.prompt,     # 提示词结构
        )
        
        # 创建代理执行器，整合代理、工具和记忆系统
        self.agent_chain = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            memory=self.memory.set_memory(),
            verbose=True  # 启用详细输出，便于调试
        ).configurable_fields(
            # 设置可配置的记忆字段，允许在运行时修改记忆系统
            memory=ConfigurableField(
                id="agent_memory",
                name="Agent Memory",
                description="The memory of the agent",
            )
        )

    def run_agent(self, input):
        """
        运行AI代理处理用户输入
        
        参数:
            input: 用户输入的文本
            
        返回:
            包含AI回复的字典
        """
        # 新增：感谢/结束语识别
        thanks_keywords = ["谢谢", "thanks", "thank you", "辛苦了", "好的", "明白了"]
        if any(k in input.lower() for k in thanks_keywords):
            return {"output": "不客气，有问题随时找我哦！"}

        try:
            # 进行情感分析，了解用户当前的情绪状态
            emotion_result = self.emotion.Emotion_Sensing(input)
            if not emotion_result:
                print("情感分析返回None，使用默认情感设置")
                self.feeling = {"feeling": "default", "score": "5"}
            else:
                self.feeling = emotion_result
        except Exception as e:
            print(f"情感分析出错: {str(e)}，使用默认情感设置")
            self.feeling = {"feeling": "default", "score": "5"}

        # 更新提示词结构
        self.prompt = PromptClass(memorykey=self.memorykey, feeling=self.feeling).Prompt_Structure()
        print("self.prompt", self.prompt)

        # 运行代理链，处理用户输入
        session_id = get_user("userid")
        memory_instance = self.memory.set_memory(session_id=session_id)
        try:
            res = self.agent_chain.with_config({"agent_memory": memory_instance}).invoke({"input": input})
        except Exception as e:
            print(f"agent_chain 执行异常: {e}")
            return {"output": "抱歉，AI处理时发生异常。"}
        # 优化：output为空时尝试兜底
        if not res or not isinstance(res, dict):
            print(f"agent_chain 返回内容异常: {res}")
            return {"output": "抱歉，我没有理解您的问题。"}
        if not res.get("output"):
            print(f"agent_chain 返回内容异常: {res}")
            # 兜底尝试其他常见字段
            for key in ["result", "answer", "response"]:
                if key in res and res[key]:
                    return {"output": res[key]}
            return {"output": "抱歉，我没有理解您的问题。"}
        return res

