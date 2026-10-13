// =========================================================================
// GEARVN AI SALES ASSISTANT WIDGET WITH INTERACTIVE PRODUCT CARDS
// =========================================================================

// Tự động chèn CSS cho Product Cards trực quan trong Chatbot
(function injectAIChatStyles() {
    if (document.getElementById("ai-chat-custom-styles")) return;
    const style = document.createElement("style");
    style.id = "ai-chat-custom-styles";
    style.innerHTML = `
        .ai-product-carousel {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin: 10px 0 6px 0;
            width: 100%;
        }
        .ai-mini-card {
            display: flex;
            align-items: center;
            gap: 10px;
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 8px 12px;
            cursor: pointer;
            transition: all 0.2s ease;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            text-decoration: none;
            color: inherit;
        }
        .ai-mini-card:hover {
            border-color: #ef4444;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(239, 68, 68, 0.15);
        }
        .ai-card-thumb {
            width: 52px;
            height: 52px;
            object-fit: contain;
            border-radius: 6px;
            background: #f8fafc;
            padding: 2px;
            flex-shrink: 0;
        }
        .ai-card-content {
            flex: 1;
            min-width: 0;
        }
        .ai-card-brand {
            font-size: 10px;
            font-weight: 700;
            color: #64748b;
            text-transform: uppercase;
        }
        .ai-card-title {
            font-size: 12px;
            font-weight: 600;
            color: #0f172a;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            margin: 1px 0 3px 0;
        }
        .ai-card-prices {
            display: flex;
            align-items: baseline;
            gap: 6px;
        }
        .ai-card-promo {
            font-size: 13px;
            font-weight: 800;
            color: #ef4444;
        }
        .ai-card-orig {
            font-size: 11px;
            color: #94a3b8;
            text-decoration: line-through;
        }
        .ai-card-btn {
            font-size: 11px;
            font-weight: 600;
            color: #ef4444;
            background: #fef2f2;
            padding: 4px 8px;
            border-radius: 6px;
            display: flex;
            align-items: center;
            gap: 4px;
            white-space: nowrap;
            flex-shrink: 0;
            transition: background 0.2s;
        }
        .ai-mini-card:hover .ai-card-btn {
            background: #ef4444;
            color: #ffffff;
        }
    `;
    document.head.appendChild(style);
})();

