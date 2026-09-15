'use client';

import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';

// Anti-Garbage-Collection hack for Chrome TTS bug
let globalUtterance: SpeechSynthesisUtterance | null = null;

export default function Home() {
  const [messages, setMessages] = useState<{ sender: string; text: string }[]>([
    { sender: 'Avatar', text: 'Hello! I am your AI assistant from Sham Marianas. How can I help you today?' }
  ]);
  const [inputMessage, setInputMessage] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  
  // Split loading states for better UX
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [loading, setLoading] = useState(false);
  
  // Audio & Video references
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [cameraActive, setCameraActive] = useState(false);

  // Auto-scroll reference for chat box
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  // 1. Force load voices immediately on mount
  useEffect(() => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.getVoices();
      window.speechSynthesis.onvoiceschanged = () => {
        window.speechSynthesis.getVoices();
      };
    }
  }, []);

  // Auto-scroll to bottom whenever messages or loading state changes
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading, isTranscribing]);

  // Clean up hardware resources when component unmounts
  useEffect(() => {
    return () => {
      stopCamera();
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  // Clear chat history
  const clearChat = () => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    setMessages([
      { sender: 'Avatar', text: 'Hello! I am your AI assistant from Sham Marianas. How can I help you today?' }
    ]);
  };

  // ==========================================
  // CAMERA CONTROLS
  // ==========================================
  const toggleCamera = async () => {
    if (cameraActive) {
      stopCamera();
    } else {
      await startCamera();
    }
  };

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        setCameraActive(true);
      }
    } catch (err) {
      console.error("Webcam access error:", err);
      setCameraActive(false);
    }
  };

  const stopCamera = () => {
    if (videoRef.current && videoRef.current.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach(track => track.stop());
      videoRef.current.srcObject = null;
    }
    setCameraActive(false);
  };

  // ==========================================
  // CHAT & VOICE ENGINE (FIXED)
  // ==========================================
  const speakText = (text: string) => {
    if (isMuted || !('speechSynthesis' in window)) return;
    
    // Stop any current speech
    window.speechSynthesis.cancel();

    if (!text) return;

    // Clean up markdown characters for natural speech
    const cleanTextForSpeech = text
      .replace(/\*/g, '')
      .replace(/#/g, '')
      .replace(/https?:\/\/\S+/g, 'a link provided in the chat')
      .trim();

    // Attach to global variable to prevent Chrome from deleting it mid-speech
    globalUtterance = new SpeechSynthesisUtterance(cleanTextForSpeech);
    
    const voices = window.speechSynthesis.getVoices();
    const englishVoice = voices.find(v => v.lang.startsWith('en') && v.name.includes('Google')) 
                      || voices.find(v => v.lang.startsWith('en')) 
                      || voices[0];
    
    if (englishVoice) {
      globalUtterance.voice = englishVoice;
    }
    globalUtterance.rate = 1.0;
    globalUtterance.volume = 1.0;
    globalUtterance.onerror = (e) => console.error('Speech synthesis error/blocked:', e);
    
    // Speak and immediately resume to bypass browser pause bugs
    window.speechSynthesis.speak(globalUtterance);
    window.speechSynthesis.resume();
  };

  const sendMessageToBackend = async (textToSend: string, isVoiceInput: boolean = false) => {
    if (!textToSend.trim()) return;

    // UNLOCK THE SPEECH ENGINE IMMEDIATELY on user interaction
    if ('speechSynthesis' in window && !isMuted) {
      window.speechSynthesis.resume();
    }

    const userMsg = { sender: 'You', text: textToSend };
    setMessages((prev) => [...prev, userMsg]);
    setInputMessage('');
    setLoading(true);

    try {
      const response = await fetch('http://127.0.0.1:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: textToSend }),
      });

      const data = await response.json();
      const avatarReply = data.reply || "I couldn't process that.";

      setMessages((prev) => [...prev, { sender: 'Avatar', text: avatarReply }]);

      // NOW SPEAK THE ACTUAL REPLY
      speakText(avatarReply);

    } catch (error) {
      console.error('API Error:', error);
      setMessages((prev) => [...prev, { sender: 'Avatar', text: 'Error connecting to Python backend.' }]);
    } finally {
      setLoading(false);
    }
  };

  // ==========================================
  // AUDIO RECORDING & TRANSCRIPTION
  // ==========================================
  const toggleListening = async () => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      
      if (!isListening) {
        const unlock = new SpeechSynthesisUtterance('');
        unlock.volume = 0;
        window.speechSynthesis.speak(unlock);
      }
    }

    if (isListening) {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
      setIsListening(false);
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        
        let mimeType = 'audio/webm';
        if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
          mimeType = 'audio/webm;codecs=opus';
        } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
          mimeType = 'audio/mp4';
        }

        const mediaRecorder = new MediaRecorder(stream, { mimeType });
        mediaRecorderRef.current = mediaRecorder;
        audioChunksRef.current = [];

        mediaRecorder.ondataavailable = (event) => {
          if (event.data && event.data.size > 0) {
            audioChunksRef.current.push(event.data);
          }
        };

        mediaRecorder.onstop = async () => {
          const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
          stream.getTracks().forEach(track => track.stop());
          await sendAudioToBackend(audioBlob);
        };

        mediaRecorder.start(250);
        setIsListening(true);
      } catch (err) {
        console.error("Microphone permission error:", err);
        alert("Microphone access is required to use voice input.");
      }
    }
  };

  const sendAudioToBackend = async (audioBlob: Blob) => {
    if (audioBlob.size === 0) {
      alert("No speech detected. Please speak louder or verify microphone settings.");
      return;
    }

    setIsTranscribing(true);
    const formData = new FormData();
    formData.append('file', audioBlob, 'speech.webm');

    try {
      const response = await fetch('http://127.0.0.1:8000/transcribe', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Transcription server error");
      }

      const data = await response.json();
      const transcribedText = data.text ? data.text.trim() : '';

      if (transcribedText) {
        await sendMessageToBackend(transcribedText, true);
      } else {
        alert("Could not transcribe audio. Please try speaking again.");
      }
    } catch (error) {
      console.error('Audio Transcription Connection Error:', error);
      alert('Failed to connect to Python backend at http://127.0.0.1:8000/transcribe.');
    } finally {
      setIsTranscribing(false);
    }
  };

  return (
    <main className="flex h-screen w-screen bg-gray-950 text-white overflow-hidden p-6 gap-6">
      
      {/* LEFT COLUMN: Controls, Vision, & 3D Avatar Box */}
      <div className="w-1/3 flex flex-col gap-4">
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4 flex flex-col h-full gap-4 shadow-xl overflow-y-auto">
          <div>
            <h1 className="text-xl font-bold text-cyan-400">Sham Marianas AI</h1>
            <p className="text-xs text-gray-400 mb-2">RAG Powered Assistant</p>
          </div>

          {/* Vision Feed Container */}
          <div className="relative w-full aspect-video bg-black rounded-xl overflow-hidden border border-gray-700 flex items-center justify-center">
            <video 
              ref={videoRef} 
              autoPlay 
              playsInline 
              muted 
              className={`w-full h-full object-cover transform -scale-x-100 ${!cameraActive && 'hidden'}`} 
            />
            {!cameraActive && (
              <span className="text-xs text-gray-500">Live Vision Disabled</span>
            )}
            
            <button
              onClick={toggleCamera}
              className={`absolute top-2 right-2 text-xs px-2.5 py-1 rounded-md font-semibold transition border ${
                cameraActive 
                  ? 'bg-red-600/80 border-red-500 text-white hover:bg-red-600' 
                  : 'bg-cyan-600/80 border-cyan-500 text-white hover:bg-cyan-600'
              }`}
            >
              {cameraActive ? '🔴 Close WebCam' : '📷 Open WebCam'}
            </button>
          </div>

          {/* 3D Avatar Viewport Container Placeholder */}
          <div className="flex-1 bg-gray-950/80 border border-cyan-500/20 rounded-xl p-4 flex flex-col items-center justify-center text-center relative overflow-hidden group">
            <div className="absolute inset-0 bg-cyan-500/5 blur-xl group-hover:bg-cyan-500/10 transition"></div>
            <div className="w-16 h-16 rounded-full border-2 border-dashed border-cyan-400/50 flex items-center justify-center mb-2 animate-spin-slow">
              <span className="text-2xl">🤖</span>
            </div>
            <p className="text-xs font-semibold text-cyan-400 z-10">3D Avatar Viewport</p>
            <p className="text-[10px] text-gray-500 z-10">Future Three.js / Canvas Integration Box</p>
          </div>
        </div>
      </div>

      {/* RIGHT COLUMN: Chat Interface */}
      <div className="w-2/3 flex flex-col bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl justify-between">
        
        {/* Chat Header Actions */}
        <div className="flex justify-between items-center pb-4 mb-4 border-b border-gray-800">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Conversation Stream</span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                setIsMuted(!isMuted);
                if (!isMuted && 'speechSynthesis' in window) window.speechSynthesis.cancel();
              }}
              title={isMuted ? "Unmute Voice Output" : "Mute Voice Output"}
              className="text-xs px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 transition flex items-center gap-1.5"
            >
              {isMuted ? '🔇 Voice Muted' : '🔊 Voice Active'}
            </button>
            <button
              onClick={clearChat}
              title="Clear Chat History"
              className="text-xs px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-red-950/50 hover:border-red-800 border border-gray-700 text-gray-300 hover:text-red-400 transition"
            >
              Clear Chat
            </button>
          </div>
        </div>

        {/* Chat History Box */}
        <div className="flex-1 overflow-y-auto space-y-4 pr-2 mb-4">
          {messages.map((msg, index) => (
            <div
              key={index}
              className={`p-4 rounded-2xl max-w-[80%] text-sm ${
                msg.sender === 'You'
                  ? 'bg-cyan-600 ml-auto text-white'
                  : 'bg-gray-800 text-gray-200 border border-gray-700'
              }`}
            >
              <p className="text-[10px] font-semibold opacity-60 mb-1 tracking-wider uppercase">{msg.sender}</p>
              
              <div className="leading-relaxed prose prose-invert max-w-none text-sm">
                <ReactMarkdown
                  components={{
                    a: ({ node, ...props }) => (
                      <a
                        {...props}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-cyan-400 underline hover:text-cyan-300 font-medium"
                      />
                    ),
                    ul: ({ node, ...props }) => <ul {...props} className="list-disc pl-4 space-y-1 my-1" />,
                    li: ({ node, ...props }) => <li {...props} className="text-sm" />
                  }}
                >
                  {msg.text}
                </ReactMarkdown>
              </div>
            </div>
          ))}

          {/* Centered Compact Dynamic Status Pill */}
          {(isTranscribing || (loading && !isTranscribing)) && (
            <div className="flex justify-center my-2">
              <div className="inline-flex items-center gap-2 bg-gray-800/90 text-cyan-400 px-4 py-1.5 rounded-full text-xs animate-pulse border border-cyan-500/30 w-fit shadow-lg">
                {isTranscribing ? '🎙️ Transcribing audio...' : '🤖 Assistant is thinking...'}
              </div>
            </div>
          )}
          
          <div ref={chatEndRef} />
        </div>

        {/* Input Form & Audio Recorder Microphone Button */}
        <div className="flex gap-2 items-center bg-gray-950 border border-gray-800 rounded-xl p-2 focus-within:border-cyan-500 transition">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                sendMessageToBackend(inputMessage, false);
              }
            }}
            placeholder={isListening ? "Recording... Click microphone button to stop and send" : "Ask a question or type something..."}
            className="flex-1 bg-transparent px-3 py-1 text-sm focus:outline-none text-white"
            disabled={isListening || isTranscribing}
          />

          <button
            onClick={toggleListening}
            title={isListening ? "Stop & Send Audio" : "Record Voice Input"}
            className={`p-2.5 rounded-lg transition text-base flex items-center justify-center ${
              isListening
                ? 'bg-red-600 text-white animate-pulse border border-red-400'
                : 'bg-gray-800 hover:bg-gray-700 text-cyan-400 border border-gray-700'
            }`}
          >
            {isListening ? '🛑' : '🎤'}
          </button>

          <button
            onClick={() => sendMessageToBackend(inputMessage, false)}
            disabled={isListening || isTranscribing}
            className="bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 px-5 py-2.5 rounded-lg text-sm font-semibold transition shadow-lg shadow-cyan-900/20 text-white"
          >
            Send
          </button>
        </div>

      </div>
    </main>
  );
}