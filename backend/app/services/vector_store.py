import chromadb
from chromadb.config import Settings as ChromaSettings
from backend.app.core.config import settings

#-------------Chromadb 持久化--------------
chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_PATH)
collection = chroma_client.get_or_create_collection(name=settings.COLLECTION_NAME)

def add_documents(embeddings, documents, ids):
    collection.add(embeddings=embeddings, documents=documents, ids=ids)

def query_documents(query_embedding, n_results=3):
    results = collection.query(
        # query_embeddings需要的是List[List[float]]，既可以接受单个向量的查询，也可以接受批量查询。
        # 外层列表：查询的数量   内层列表：单个查询的向量
        query_embeddings=[query_embedding],
        n_results=n_results
    )
    # results.get("documents")返回的是一个二维列表，结构取决于查询了多少个问题。
    # 以下则表示获取第一个查询的所有结果，包含3个文档，如：{"documents":[["文档1","文档2"]，["第二个查询结果的文档...]], ids[[]]}
    return results.get("documents", [[]])[0]

