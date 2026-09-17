'use client';

import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import Link from 'next/link';

let globalUtterance: SpeechSynthesisUtterance | null = null;

function Live2DAvatar({ isSpeaking }: { isSpeaking: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const modelRef = useRef<any>(null);

  useEffect(() => {
    let app: any = null;
    let isMounted = true;

    const initLive2D = async () => {
      if (!canvasRef.current) return;

      const PIXI = await import('pixi.js');
      (window as any).PIXI = PIXI;

      const { Live2DModel } = await import('pixi-live2d-display/cubism4');
      Live2DModel.registerTicker(PIXI.Ticker as any);

      if (!isMounted || !canvasRef.current) return;

      app = new PIXI.Application({
        view: canvasRef.current,
        backgroundAlpha: 0,
        autoStart: true,
        resizeTo: canvasRef.current.parentElement || undefined,
      });

      try {
        const model = await Live2DModel.from('/models/kei/kei_basic_free.model3.json', {
          autoInteract: false,
        });

        if (!isMounted) return;

        if (model.internalModel?.motionManager) {
          (model.internalModel.motionManager as any).idleMotionGroup = '';
        }

        modelRef.current = model;
        app.stage.addChild(model);

        model.anchor.set(0.5, 0.35);
        model.x = app.renderer.width / 2;
        model.y = app.renderer.height / 2;
        model.scale.set(0.28);

      } catch (err) {
        console.error('Failed to load Live2D model:', err);
      }
    };

    initLive2D();

    return () => {
      isMounted = false;
      if (app) app.destroy(true, { children: true });
    };
  }, []);

  useEffect(() => {
    let animationFrameId: number;

    const setMouthOpen = (value: number) => {
      const coreModel = modelRef.current?.internalModel?.coreModel;
      if (!coreModel) return;

      try {
        if (typeof coreModel.setParameterValueById === 'function') {
          coreModel.setParameterValueById('ParamMouthOpenY', value);
        } else if (typeof coreModel.setParamFloat === 'function') {
          coreModel.setParamFloat('ParamMouthOpenY', value);
        }
      } catch (e) {}
    };

    if (isSpeaking && modelRef.current) {
      let step = 0;
      const animateMouth = () => {
        step += 0.25;
        const openValue = Math.abs(Math.sin(step) * 0.6) + Math.random() * 0.25;
        setMouthOpen(openValue);
        animationFrameId = requestAnimationFrame(animateMouth);
      };

      animateMouth();
    } else {
      setMouthOpen(0);
    }

    return () => {
      if (animationFrameId) cancelAnimationFrame(animationFrameId);
      setMouthOpen(0);
    };
  }, [isSpeaking]);

  return (
    <div className="w-full h-full flex items-center justify-center relative">
      <canvas ref={canvasRef} className="w-full h-full max-h-[400px]" />
    </div>
  );
}

export default function Home() {
  const initialGreeting = 'Hello! I am your AI assistant from Sham Marianas. How can I help you today?';

  const [messages, setMessages] = useState<{ sender: string; text: string }[]>([
    { sender: 'Avatar', text: initialGreeting }
  ]);
  const [inputMessage, setInputMessage] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [isAvatarSpeaking, setIsAvatarSpeaking] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [loading, setLoading] = useState(false);
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [cameraActive, setCameraActive] = useState(false);
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.getVoices();
      window.speechSynthesis.onvoiceschanged = () => {
        window.speechSynthesis.getVoices();
      };
    }

    const timer = setTimeout(() => {
      speakText(initialGreeting);
    }, 800);

    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading, isTranscribing]);

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

  const clearChat = () => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    setIsAvatarSpeaking(false);
    setMessages([{ sender: 'Avatar', text: initialGreeting }]);
  };

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
      console.error('Webcam access error:', err);
      setCameraActive(false);
    }
  };

  const stopCamera = () => {
    if (videoRef.current && videoRef.current.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach((track) => track.stop());
      videoRef.current.srcObject = null;
    }
    setCameraActive(false);
  };

  const speakText = (text: string) => {
    if (isMuted || !('speechSynthesis' in window)) return;
    
    window.speechSynthesis.cancel();
    if (!text) return;

    const cleanTextForSpeech = text
      .replace(/\*/g, '')
      .replace(/#/g, '')
      .replace(/https?:\/\/\S+/g, 'a link provided in the chat')
      .trim();

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

    globalUtterance.onstart = () => setIsAvatarSpeaking(true);
    globalUtterance.onend = () => setIsAvatarSpeaking(false);
    globalUtterance.onerror = (e) => {
      console.error('Speech synthesis error:', e);
      setIsAvatarSpeaking(false);
    };
    
    window.speechSynthesis.speak(globalUtterance);
    window.speechSynthesis.resume();
  };

  const sendMessageToBackend = async (textToSend: string, isVoiceInput: boolean = false) => {
    if (!textToSend.trim()) return;

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
      speakText(avatarReply);

    } catch (error) {
      console.error('API Error:', error);
      setMessages((prev) => [...prev, { sender: 'Avatar', text: 'Error connecting to Python backend.' }]);
    } finally {
      setLoading(false);
    }
  };

  const toggleListening = async () => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      setIsAvatarSpeaking(false);
      
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
    if (audioBlob.size === 0) return;

    setIsTranscribing(true);
    const formData = new FormData();
    formData.append('file', audioBlob, 'speech.webm');

    try {
      const response = await fetch('http://127.0.0.1:8000/transcribe', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error("Transcription error");

      const data = await response.json();
      const transcribedText = data.text ? data.text.trim() : '';

      if (transcribedText) {
        await sendMessageToBackend(transcribedText, true);
      }
    } catch (error) {
      console.error('Audio Transcription Error:', error);
    } finally {
      setIsTranscribing(false);
    }
  };

  return (
    <main className="flex h-screen w-screen bg-[#0A0F0D] text-slate-200 overflow-hidden p-5 gap-5 font-sans selection:bg-teal-500/30 selection:text-teal-200">
      
      {/* LEFT COLUMN: Controls, Vision, & Live2D Avatar Frame */}
      <div className="w-1/3 flex flex-col gap-4">
        <div className="bg-[#111714]/80 border border-white/[0.08] rounded-2xl p-4 flex flex-col h-full gap-4 shadow-2xl backdrop-blur-xl overflow-y-auto">
          
          <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
            <div>
              <h1 className="text-sm font-semibold text-white tracking-tight">Resume Assistant</h1>
              <p className="text-[10px] font-mono text-teal-400/80">DEMO</p>
            </div>
            <Link 
              href="/" 
              className="text-[11px] font-medium px-2.5 py-1 rounded-md bg-white/[0.06] hover:bg-white/[0.1] text-slate-300 border border-white/[0.08] transition"
            >
              Exit Console
            </Link>
          </div>

          {/* Camera Feed */}
          <div className="relative w-full aspect-video bg-black/60 rounded-xl overflow-hidden border border-white/[0.08] flex items-center justify-center group">
            <video 
              ref={videoRef} 
              autoPlay 
              playsInline 
              muted 
              className={`w-full h-full object-cover transform -scale-x-100 ${!cameraActive && 'hidden'}`} 
            />
            {!cameraActive && (
              <div className="flex flex-col items-center gap-1.5 text-slate-500 font-mono text-[11px]">
                <span className="w-2 h-2 rounded-full bg-slate-600" />
                <span>CAMERA OFFLINE</span>
              </div>
            )}
            
            <button
              onClick={toggleCamera}
              className={`absolute top-2 right-2 text-[10px] font-mono px-2.5 py-1 rounded-md transition-all border shadow-sm ${
                cameraActive 
                  ? 'bg-rose-500/20 border-rose-500/40 text-rose-300 hover:bg-rose-500/30' 
                  : 'bg-teal-500/20 border-teal-500/40 text-teal-300 hover:bg-teal-500/30'
              }`}
            >
              {cameraActive ? '• DISABLE' : '+ ENABLE CAMERA'}
            </button>
          </div>

          {/* Live2D Frame */}
          <div className="flex-1 bg-black/30 border border-teal-500/20 rounded-xl overflow-hidden relative min-h-[280px]">
            <div className="absolute top-3 left-3 z-10 flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${isAvatarSpeaking ? 'bg-emerald-400 animate-ping' : 'bg-teal-400'}`} />
              <span className="text-[10px] font-mono font-medium text-slate-400 tracking-wider">
                {isAvatarSpeaking ? 'AUDIO OUTPUT ACTIVE' : 'AVATAR READY'}
              </span>
            </div>
            <Live2DAvatar isSpeaking={isAvatarSpeaking} />
          </div>

        </div>
      </div>

      {/* RIGHT COLUMN: Soothing Chat Workspace */}
      <div className="w-2/3 flex flex-col bg-[#111714]/80 border border-white/[0.08] rounded-2xl p-5 shadow-2xl backdrop-blur-xl justify-between">
        
        {/* Workspace Toolbar */}
        <div className="flex justify-between items-center pb-3 mb-4 border-b border-white/[0.08]">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-teal-400" />
            <span className="text-[11px] font-mono font-semibold text-slate-400 tracking-wider uppercase">Conversation Stream</span>
          </div>
          
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                const nextMute = !isMuted;
                setIsMuted(nextMute);
                if (nextMute) {
                  if ('speechSynthesis' in window) window.speechSynthesis.cancel();
                  setIsAvatarSpeaking(false);
                }
              }}
              className="text-[11px] font-mono px-3 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-slate-300 transition flex items-center gap-1.5"
            >
              {isMuted ? 'MUTE ON' : 'AUDIO ACTIVE'}
            </button>
            <button
              onClick={clearChat}
              className="text-[11px] font-mono px-3 py-1 rounded-lg bg-white/[0.04] hover:bg-rose-500/20 hover:border-rose-500/30 border border-white/[0.08] text-slate-400 hover:text-rose-300 transition"
            >
              RESET CHAT
            </button>
          </div>
        </div>

        {/* Chat Log Viewport with Relaxing Bubble Colors */}
        <div className="flex-1 overflow-y-auto space-y-4 pr-2 mb-4">
          {messages.map((msg, index) => (
            <div
              key={index}
              className={`p-4 rounded-xl max-w-[80%] text-xs leading-relaxed transition-all ${
                msg.sender === 'You'
                  ? 'bg-teal-700/80 text-white ml-auto border border-teal-400/30 shadow-lg shadow-teal-950/20'
                  : 'bg-[#18211C] text-slate-200 border border-white/[0.08] shadow-md shadow-black/30'
              }`}
            >
              <div className="text-[9px] font-mono font-bold opacity-60 mb-1 tracking-widest uppercase text-teal-200">
                {msg.sender}
              </div>
              
              <div className="prose prose-invert max-w-none text-xs">
                <ReactMarkdown
                  components={{
                    a: ({ node, ...props }) => (
                      <a
                        {...props}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-teal-300 underline font-medium hover:text-teal-200"
                      />
                    ),
                    ul: ({ node, ...props }) => <ul {...props} className="list-disc pl-4 space-y-1 my-1" />,
                    li: ({ node, ...props }) => <li {...props} className="text-xs" />
                  }}
                >
                  {msg.text}
                </ReactMarkdown>
              </div>
            </div>
          ))}

          {(isTranscribing || (loading && !isTranscribing)) && (
            <div className="flex justify-center my-3">
              <div className="inline-flex items-center gap-2 bg-[#18211C] border border-teal-500/30 text-teal-300 px-4 py-1.5 rounded-full text-[11px] font-mono animate-pulse shadow-lg">
                <span className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-ping" />
                {isTranscribing ? 'TRANSCRIBING STREAM...' : 'PROCESSING QUERY...'}
              </div>
            </div>
          )}
          
          <div ref={chatEndRef} />
        </div>

        {/* Command Dock Input */}
        <div className="flex gap-2 items-center bg-black/40 border border-white/[0.08] rounded-xl p-1.5 focus-within:border-teal-500/50 focus-within:ring-1 focus-within:ring-teal-500/30 transition-all duration-200">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                sendMessageToBackend(inputMessage, false);
              }
            }}
            placeholder={isListening ? "Recording voice input..." : "Type query or command..."}
            className="flex-1 bg-transparent px-3 py-1.5 text-xs focus:outline-none text-white placeholder-slate-500"
            disabled={isListening || isTranscribing}
          />

          <button
            onClick={toggleListening}
            title={isListening ? "Stop & Transcribe" : "Record Voice Query"}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono transition-all flex items-center gap-1 border ${
              isListening
                ? 'bg-rose-500/20 text-rose-300 border-rose-500/40 animate-pulse'
                : 'bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 border-white/[0.08]'
            }`}
          >
            {isListening ? '• RECORDING' : '🎙 VOICE'}
          </button>

          <button
            onClick={() => sendMessageToBackend(inputMessage, false)}
            disabled={isListening || isTranscribing}
            className="bg-teal-600 hover:bg-teal-500 disabled:opacity-40 px-4 py-1.5 rounded-lg text-xs font-medium transition-all shadow-md shadow-teal-950/50 text-white border border-teal-400/30"
          >
            Send
          </button>
        </div>

      </div>
    </main>
  );
}