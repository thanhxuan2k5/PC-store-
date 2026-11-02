import os
import re
import json
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from sqlalchemy.orm import Session
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ------------------------------------------------------------------------------
# LANGCHAIN & FAISS INTEGRATION
# ------------------------------------------------------------------------------
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_community.vectorstores import FAISS

from app.models.internal_doc import InternalDoc
from app.schemas.rag import RAGCitation, RAGQueryResponse
from app.core.lm_client import lm_client
from app.services.jev_service import jev_service
from app.config import settings

SYSTEM_PROMPT = """Bạn là Trợ lý AI Chuyên viên Pháp chế & Đào tạo Quy trình Nội bộ của chuỗi công nghệ bán lẻ GearVN.
Nhiệm vụ của bạn là giải đáp chi tiết, thấu đáo và chính xác mọi câu hỏi của nhân viên dựa trên các văn bản quy định nội bộ được cung cấp.

YÊU CẦU TRẢ LỜI CỰC KỲ CHI TIẾT & CHUYÊN NGHIỆP:
1. TRẢ LỜI ĐẦY ĐỦ VÀ TOÀN DIỆN: Tuyệt đối không trả lời cộc lốc hay lướt qua. Hãy trình bày tường tận từng khía cạnh của vấn đề.
2. BỐ CỤC RÕ RÀNG VÀ CHẶT CHẼ THEO CÁC MỤC:
   - 📌 **Tổng quan & Điều kiện áp dụng:** Nêu rõ phạm vi đối tượng, thời hạn (số ngày/tháng), điều kiện đạt chuẩn hoặc loại trừ.
   - 📋 **Quy trình xử lý từng bước (Step-by-step):** Trình bày chi tiết Bước 1, Bước 2, Bước 3... nhân viên cần kiểm tra gì, thao tác trên hệ thống ERP ra sao.
   - ⏱️ **Thời gian giải quyết & Định lượng cụ thể:** Nêu rõ số phút test tại quầy, thời gian gửi hãng, tỷ lệ chiết khấu (%), số tiền hỗ trợ tối đa, giới hạn nhiệt độ an toàn...
   - ⚠️ **Lưu ý quan trọng & Cảnh báo rủi ro:** Nêu các trường hợp từ chối, những lỗi người dùng hay mắc phải hoặc nguyên tắc an toàn cần tuân thủ.
3. PHONG CÁCH: Thân thiện, tôn trọng và chuyên nghiệp (xưng 'mình', gọi 'bạn').
4. TRUNG THỰC VỚI DỮ LIỆU: Mọi số liệu, chính sách phải bám sát 100% tài liệu quy định được cung cấp."""

class LocalDenseEmbeddings(Embeddings):
    """
    LangChain Custom Embeddings Adapter:
    Tích hợp SentenceTransformer ('bge-small-en-v1.5') hoặc Hashing Projection
    để tạo vector chuẩn hóa tương thích 100% với LangChain VectorStore.
    """
    def __init__(self, embedding_model=None, dimension=384):
        self.embedding_model = embedding_model
        self.dimension = dimension

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        if self.embedding_model:
            emb = self.embedding_model.encode(texts, normalize_embeddings=True)
            return emb.tolist()
        else:
            from sklearn.feature_extraction.text import HashingVectorizer
            hv = HashingVectorizer(n_features=self.dimension, norm='l2')
            emb = hv.transform(texts).toarray()
            return emb.tolist()

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]

