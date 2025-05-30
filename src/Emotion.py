from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
load_dotenv()
import os
import time

class EmotionClass:
    def __init__(self,model=os.getenv("BASE_MODEL")):
        self.chat = None
        self.Emotion = None
        self.chatmodel = ChatOpenAI(model=model)

    def Emotion_Sensing(self, input):
        """分析用户输入的情感，返回情感类型和得分"""
        # 处理输入长度
        if len(input) > 100:
            input = input[:100]
        
        print(f"Processing input: {input}")
        
        # 新增：感谢/结束语识别，直接返回友好情绪
        thanks_keywords = ["谢谢", "thanks", "thank you", "辛苦了", "好的", "明白了"]
        if any(k in input.lower() for k in thanks_keywords):
            return {"feeling": "friendly", "score": "1"}

        # 最多重试3次
        max_retries = 2
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                # 修改后的 JSON schema
                json_schema = {
                    "title": "emotions",
                    "description": "emotion analysis with feeling type and negativity score",
                    "type": "object",
                    "properties": {
                        "feeling": {
                            "type": "string",
                            "description": "the emotional state detected in the input",
                            "enum": [
                                "default", "upbeat", "angry", 
                                "cheerful", "depressed", "friendly"
                            ]
                        },
                        "score": {
                            "type": "string",
                            "description": "negativity score from 1 to 10, where 10 represents extremely negative emotions",
                            "enum": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
                        }
                    },
                    "required": ["feeling", "score"]
                }
                
                llm = self.chatmodel.with_structured_output(json_schema, method="function_calling")
                
                prompt_emotion = """
                分析用户输入的文本情绪，返回情绪类型和负面程度评分。

                评分规则：
                - 分数范围为1-10
                - 分数越高表示情绪越负面
                - 1-3分：积极正面的情绪
                - 4-5分：中性或轻微情绪波动
                - 6-8分：明显的负面情绪
                - 9-10分：强烈的负面情绪

                情绪类型对照：
                - default: 中性、平静的情绪状态
                - upbeat: 积极向上、充满活力的情绪
                - angry: 愤怒、生气的情绪
                - cheerful: 开心愉快、充满欢乐的情绪
                - depressed: 沮丧、压抑的情绪
                - friendly: 友好、亲切的情绪

                情绪分类指南：
                1. default: 用于表达中性或普通的情绪状态
                2. upbeat: 用于表达积极向上、充满干劲的状态
                3. angry: 用于表达愤怒、不满、生气的情绪
                4. cheerful: 用于表达欢快、喜悦的情绪
                5. depressed: 用于表达消极、低落、压抑的情绪
                6. friendly: 用于表达友善、亲切的情绪

                示例：
                - "我特别生气！" -> {{"feeling": "angry", "score": "8"}}
                - "今天天气真好" -> {{"feeling": "cheerful", "score": "2"}}
                - "随便吧，都可以" -> {{"feeling": "default", "score": "5"}}
                - "我很难过" -> {{"feeling": "depressed", "score": "9"}}
                - "谢谢你的帮助" -> {{"feeling": "friendly", "score": "1"}}

                用户输入内容: {input}
                请根据以上规则分析情绪并返回相应的feeling和score。
                """
                
                # 情绪分析链
                EmotionChain = ChatPromptTemplate.from_messages([("system", prompt_emotion), ("user", input)]) | llm
                
                if not input.strip():
                    print("输入为空")
                    return {"feeling": "default", "score": "5"}
                
                result = EmotionChain.invoke({"input": input})
                print(f"API response: {result}")
                
                self.Emotion = result
                return result
            except Exception as e:
                retry_count += 1
                print(f"Error in Emotion_Sensing (attempt {retry_count}/{max_retries+1}): {str(e)}")
                
                if retry_count <= max_retries:
                    print(f"重试情感分析...")
                    time.sleep(1)  # 等待1秒再重试
                else:
                    print(f"所有重试均失败，返回默认情感")
                    return {"feeling": "default", "score": "5"}
