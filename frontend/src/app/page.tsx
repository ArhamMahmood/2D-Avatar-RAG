'use client';

import React from 'react';
import Link from 'next/link';
import InteractiveBackground from '@/components/InteractiveBackground';

export default function LandingPage() {
  return (
    <div className="min-h-screen text-slate-200 flex flex-col justify-between selection:bg-teal-500/30 selection:text-teal-200 relative overflow-hidden font-sans">
      
      {/* Interactive Dust & Watermark Canvas */}
      <InteractiveBackground />

      {/* Ambient Soft Glow Gradient */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[500px] bg-[radial-gradient(ellipse_at_top,rgba(20,184,166,0.12),transparent_70%)] pointer-events-none z-0" />

      {/* Header */}
      <header className="border-b border-white/[0.08] bg-[#0A0F0D]/70 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="font-semibold text-sm tracking-tight text-white/90">Project</span>
            <span className="text-[13px] font-mono font-medium px-2 py-0.5 rounded-full bg-white/[0.06] text-teal-300 border border-teal-500/20">
              DEMO
            </span>
          </div>

          <nav className="flex items-center gap-4">
            <Link 
              href="/assistant" 
              className="text-xs font-medium bg-teal-500 hover:bg-teal-400 text-slate-950 px-4 py-2 rounded-lg transition-all duration-200 shadow-md shadow-teal-500/20 font-sans"
            >
              Launch
            </Link>
          </nav>
        </div>
      </header>

      {/* Hero Content */}
      <main className="max-w-6xl mx-auto px-6 py-24 flex-1 flex flex-col justify-center relative z-10">
        <div className="max-w-3xl space-y-6">
          
          {/* Status Badge */}
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-teal-500/10 border border-teal-500/20 text-teal-300 text-xs font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-pulse" />
            <span>Project by Arham Mahmood</span>
          </div>
          
          {/* Headline */}
          <h1 className="text-4xl sm:text-6xl font-bold tracking-tight text-transparent bg-clip-text bg-gradient-to-b from-white via-slate-200 to-slate-400 leading-[1.1]">
            Real-Time AI Avatar & Context Engine
          </h1>
          
          <p className="text-slate-400 text-base sm:text-lg leading-relaxed max-w-2xl font-normal">
            Low-latency conversational platform integrating Live2D lip-sync animation, real-time voice synthesis, and document-grounded context retrieval.
          </p>

          {/* CTA */}
          <div className="pt-4 flex items-center gap-4">
            <Link 
              href="/assistant" 
              className="bg-teal-600 hover:bg-teal-500 text-white font-medium px-6 py-3 rounded-xl transition-all duration-200 shadow-lg shadow-teal-900/30 hover:shadow-teal-600/30 flex items-center gap-2 text-sm border border-teal-400/30"
            >
              Open Chat
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
              </svg>
            </Link>
          </div>
        </div>

        {/* Feature Cards Grid */}
        <div className="grid md:grid-cols-3 gap-5 mt-20">
          
          <div className="bg-slate-900/40 border border-white/[0.08] p-6 rounded-2xl backdrop-blur-xl hover:border-teal-500/30 transition-all duration-300 group">
            <div className="w-8 h-8 rounded-lg bg-teal-500/10 border border-teal-500/20 flex items-center justify-center text-teal-400 mb-4 font-mono text-xs group-hover:scale-105 transition-transform">
              1
            </div>
            <h3 className="font-semibold text-white text-sm mb-1.5">Context Grounding</h3>
            <p className="text-slate-400 text-xs leading-relaxed">
              Retrieval-Augmented Generation pipeline enforcing zero-hallucination document-backed responses.
            </p>
          </div>

          <div className="bg-slate-900/40 border border-white/[0.08] p-6 rounded-2xl backdrop-blur-xl hover:border-teal-500/30 transition-all duration-300 group">
            <div className="w-8 h-8 rounded-lg bg-teal-500/10 border border-teal-500/20 flex items-center justify-center text-teal-400 mb-4 font-mono text-xs group-hover:scale-105 transition-transform">
              2
            </div>
            <h3 className="font-semibold text-white text-sm mb-1.5">2D Avatar</h3>
            <p className="text-slate-400 text-xs leading-relaxed">
              Web Audio & SpeechSynthesis synchronization driving real-time parameter animation loops.
            </p>
          </div>

          <div className="bg-slate-900/40 border border-white/[0.08] p-6 rounded-2xl backdrop-blur-xl hover:border-teal-500/30 transition-all duration-300 group">
            <div className="w-8 h-8 rounded-lg bg-teal-500/10 border border-teal-500/20 flex items-center justify-center text-teal-400 mb-4 font-mono text-xs group-hover:scale-105 transition-transform">
              3
            </div>
            <h3 className="font-semibold text-white text-sm mb-1.5">Voice & Vision Stream</h3>
            <p className="text-slate-400 text-xs leading-relaxed">
              Instant backend Whisper transcription paired with live browser media-stream viewport monitoring.
            </p>
          </div>

        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-white/[0.08] py-6 text-center text-[11px] text-slate-500 font-mono relative z-10">
        <span>© 2026 RAG Project. ARHAM MAHMOOD</span>
      </footer>
    </div>
  );
}