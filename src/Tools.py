# from typing import Optional
import os
# import time
# import requests
# from pydantic import BaseModel, Field
from dotenv import load_dotenv
from langchain.agents import tool
from langchain_community.utilities import SerpAPIWrapper
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from .Memory import MemoryClass
from .Storage import get_user
# from langchain_core.output_parsers import PydanticOutputParser

# 配置管理
class Config:
    def __init__(self):
        load_dotenv()
        self.setup_environment()
        
    @staticmethod
    def setup_environment():
        required_vars = [
            "SERPAPI_API_KEY",
            "OPENAI_API_KEY",
            "OPENAI_API_BASE",
        ]
        
        for var in required_vars:
            if not os.getenv(var):
                raise EnvironmentError(f"Missing required environment variable: {var}")
            
        os.environ.update({
            "SERPAPI_API_KEY": os.getenv("SERPAPI_API_KEY"),
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
            "OPENAI_API_BASE": os.getenv("OPENAI_API_BASE")
        })


# 工具函数
@tool
def search(query: str) -> str:
    """只有需要了解实时信息或不知道的事情的时候才会使用这个工具."""
    serp = SerpAPIWrapper()
    return serp.run(query)

@tool(parse_docstring=True)
def get_info_from_local(query: str) -> str:
    """从本地知识库获取信息。

    Args:
        query (str): 用户的查询问题

    Returns:
        str: 从知识库中检索到的答案
    """
    print("-------RAG-------------")
    userid = get_user("userid")
    print(userid)
    llm = ChatOpenAI(model=os.getenv("BASE_MODEL"))
    memory = MemoryClass(memorykey=os.getenv("MEMORY_KEY"),model=os.getenv("BASE_MODEL"))
    chat_history = memory.get_memory(session_id=userid).messages if userid else []
    
    condense_question_prompt = ChatPromptTemplate.from_messages([
        ("system", "给出聊天记录和最新的用户问题。可能会引用聊天记录中的上下文，提出一个可以理解的独立问题。没有聊天记录，请勿回答。必要时重新配制，否则原样退还。"),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
    ])

    client = QdrantClient(path=os.getenv("PERSIST_DIR","./vector_store"))
    vector_store = QdrantVectorStore(
        client=client, 
        collection_name=os.getenv("EMBEDDING_COLLECTION"), 
        embedding=OpenAIEmbeddings(
            model=os.getenv("EMBEDDING_MODEL", "Pro/BAAI/bge-m3"),
            api_key=os.getenv("EMBEDDING_API_KEY"),
            base_url=os.getenv("EMBEDDING_API_BASE")
        )
    )
    
    retriever = vector_store.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 5, "fetch_k": 10}
    )
    
    qa_chain = create_retrieval_chain(
        create_history_aware_retriever(llm, retriever, condense_question_prompt),
        create_stuff_documents_chain(
            llm,
            ChatPromptTemplate.from_messages([
                ("system", "你是回答问题的助手。使用下列检索到的上下文回答。这个问题。如果你不知道答案，就说你不知道。最多使用三句话，并保持回答简明扼要。\n\n{context}"),
                ("placeholder", "{chat_history}"),
                ("human", "{input}"),
            ])
        )
    )
    
    res = qa_chain.invoke({
        "input": query,
        "chat_history": chat_history,
    })
    print("-------RAG- OUTPUT------------")
    print(res)
    return res["answer"]



# 初始化配置
Config()
