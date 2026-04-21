import { useState, useEffect, useRef, useContext } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { apiChatMessageStream } from '../logic/apis.js';
import { CustomerContext } from './contexts.js';

const SESSION_STORAGE_KEY = 'chat_assistant_session_id';

const WaveDots = () => (
  <span className="inline-flex items-center gap-0.5">
    Thinking
    <span className="wave-dot"></span>
    <span className="wave-dot"></span>
    <span className="wave-dot"></span>
  </span>
);

const extractCharts = (content) => {
  const chartRegex = /<chart>(data:image\/[^;]+;base64,[^<]+)<\/chart>/g;
  const images = [];
  let match;
  while ((match = chartRegex.exec(content)) !== null) images.push(match[1]);
  const cleanContent = content.replace(/<chart>data:image\/[^;]+;base64,[^<]+<\/chart>/g, '');
  return { cleanContent, images };
};

const generateUUID = () =>
  'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });

export const ChatAssistant = () => {
  const customer = useContext(CustomerContext);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [streamingContent, setStreamingContent] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  useEffect(() => { scrollToBottom(); }, [messages, streamingContent]);

  useEffect(() => {
    let stored = localStorage.getItem(SESSION_STORAGE_KEY);
    if (!stored) { stored = generateUUID(); localStorage.setItem(SESSION_STORAGE_KEY, stored); }
    setSessionId(stored);
    setMessages([]);
  }, []);

  const handleSendMessage = async () => {
    const prompt = inputValue.trim();
    if (!prompt || isLoading) return;

    setMessages(prev => [...prev, { type: 'outgoing', content: prompt, timestamp: new Date().toISOString() }]);
    setInputValue('');
    setIsLoading(true);
    setStreamingContent('');
    setIsStreaming(true);

    try {
      let accumulatedContent = '';
      const success = await apiChatMessageStream(
        { prompt, session_id: sessionId, identity: customer.customer_username },
        (chunk) => {
          if (chunk.type === 'text' && chunk.content) {
            accumulatedContent += typeof chunk.content === 'string' ? chunk.content : '';
            setStreamingContent(accumulatedContent);
          } else if (chunk.type === 'done') {
            setIsStreaming(false);
          } else if (chunk.result) {
            accumulatedContent = typeof chunk.result === 'string' ? chunk.result : (chunk.result.text || '');
            setStreamingContent(accumulatedContent);
            setIsStreaming(false);
          }
        }
      );

      setStreamingContent('');
      setIsStreaming(false);
      setIsLoading(false);

      if (accumulatedContent) {
        const { cleanContent, images } = extractCharts(accumulatedContent);
        setMessages(prev => [...prev, { type: 'incoming', content: cleanContent, images, timestamp: new Date().toISOString() }]);
      } else if (!success) {
        throw new Error('Stream failed');
      }
    } catch (error) {
      console.error('Chat error:', error);
      setMessages(prev => [...prev, { type: 'incoming', content: 'I apologize, but I encountered an error processing your request. Please try again.', timestamp: new Date().toISOString(), isError: true }]);
    } finally {
      setIsLoading(false);
      setIsStreaming(false);
      setStreamingContent('');
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    const newId = generateUUID();
    setSessionId(newId);
    localStorage.setItem(SESSION_STORAGE_KEY, newId);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendMessage(); }
  };

  return (
    <div className="rounded-lg border border-border bg-card flex flex-col" style={{ height: '720px' }}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-violet-500 to-blue-500 flex items-center justify-center">
            <svg className="h-4 w-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <div>
            <h2 className="font-semibold text-sm text-card-foreground">Energy Assistant</h2>
            <p className="text-xs text-muted-foreground">Powered by AI</p>
          </div>
        </div>
        <button onClick={handleClearChat} disabled={isLoading} className="inline-flex items-center justify-center rounded-md text-sm h-8 px-3 border border-border bg-card hover:bg-secondary transition-colors text-muted-foreground hover:text-foreground disabled:opacity-50 cursor-pointer">
          Clear chat
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 chat-scroll">
        {messages.map((message, index) => (
          <div key={index} className={`flex gap-3 max-w-[85%] ${message.type === 'outgoing' ? 'ml-auto flex-row-reverse' : ''}`}>
            {message.type === 'outgoing' ? (
              <div className="h-7 w-7 rounded-full bg-secondary flex-shrink-0 flex items-center justify-center mt-1 text-xs font-medium text-foreground">
                {(customer?.first_name || '')[0]}{(customer?.last_name || '')[0]}
              </div>
            ) : (
              <div className="h-7 w-7 rounded-full bg-gradient-to-br from-violet-500 to-blue-500 flex-shrink-0 flex items-center justify-center mt-1">
                <svg className="h-3.5 w-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
            )}
            <div className={message.type === 'outgoing' ? 'chat-bubble-user px-4 py-3' : 'chat-bubble-ai px-4 py-3'}>
              <div className="text-sm prose prose-sm max-w-none dark:prose-invert">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
              </div>
              {message.images && message.images.length > 0 && (
                <div className="mt-3 flex flex-col gap-3">
                  {message.images.map((imageData, imgIndex) => (
                    <img key={imgIndex} src={imageData} alt={`Chart ${imgIndex + 1}`} className="max-w-full h-auto rounded-lg border border-border" />
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Streaming / Loading */}
        {isLoading && (
          <div className="flex gap-3 max-w-[85%]">
            <div className="h-7 w-7 rounded-full bg-gradient-to-br from-violet-500 to-blue-500 flex-shrink-0 flex items-center justify-center mt-1">
              <svg className="h-3.5 w-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
            </div>
            <div className="chat-bubble-ai px-4 py-3">
              {streamingContent ? (
                <div className="text-sm prose prose-sm max-w-none dark:prose-invert">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{streamingContent.replace(/<chart>data:image\/[^;]+;base64,[^<]+<\/chart>/g, '')}</ReactMarkdown>
                </div>
              ) : (
                <WaveDots />
              )}
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-border">
        <div className="flex gap-2">
          <div className={`flex-1 flex items-center rounded-md border bg-card px-3 focus-within:ring-2 focus-within:ring-ring/30 ${isLoading ? 'chat-input-glow border-transparent' : 'border-border'}`}>
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your energy usage..."
              disabled={isLoading}
              className="flex-1 bg-transparent text-sm py-2.5 outline-none placeholder:text-muted-foreground text-foreground disabled:opacity-50"
              aria-label="Chat message input"
            />
          </div>
          <button
            onClick={handleSendMessage}
            disabled={isLoading || !inputValue.trim()}
            className="inline-flex items-center justify-center rounded-md h-10 w-10 bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 cursor-pointer"
            aria-label="Send message"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14m-7-7l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
};
