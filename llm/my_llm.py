from langchain_openai import ChatOpenAI

from llm.env_utils import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL

#这个使用langchain-openai标准库
llm = ChatOpenAI(
    model="deepseek-v4-pro",
    temperature=0.5,
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
)

#这个使用langchain-deepseek标准库
# llm = ChatDeepSeek(
#     model_name="deepseek-v4-pro",
#     temperature=0.5,
#     api_key=DEEPSEEK_API_KEY,
#     api_base=DEEPSEEK_BASE_URL,
# )