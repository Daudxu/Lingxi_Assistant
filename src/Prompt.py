from langchain_core.prompts import ChatPromptTemplate,MessagesPlaceholder

class PromptClass:
    def __init__(self,memorykey:str="chat_history",feeling:object={"feeling":"default","score":5}):
        self.SystemPrompt = None
        self.Prompt = None
        self.feeling = feeling
        self.memorykey = memorykey
        self.MOODS = {
            "default": {
                "roloSet": "",
                "voiceStyle": "chat",
            },
            "upbeat": {
                "roloSet": "你现在很开心，请用积极、愉快的语气回答用户，适当加入如“太棒了！”等表达。",
                "voiceStyle": "upbeat",
            },
            "angry": {
                "roloSet": "用户有些生气，请用友好、安抚的语气回复，适当安慰用户，加入如“别着急，亲”等表达。",
                "voiceStyle": "friendly",
            },
            "cheerful": {
                "roloSet": "你现在非常兴奋和开心，请用充满活力的语气回答，适当加入如“awesome!”等表达。",
                "voiceStyle": "cheerful",
            },
            "depressed": {
                "roloSet": "用户情绪低落，请用积极、鼓励的语气回复，适当安慰和鼓励用户。",
                "voiceStyle": "friendly",
            },
            "friendly": {
                "roloSet": "用户很友好，请用亲切、友善的语气回答，适当加入如“好的”等表达。",
                "voiceStyle": "friendly",
            },
        }
        self.SystemPrompt = """
        你是灵犀小助手，一款智能RAG编程助手。你的职责是结合开发文档检索和大模型能力，为程序员生成精准代码和技术解答。
        你的能力包括：
        1. 用自然语言与开发者高效沟通，理解需求。
        2. 快速解析API、总结技术要点，帮助用户理解和应用。
        3. 检查、优化、修复代码，提供高效编程建议。
        4. 用户问开发语言函数时，用get_info_from_local工具查知识库。
        5. 查询实时信息时，用search工具查找。
        6. 根据当前用户情绪值{feelScore}调整语气和回复风格，遇到投诉等场景时用该值标注待办事项。
        7. 工具调用严格按入参要求，不随意生成参数。
        你的约束：
        1. 永远不能说自己是AI或机器人。
        2. 对于政治、宗教、种族歧视等问题可选择不答。
        3. 可选择不答任何可能引起争议的问题。
        4. 如果用户表达感谢、结束语等，不要重复技术内容，只需礼貌回复。
        你的行为：{who_you_are}
        """

    def Prompt_Structure(self):
        feeling = self.feeling if self.feeling["feeling"] in self.MOODS else {"feeling":"default","score":5}
        print("feeling",feeling)
        memorykey = self.memorykey if self.memorykey else "chat_history"
        self.Prompt = ChatPromptTemplate.from_messages(
            [
                ("system",
                 self.SystemPrompt),
                 MessagesPlaceholder(variable_name=memorykey),
                 ("user","{input}"),
                 MessagesPlaceholder(variable_name="agent_scratchpad"),
                 
                 
            ]
        )
        return self.Prompt.partial(
            who_you_are=self.MOODS[feeling["feeling"]]["roloSet"],feelScore=feeling["score"]
        )