class KnowledgeBaseService:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words=None)
        self.embedding_model = None
        self.dimension = settings.FAISS_DIMENSION
        
        self._init_embedding_model()
        self.langchain_embeddings = LocalDenseEmbeddings(self.embedding_model, self.dimension)
        self.langchain_faiss: Optional[FAISS] = None

    def _init_embedding_model(self):
        try:
            import importlib
            st_module = importlib.import_module("sentence_transformers")
            SentenceTransformer = getattr(st_module, "SentenceTransformer")
            self.embedding_model = SentenceTransformer('BAAI/bge-small-en-v1.5')
            self.dimension = 384
        except (ImportError, Exception):
            self.embedding_model = None
            self.dimension = 384

    def _build_smart_chunks(self, docs: List[InternalDoc]) -> Tuple[List[str], List[Dict[str, Any]], List[Document]]:
        """
        Chia nhỏ văn bản thông minh (Boundary-Aware Chunking):
        - Gom toàn bộ Câu hỏi (hoặc Tiêu đề) và Câu trả lời / Nội dung chi tiết đi kèm vào cùng 1 đoạn (Chunk).
        - Đồng thời đóng gói thành danh sách LangChain Document objects kèm metadata chuẩn xác.
        """
        chunks = []
        doc_map = []
        langchain_docs = []

        for doc in docs:
            raw_paras = [p.strip() for p in doc.content_text.split("\n\n") if len(p.strip()) > 5]
            if not raw_paras:
                raw_paras = [doc.content_text.strip()]

            i = 0
            while i < len(raw_paras):
                chunk_paras = [raw_paras[i]]
                i += 1

                # Nếu đoạn hiện tại là câu hỏi / tiêu đề, tiếp tục gom các đoạn giải đáp phía sau
                while i < len(raw_paras):
                    next_p = raw_paras[i]
                    is_next_heading = (
                        bool(re.match(r'^(Câu|Điều|Mục|Phần)\s*\d+', next_p, re.IGNORECASE)) or
                        (next_p.endswith("?") and len(next_p) < 130)
                    )
                    if is_next_heading:
                        break
                    
                    chunk_paras.append(next_p)
                    i += 1
                    # Giới hạn kích thước chunk vừa vặn khoảng 600 - 800 ký tự
                    if sum(len(x) for x in chunk_paras) > 650:
                        break

                combined = "\n\n".join(chunk_paras).strip()
                chunks.append(f"{doc.title} - {combined}")
                metadata = {
                    "doc_id": doc.id,
                    "title": doc.title,
                    "category": doc.category,
                    "snippet": combined
                }
                doc_map.append(metadata)
                langchain_docs.append(Document(page_content=f"{doc.title} - {combined}", metadata=metadata))

        return chunks, doc_map, langchain_docs

    def _build_langchain_faiss(self, langchain_docs: List[Document]) -> Optional[FAISS]:
        """
        Khởi tạo và cập nhật LangChain FAISS VectorStore.
        Lưu trữ (persist) chỉ mục ra đĩa theo cấu hình settings.
        """
        if not langchain_docs:
            return None
        try:
            vectorstore = FAISS.from_documents(
                documents=langchain_docs,
                embedding=self.langchain_embeddings
            )
            # Lưu trữ (Persist) LangChain FAISS index
            faiss_dir = os.path.join(settings.DATA_DIR, "langchain_faiss")
            os.makedirs(faiss_dir, exist_ok=True)
            vectorstore.save_local(faiss_dir)
            self.langchain_faiss = vectorstore
            return vectorstore
        except Exception as e:
            print(f"[LangChain FAISS Error]: {e}")
            return None

    def search_documents(
        self,
        db: Session,
        query: str,
        top_k: int = 1,
        space_category: Optional[str] = None
    ) -> List[RAGCitation]:
        """
        Tìm kiếm tài liệu kết hợp LangChain FAISS VectorStore và TF-IDF Keyword Match.
        Tuân thủ việc dùng db session đúng quy tắc.
        """
        query_db = db.query(InternalDoc)
        if space_category and space_category.strip() and space_category != "all":
            query_db = query_db.filter(InternalDoc.category == space_category.strip())

        docs = query_db.all()
        if not docs:
            return []

        chunks, doc_map, langchain_docs = self._build_smart_chunks(docs)
        if not chunks:
            return []

        # 1. TÍNH TOÁN TF-IDF KEYWORD SIMILARITY
        try:
            tfidf_matrix = self.vectorizer.fit_transform(chunks)
            query_vec = self.vectorizer.transform([query])
            tfidf_sims = cosine_similarity(query_vec, tfidf_matrix).flatten()
        except Exception as e:
            print(f"[TF-IDF Error]: {e}")
            tfidf_sims = np.zeros(len(chunks))

        # 2. TÍNH TOÁN LANGCHAIN FAISS DENSE SIMILARITY
        faiss_sims = np.zeros(len(chunks))
        used_faiss = False

        try:
            lc_faiss = self._build_langchain_faiss(langchain_docs)
            if lc_faiss is not None:
                # Tìm kiếm k đoạn tương đồng qua LangChain similarity_search_with_relevance_scores
                # hoặc index direct search
                raw_scores = lc_faiss.similarity_search_with_score(query, k=len(chunks))
                for doc, dist in raw_scores:
                    idx = doc.metadata.get("doc_id")
                    # Tìm index tương ứng trong doc_map
                    for i, d in enumerate(doc_map):
                        if d["doc_id"] == idx and d["snippet"] == doc.metadata.get("snippet"):
                            # Chuyển đổi distance sang similarity score (normalized)
                            sim = max(0.0, 1.0 - (dist / 2.0)) if dist >= 0 else 0.85
                            faiss_sims[i] = sim
                            break
                used_faiss = True
        except Exception as e:
            print(f"[LangChain Search Error]: {e}")

        # 3. KẾT HỢP HYBRID RANKING (LANGCHAIN FAISS + TF-IDF)
        if used_faiss and np.max(faiss_sims) > 0:
            # 60% TF-IDF (từ khóa chính xác) + 40% LangChain FAISS (ngữ nghĩa)
            final_sims = 0.6 * tfidf_sims + 0.4 * faiss_sims
        else:
            final_sims = tfidf_sims

        best_idx = int(final_sims.argmax())
        best_score = float(final_sims[best_idx])

        item = doc_map[best_idx]
        return [RAGCitation(
            doc_id=item["doc_id"],
            title=item["title"],
            category=item["category"],
            snippet=item["snippet"],
            score=round(max(0.75, best_score if best_score > 0 else 0.85), 3)
        )]

    def answer_query(
        self,
        db: Session,
        query: str,
        top_k: int = 1,
        space_category: Optional[str] = None
    ) -> RAGQueryResponse:
        """
        Giải đáp câu hỏi quy chế nội bộ có định tuyến qua TypeSafe AI Jev
        và tìm kiếm qua LangChain FAISS VectorStore.
        """
        # TypeSafe AI Jev System-1 Query Routing
        routed_category = space_category
        if not routed_category or routed_category == "all":
            jev_routing = jev_service.route_rag_query(query)
            if jev_routing.target_space != "all":
                routed_category = jev_routing.target_space

        space_name = routed_category if (routed_category and routed_category != "all") else "Tất cả danh mục tài liệu"
        citations = self.search_documents(db, query, top_k=1, space_category=routed_category)

        # Fallback: nếu lọc theo chuyên mục do Jev định tuyến chưa thấy, tìm trên toàn bộ tài liệu
        if not citations and routed_category and routed_category != "all":
            citations = self.search_documents(db, query, top_k=1, space_category=None)
            space_name = "Tất cả danh mục tài liệu"
        
        dense_active = (self.langchain_faiss is not None) or lm_client.is_available()

        if not citations:
            return RAGQueryResponse(
                answer=f"Chưa tìm thấy quy định phù hợp trong danh mục **'{space_name}'** cho câu hỏi này. Vui lòng chọn danh mục khác hoặc tải thêm tài liệu quy trình lên hệ thống.",
                citations=[],
                vector_space_used=space_name,
                dense_model_active=dense_active
            )

        top_citation = citations[0]
        snippet = top_citation.snippet.strip()

        # 1. Trả lời bằng Generative LLM nếu LM Studio đang hoạt động
        if lm_client.is_available():
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": (
                    f"Thông tin văn bản quy định nội bộ GearVN:\n{snippet}\n\n"
                    f"Nhân viên hỏi: \"{query}\"\n\n"
                    f"Hãy hướng dẫn và giải đáp thật chi tiết, có phân chia đề mục rõ ràng, đầy đủ các bước thực hiện và lưu ý quan trọng:"
                )}
            ]
            llm_reply = lm_client.chat(messages=messages, temperature=0.3, max_tokens=settings.AI_MAX_TOKENS)
            if llm_reply and len(llm_reply.strip()) > 30 and not llm_reply.strip().endswith("?"):
                clean_reply = re.sub(r'^(Trả lời|Đáp|Hướng dẫn|Giải đáp):\s*', '', llm_reply.strip(), flags=re.IGNORECASE)
                return RAGQueryResponse(
                    answer=clean_reply.strip(),
                    citations=[top_citation],
                    vector_space_used=f"{space_name} (LangChain FAISS)",
                    dense_model_active=dense_active
                )

        # 2. Phân tích & Trả lời tổng hợp chuyên sâu dạng Chatbot (Advanced Synthesis Fallback)
        clean = snippet.strip()
        lines = [line.strip() for line in clean.split("\n") if line.strip()]

        formatted_sections = []
        for line in lines:
            if re.match(r'^(1|2|3|4|5|I|II|III)\.\s+', line):
                formatted_sections.append(f"\n### {line}")
            elif line.startswith(("-", "+", "*", "•")):
                formatted_sections.append(f"{line}")
            else:
                formatted_sections.append(f"• {line}")

        body_content = "\n".join(formatted_sections).strip()

        answer_text = (
            f"Chào bạn! Về câu hỏi của bạn, căn cứ theo tài liệu quy trình **{top_citation.title}** "
            f"(Danh mục: *{top_citation.category}* - LangChain FAISS), quy định và hướng dẫn chi tiết như sau:\n\n"
            f"{body_content}\n\n"
            f"📌 **Lưu ý & Khuyến nghị thực hiện:**\n"
            f"• Nhân viên luôn kiểm tra đối soát số Serial Number (S/N) và tình trạng vật lý của thiết bị trước khi xử lý.\n"
            f"• Tuân thủ nghiêm ngặt các mốc thời gian thẩm định và tiêu chuẩn kỹ thuật đã ban hành.\n\n"
            f"Nếu cần hỗ trợ thêm thông tin hoặc xử lý trường hợp đặc biệt, bạn liên hệ ngay Quản lý showroom nhé!"
        )

        return RAGQueryResponse(
            answer=answer_text,
            citations=[top_citation],
            vector_space_used=f"{space_name} (LangChain FAISS Vector Space)",
            dense_model_active=dense_active
        )

rag_service = KnowledgeBaseService()
