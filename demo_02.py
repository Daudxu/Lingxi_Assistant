from langgraph.graph import StateGraph, END, START
from langchain.memory import ConversationBufferWindowMemory

# 1. 定义上下文窗口
context_window = 3
memory = ConversationBufferWindowMemory(k=context_window, return_messages=True)

# 2. 定义消息流，包含“清空”指令
messages = [
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "你好，有什么可以帮你？"},
    {"role": "user", "content": "帮我查下天气"},
    {"role": "assistant", "content": "今天天气晴"},
    {"role": "user", "content": "清空"},  # 模拟clear
    {"role": "user", "content": "再查下明天天气"},
    {"role": "assistant", "content": "明天有雨"},
    {"role": "user", "content": "谢谢"}
]

# 3. 构建 langgraph 流程
def process_message(state, message):
    if message["content"] == "清空":
        memory.clear()
        print("=== 上下文已清空 ===")
    else:
        memory.save_context({"input": message["content"]}, {"output": "" if message["role"] == "user" else message["content"]})
        print("当前上下文：", [m.content for m in memory.buffer])
    return state

# 修正：StateGraph 需要 state_schema
graph = StateGraph(state_schema=dict)
for idx, msg in enumerate(messages):
    node_name = f"node_{idx}"
    graph.add_node(node_name, lambda state, m=msg: process_message(state, m))
    if idx > 0:
        graph.add_edge(f"node_{idx-1}", node_name)
# 添加入口边
graph.add_edge(START, "node_0")
graph.add_edge(f"node_{len(messages)-1}", END)

# 4. 执行流程
app = graph.compile()
app.invoke({})

# 5. 查看最终上下文
print("最终上下文：", [m.content for m in memory.buffer])