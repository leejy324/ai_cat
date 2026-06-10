import logging

import chromadb

from app.services.embedding_service import encode

logger = logging.getLogger(__name__)

_client = None
_COLLECTION_NAME = "student_memories"


def get_client() -> chromadb.ClientAPI:
    """获取全局单例 Chroma 客户端（嵌入式，数据持久化到本地）"""
    global _client
    if _client is None:
        # 数据持久化到本地磁盘。保存在 ./chroma_data 文件夹里
        # ./chroma_data 是相对于启动 uvicorn 时的当前工作目录
        # 也就是说，当你在 D:\MyProjects\ai_cat 目录下运行：
        # 如果你 cd 到别的目录再启动 uvicorn，Chroma 数据就会存到那个目录下的chroma_data/
        # 而之前的数据就找不到了。所以项目约定统一在项目根目录启动 uvicorn
        _client = chromadb.PersistentClient(path="./chroma_data")
        logger.info("Chroma 客户端初始化完成")
    return _client


def get_collection() -> chromadb.Collection:
    """获取或创建 student_memories 集合"""
    return get_client().get_or_create_collection(
        name=_COLLECTION_NAME,
        # hnsw：Chroma 使用的向量索引算法（Hierarchical Navigable Small World），用于快速查找最近邻向量
        # hnsw:space：指定距离计算方式
        # 选 cosine 是因为文本 embedding
        # 向量关注的是语义方向而不是向量长度。比如"我很开心"和"非常高兴"语义相近，余弦相似度会很高，即使用词完全不同
        metadata={"hnsw:space": "cosine"},
    )


def add_memory(
    memory_id: str,
    content: str,
    student_id: str,
    created_at: str,
    importance: str,
):
    """添加一条记忆到向量库"""
    collection = get_collection()
    embedding = encode(content) # 将文本编码为向量
    # .add() 支持批量写入，参数接收的是列表
    collection.add(
        ids=[memory_id],
        documents=[content],
        embeddings=[embedding],
        metadatas=[{
            "student_id": student_id,
            "created_at": created_at,
            "importance": importance,
        }],
    )


def query_memories(
    query_text: str,
    student_id: str,
    n_results: int = 3,
) -> list[dict]:
    """语义搜索相关记忆，返回包含 id、content、metadata 的字典列表"""
    collection = get_collection()
    if collection.count() == 0:
        return []

    query_embedding = encode(query_text)
    results = collection.query(
        query_embeddings=[query_embedding],
        where={"student_id": student_id},
        n_results=n_results,
    )

    if not results["ids"] or not results["ids"][0]:
        return []

# Chroma 的 query() 返回结果的结构是固定的。返回值大概长这样：                                                                                                                                                                                                   
#   results = {                                                                                                                          
#       "ids": [    
#           ["mem_id_3", "mem_id_1", "mem_id_5"]  # 外层列表对应每条查询（我们只有1条），内层是匹配的记忆ID，按相似度从高到低排          
#       ],          
#       "documents": [
#           ["记忆内容3", "记忆内容1", "记忆内容5"]  # 和 ids 一一对应
#       ],
#       "metadatas": [
#           [
#               {"student_id": "xxx", "created_at": "...", "importance": "high"},
#               {"student_id": "xxx", "created_at": "...", "importance": "medium"},
#               {"student_id": "xxx", "created_at": "...", "importance": "low"},
#           ]
#       ],
#       "distances": [
#           [0.12, 0.35, 0.58]  # 余弦距离，越小越相似
#       ],
#   }

    memories = []
    for i, mem_id in enumerate(results["ids"][0]):
        memories.append({
            "id": mem_id,
            "content": results["documents"][0][i],
            "student_id": results["metadatas"][0][i]["student_id"],
            "created_at": results["metadatas"][0][i]["created_at"],
            "importance": results["metadatas"][0][i]["importance"],
        })
    return memories


def delete_memory(memory_id: str):
    """从向量库中删除一条记忆"""
    collection = get_collection()
    collection.delete(ids=[memory_id])
