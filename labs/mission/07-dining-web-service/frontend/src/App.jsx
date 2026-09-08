import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import ChatBubble from "@cloudscape-design/chat-components/chat-bubble";
import Avatar from "@cloudscape-design/chat-components/avatar";
import PromptInput from "@cloudscape-design/components/prompt-input";
import AppLayout from "@cloudscape-design/components/app-layout";
import SideNavigation from "@cloudscape-design/components/side-navigation";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import { applyMode, Mode } from "@cloudscape-design/global-styles";

const API_URL = import.meta.env.VITE_API_URL;

function newConversation() {
  return {
    id: crypto.randomUUID(),
    title: "새 대화",
    messages: [],
  };
}

// 대화의 첫 사용자 메시지로 사이드바 제목을 만든다. 너무 길면 잘라낸다.
function titleFromFirstMessage(text) {
  const trimmed = text.trim();
  return trimmed.length > 24 ? `${trimmed.slice(0, 24)}...` : trimmed;
}

// AI 응답은 마크다운(제목·굵게·목록)으로 오므로 렌더링해야 가독성이 나온다.
// 사용자 메시지는 평문이라 그대로 표시한다.
function MessageContent({ type, content }) {
  if (type === "outgoing") {
    return <>{content}</>;
  }
  return (
    <div className="markdown-body">
      <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  );
}

function App() {
  const [conversations, setConversations] = useState(() => [newConversation()]);
  const [activeId, setActiveId] = useState(() => conversations[0].id);
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [isDark, setIsDark] = useState(
    () => window.matchMedia("(prefers-color-scheme: dark)").matches
  );
  const scrollRef = useRef(null);

  const activeConversation =
    conversations.find((c) => c.id === activeId) ?? conversations[0];

  // 새 메시지가 추가될 때마다 대화 영역을 맨 아래로 스크롤한다.
  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [activeConversation?.messages.length, loading]);

  function toggleColorMode() {
    const next = !isDark;
    setIsDark(next);
    applyMode(next ? Mode.Dark : Mode.Light);
  }

  function updateConversation(id, updater) {
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? updater(c) : c))
    );
  }

  function handleNewConversation() {
    const fresh = newConversation();
    setConversations((prev) => [fresh, ...prev]);
    setActiveId(fresh.id);
    setPrompt("");
  }

  async function handleSend() {
    const text = prompt.trim();
    if (!text || loading) return;

    const conversationId = activeConversation.id;
    const isFirstMessage = activeConversation.messages.length === 0;

    updateConversation(conversationId, (c) => ({
      ...c,
      title: isFirstMessage ? titleFromFirstMessage(text) : c.title,
      messages: [...c.messages, { type: "outgoing", content: text }],
    }));
    setPrompt("");
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: text }),
      });
      const data = await res.json();
      updateConversation(conversationId, (c) => ({
        ...c,
        messages: [
          ...c.messages,
          { type: "incoming", content: data.answer || "(응답 없음)" },
        ],
      }));
    } catch (err) {
      updateConversation(conversationId, (c) => ({
        ...c,
        messages: [
          ...c.messages,
          { type: "incoming", content: `오류가 발생했습니다: ${err.message}` },
        ],
      }));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppLayout
      toolsHide
      navigationWidth={280}
      navigation={
        <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
          <Box padding={{ horizontal: "m", top: "m" }}>
            <Button fullWidth iconName="add-plus" onClick={handleNewConversation}>
              새 대화
            </Button>
          </Box>
          <SideNavigation
            activeHref={`#${activeId}`}
            items={conversations.map((c) => ({
              type: "link",
              text: c.title,
              href: `#${c.id}`,
            }))}
            onFollow={(e) => {
              e.preventDefault();
              const id = e.detail.href.slice(1);
              setActiveId(id);
            }}
          />
        </div>
      }
      content={
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            height: "100vh",
            maxWidth: 900,
            margin: "0 auto",
          }}
        >
          <Box
            padding={{ vertical: "m", horizontal: "l" }}
            className="app-header"
          >
            <h1 style={{ margin: 0, fontSize: "1.25rem" }}>
              🍽️ 강남 다이닝 컨시어지
            </h1>
            <Button
              variant="normal"
              ariaLabel={isDark ? "라이트 모드로 전환" : "다크 모드로 전환"}
              onClick={toggleColorMode}
            >
              {isDark ? "🌙 다크" : "☀️ 라이트"}
            </Button>
          </Box>

          {/* 대화 영역만 스크롤되고, 입력창은 항상 화면 하단에 고정된다. */}
          <div
            ref={scrollRef}
            style={{ flex: 1, overflowY: "auto", padding: "0 24px" }}
          >
            {activeConversation.messages.length === 0 && !loading && (
              <Box textAlign="center" color="text-body-secondary" padding={{ top: "xxl" }}>
                강남 일대 식당 추천, 메뉴 안내, 예약 문의를 도와드립니다.
                <br />
                예: "강남역 근처 이탈리안 식당 추천해 주세요"
              </Box>
            )}

            <div style={{ display: "flex", flexDirection: "column", gap: 16, paddingBottom: 16 }}>
              {activeConversation.messages.map((msg, idx) => (
                <ChatBubble
                  key={idx}
                  type={msg.type}
                  ariaLabel={msg.type === "outgoing" ? "사용자" : "AI 어시스턴트"}
                  avatar={
                    msg.type === "outgoing" ? (
                      <Avatar ariaLabel="사용자" initials="ME" />
                    ) : (
                      <Avatar ariaLabel="AI 어시스턴트" color="gen-ai" iconName="gen-ai" />
                    )
                  }
                >
                  <MessageContent type={msg.type} content={msg.content} />
                </ChatBubble>
              ))}
              {loading && (
                <ChatBubble
                  type="incoming"
                  ariaLabel="AI 어시스턴트"
                  avatar={
                    <Avatar ariaLabel="AI 어시스턴트" color="gen-ai" iconName="gen-ai" loading />
                  }
                >
                  생각 중...
                </ChatBubble>
              )}
            </div>
          </div>

          {/* 입력창: 챗봇 UX의 핵심 — 항상 화면 맨 아래에 고정된다. */}
          <Box padding={{ vertical: "m", horizontal: "l" }}>
            <PromptInput
              value={prompt}
              onChange={({ detail }) => setPrompt(detail.value)}
              onAction={handleSend}
              actionButtonIconName="send"
              placeholder="예: 강남역 근처 이탈리안 식당 추천해 주세요"
              disabled={loading}
            />
          </Box>
        </div>
      }
    />
  );
}

export default App;
