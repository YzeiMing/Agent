from typing import List

def chunk_text(text:str, chunk_size:int=500, overlap:int=50) -> List[str]:
    """
    将文本按固定字数切分成块，相邻之间有 overlap 重叠
    """
    chunks = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = start + chunk_size
        # 取当前块
        #text[start:end]:从字符串中截取一部分
        chunk = text[start:end]
        chunks.append(chunk)
        # 下一块的起始位置
        start = end - overlap
    return chunks