const AIChat = {
    isOpen: false,

    toggle() {
        this.isOpen = !this.isOpen;
        const chatWindow = document.getElementById("aiChatWindow");
        if (chatWindow) {
            chatWindow.style.display = this.isOpen ? "flex" : "none";
            if (this.isOpen) {
                document.getElementById("aiChatInput")?.focus();
            }
        }
    },

    quickAsk(text) {
        const input = document.getElementById("aiChatInput");
        if (input) {
            input.value = text;
            this.send();
        }
    },

    // Hàm render thẻ sản phẩm trực quan khi AI gợi ý
    renderProductCards(products, targetContainer) {
        if (!products || products.length === 0 || !targetContainer) return;

        const carousel = document.createElement("div");
        carousel.className = "ai-product-carousel";

        products.forEach(p => {
            const card = document.createElement("a");
            card.className = "ai-mini-card";
            card.href = `/product/${p.slug}`;
            card.target = "_blank"; // Mở tab mới hoặc đổi thành "_self" nếu muốn chuyển trang trực tiếp

            const promoFormatted = Number(p.promo_price || 0).toLocaleString("vi-VN") + "đ";
            const origFormatted = p.original_price > p.promo_price
                ? Number(p.original_price).toLocaleString("vi-VN") + "đ"
                : "";

            const thumbImg = p.thumbnail || "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=200";

            card.innerHTML = `
                <img src="${thumbImg}" class="ai-card-thumb" alt="${p.name}" onerror="this.src='/static/images/default-product.png'">
                <div class="ai-card-content">
                    <div class="ai-card-brand">${p.brand || 'CHÍNH HÃNG'}</div>
                    <div class="ai-card-title" title="${p.name}">${p.name}</div>
                    <div class="ai-card-prices">
                        <span class="ai-card-promo">${promoFormatted}</span>
                        ${origFormatted ? `<span class="ai-card-orig">${origFormatted}</span>` : ""}
                    </div>
                </div>
                <div class="ai-card-btn">
                    Xem ngay <i class="fa-solid fa-arrow-up-right-from-square"></i>
                </div>
            `;
            carousel.appendChild(card);
        });

        targetContainer.appendChild(carousel);
    },

    async send() {
        const input = document.getElementById("aiChatInput");
        const body = document.getElementById("aiChatBody");
        if (!input || !body) return;

        const message = input.value.trim();
        if (!message) return;

        // 1. Thêm bubble tin nhắn của người dùng
        this.appendMessage("user", message);
        input.value = "";

        // 2. Tạo bubble của AI đang chờ streaming
        const aiBubble = document.createElement("div");
        aiBubble.className = "chat-bubble ai";
        aiBubble.id = "aiStreamingBubble";
        aiBubble.innerHTML = `<span style="opacity:0.7;"><i class="fa-solid fa-spinner fa-spin"></i> Trợ lý AI đang tra cứu kho hàng & thông số...</span>`;
        body.appendChild(aiBubble);
        body.scrollTop = body.scrollHeight;

        let accumulatedText = "";
        let recommendedProducts = [];
        let suggestedQuestions = [];

        try {
            const res = await fetch("/api/v1/ai/chat/stream", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: message })
            });

            if (!res.ok) throw new Error("HTTP error " + res.status);

            const reader = res.body.getReader();
            const decoder = new TextDecoder("utf-8");
            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n\n");
                buffer = lines.pop();

                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        const eventData = JSON.parse(line.replace("data: ", ""));

                        if (eventData.type === "products") {
                            // Lưu danh sách sản phẩm hệ thống gợi ý
                            recommendedProducts = eventData.recommended_products || [];
                        } else if (eventData.type === "content") {
                            accumulatedText += eventData.chunk;
                            // Format markdown câu trả lời
                            let formatted = accumulatedText
                                .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
                                .replace(/\*(.*?)\*/g, "<em>$1</em>")
                                .replace(/\n/g, "<br>");
                            aiBubble.innerHTML = formatted;
                            body.scrollTop = body.scrollHeight;
                        } else if (eventData.type === "done") {
                            suggestedQuestions = eventData.suggested_questions || [];
                        }
                    }
                }
            }

            // 3. Render các thẻ sản phẩm trực quan ngay dưới câu trả lời của AI
            if (recommendedProducts.length > 0) {
                this.renderProductCards(recommendedProducts, body);
                body.scrollTop = body.scrollHeight;
            }

            // 4. Render các nút câu hỏi gợi ý dạng Chip
            if (suggestedQuestions.length > 0) {
                const chipsBox = document.createElement("div");
                chipsBox.style.cssText = "display:flex;flex-wrap:wrap;gap:4px;margin-top:6px;";
                suggestedQuestions.slice(0, 3).forEach(q => {
                    const btn = document.createElement("button");
                    btn.className = "btn btn-outline";
                    btn.style.cssText = "font-size:11px;padding:4px 8px;border-radius:12px;background:#f1f5f9;cursor:pointer;";
                    btn.innerText = q;
                    btn.onclick = () => AIChat.quickAsk(q);
                    chipsBox.appendChild(btn);
                });
                body.appendChild(chipsBox);
                body.scrollTop = body.scrollHeight;
            }

        } catch (err) {
            console.error("Lỗi AI Stream:", err);
            aiBubble.innerHTML = "Xin lỗi, đã xảy ra lỗi kết nối tới máy chủ AI. Bạn vui lòng thử lại sau giây lát.";
        }
        body.scrollTop = body.scrollHeight;
    },

    appendMessage(role, htmlContent) {
        const body = document.getElementById("aiChatBody");
        if (!body) return;

        const bubble = document.createElement("div");
        bubble.className = `chat-bubble ${role}`;
        bubble.innerHTML = htmlContent;
        body.appendChild(bubble);
        body.scrollTop = body.scrollHeight;
    }
};
