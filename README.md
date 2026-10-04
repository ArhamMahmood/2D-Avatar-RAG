# 2D Avatar RAG: Interactive Live2D AI Resume Assistant

A full-stack, real-time AI assistant application combining interactive **Live2D avatars**, **Voice-to-Voice communication**, **Webcam vision stream**, and a local **Retrieval-Augmented Generation (RAG)** backend. 

The system allows users to interact naturally with an AI avatar through voice or text, fetching grounded context about professional experience, projects, and skills powered by local LLM orchestration.

---

## 🌟 Key Features

* **Interactive Live2D Avatar**: Real-time rendering of Cubism 4 models using Pixi.js, featuring dynamic lip-sync (`ParamMouthOpenY`) synchronized directly with Web Speech Synthesis audio output.
* **Voice-to-Voice Interface**:
  * **Speech-to-Text (STT)**: Client-side browser audio recording (`MediaRecorder`) sent to a FastAPI backend for real-time transcription.
  * **Text-to-Speech (TTS)**: Cleaned dynamic voice synthesis leveraging browser Web Speech API with real-time audio state detection.
* **RAG-Powered Conversations**: FastAPI backend integration querying document vector databases to deliver factual, grounded responses.
* **Webcam & Vision Stream**: Integrated client-side video feed toggle for future multi-modal vision enhancements.
* **Modern Developer Console UI**: Built with Next.js 16 (Turbopack), Tailwind CSS, dark glassmorphism aesthetic, and markdown message parsing (`react-markdown`).
* **Containerized Deployment**: Ready for multi-container Docker deployments (`avatar-rag:v1`).

---

## 🛠 Tech Stack

### Frontend
* **Framework**: Next.js 16.3.4 (App Router, Turbopack)
* **UI Library**: React 19, Tailwind CSS
* **2D Graphics & Animation**: Pixi.js v7, `pixi-live2d-display`
* **Markdown Rendering**: `react-markdown`
* **Audio & Speech**: HTML5 MediaRecorder API, Web Speech API (`SpeechSynthesis`)

### Backend
* **API Framework**: Python FastAPI, Uvicorn
* **AI Orchestration & RAG**: LangChain / LlamaIndex, PyTorch
* **Local Inference Engine**: Ollama (`llama3.2` / `qwen2.5`)
* **Audio Processing**: OpenAI Whisper / Speech-to-Text pipeline

---

## 📁 Repository Structure

```text
2D-Avatar-RAG/
├── frontend/
│   ├── public/
│   │   └── models/
│   │       └── kei/
│   │           └── kei_basic_free.model3.json   # Live2D Cubism 4 Model Assets
│   ├── src/
│   │   └── app/
│   │       ├── layout.tsx                      # Root layout loading Cubism SDKs
│   │       ├── page.tsx                        # Landing / Portfolio view
│   │       └── assistant/
│   │           └── page.tsx                    # Main Live2D AI Assistant Console
│   ├── package.json
│   └── next.config.ts
├── backend/
│   ├── main.py                                 # FastAPI server entry point
│   ├── rag_engine.py                           # Vector DB & retrieval pipeline
│   ├── stt_engine.py                          # Audio transcription service
│   ├── requirements.txt
│   └── data/                                   # RAG knowledge base documents
├── Dockerfile
└── README.md
