
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

    async send() {
        const input = document.getElementById("aiChatInput");
        const body = document.getElementById("aiChatBody");
        if (!input || !body) return;

        const message = input.value.trim();
        if (!message) return;

        this.appendMessage("user", message);
        input.value = "";

        const aiBubble = document.createElement("div");
        aiBubble.className = "chat-bubble ai";
        aiBubble.id = "aiStreamingBubble";
        aiBubble.innerHTML = `<span style="opacity:0.7;"><i class="fa-solid fa-spinner fa-spin"></i> Trợ lý AI đang tra cứu dữ liệu...</span>`;
        body.appendChild(aiBubble);
        body.scrollTop = body.scrollHeight;

        let accumulatedText = "";
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

                        if (eventData.type === "content") {
                            accumulatedText += eventData.chunk;
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
