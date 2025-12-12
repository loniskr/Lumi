import { useState, useRef, useEffect } from "react";
import {
  VSCodeButton,
  VSCodeTextField,
  VSCodeProgressRing,
} from "@vscode/webview-ui-toolkit/react";
import "./App.css";

interface ChatMessage {
  role: "user" | "bot";
  text: string;
  results?: any[]; // 검색 결과가 있을 경우
}

const App = () => {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "bot", text: "안녕하세요! '빈 폴더 찾아줘' 또는 '최근 문서 보여줘' 처럼 물어보세요." }
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  // 스크롤 자동 이동
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMsg = input;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: userMsg }]);
    setIsLoading(true);

    try {
      const res = await fetch("http://localhost:8000/api/agent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_query: userMsg }),
      });
      const data = await res.json();

      setMessages((prev) => [
        ...prev,
        { role: "bot", text: data.message, results: data.results },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "bot", text: "오류가 발생했습니다. 백엔드 연결을 확인하세요." },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main style={{ display: "flex", flexDirection: "column", height: "100vh", padding: "10px", maxWidth: "800px", margin: "0 auto" }}>
      {/* 채팅 영역 */}
      <div style={{ flex: 1, overflowY: "auto", marginBottom: "10px", padding: "10px", border: "1px solid #ccc", borderRadius: "5px" }}>
        {messages.map((msg, idx) => (
          <div key={idx} style={{ marginBottom: "15px", textAlign: msg.role === "user" ? "right" : "left" }}>
            <div style={{ 
              display: "inline-block", 
              padding: "10px", 
              borderRadius: "10px", 
              background: msg.role === "user" ? "#007acc" : "#f1f1f1", 
              color: msg.role === "user" ? "white" : "black",
              maxWidth: "80%",
              wordBreak: "break-word"
            }}>
              {msg.text}
            </div>
            
            {/* 검색 결과가 있으면 리스트로 표시 */}
            {msg.results && msg.results.length > 0 && (
              <div style={{ marginTop: "10px", textAlign: "left" }}>
                <ul style={{ listStyle: "none", padding: 0, border: "1px solid #ddd", borderRadius: "5px", overflow: "hidden" }}>
                  {msg.results.map((file: any, i: number) => (
                    <li key={i} style={{ padding: "8px", borderBottom: "1px solid #eee", background: "#fff", fontSize: "0.9em", color: "#333" }}>
                      <strong>{file.name}</strong>
                      <br />
                      <span style={{ color: "#666", fontSize: "0.8em" }}>{file.path}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
        {isLoading && <div style={{textAlign: "center"}}><VSCodeProgressRing /></div>}
        <div ref={bottomRef} />
      </div>

      {/* 입력 영역 */}
      <div style={{ display: "flex", gap: "10px" }}>
        <VSCodeTextField 
          value={input} 
          onInput={(e: any) => setInput(e.target.value)} 
          placeholder="여기에 명령을 입력하세요..." 
          style={{ flex: 1 }}
          onKeyDown={(e: any) => e.key === 'Enter' && handleSend()}
        />
        <VSCodeButton onClick={handleSend} disabled={isLoading}>전송</VSCodeButton>
      </div>
    </main>
  );
};

export default App;