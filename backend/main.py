import os
import re
import shutil
import tempfile
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import ollama
from pinecone import Pinecone

load_dotenv()

app = FastAPI(title="Sham Marianas AI Assistant Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("avatar-brain")

try:
    import whisper
    whisper_model = whisper.load_model("base.en")
except ImportError:
    whisper_model = None

class ChatRequest(BaseModel):
    message: str

FALLBACK_RESPONSE = "Sorry! At this moment I can only help you with information related to developer Arham Mahmood's resume."

@app.get("/")
def home():
    return {"status": "Sham Marianas backend is running successfully!"}

@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    if not whisper_model:
        raise HTTPException(status_code=500, detail="Whisper model is not installed on the server.")

    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
            shutil.copyfileobj(file.file, temp_audio)
            temp_file_path = temp_audio.name

        result = whisper_model.transcribe(
            temp_file_path,
            language="en",
            initial_prompt="Arham Mahmood, Sham Marianas, resume, AI engineer, contact, GitHub, LinkedIn."
        )
        return {"text": result.get("text", "").strip()}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio processing failed: {str(e)}")
    
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


@app.post("/chat")
def chat_with_avatar(request: ChatRequest):
    user_question = request.message.strip()
    lower_q = user_question.lower()

    # 1. Reject empty or single-token garbage queries (e.g., "Ram", "a", "??")
    # Extended whitelist to allow single-word conversational terms through
    clean_words = [w for w in re.findall(r'\b\w+\b', lower_q) if len(w) > 1]
    allowed_single_words = {"hi", "hii", "hiii", "hello", "hey", "arham", "bye", "cya", "thanks", "who"}
    
    if len(clean_words) == 0 or (len(clean_words) == 1 and clean_words[0] not in allowed_single_words):
        return {"reply": FALLBACK_RESPONSE}

    # 2. Exact Conversational Interceptors
    if re.search(r'\b(bye|goodbye|cya|see ya|take care)\b', lower_q):
        return {"reply": "Goodbye! Feel free to reach out anytime if you have more questions about Arham Mahmood's resume."}

    if re.search(r'\b(thanks|thank you|shukriya)\b', lower_q):
        return {"reply": "You're welcome! Let me know if you need any other details regarding Arham Mahmood's experience."}

    if lower_q in ["hi", "hii", "hiii", "hello", "hey", "kia hall hy", "kia hal hy", "kaise ho"]:
        return {"reply": "Hello! I am an AI assistant from Sham Marianas. How can I help you today with questions about developer Arham Mahmood's resume?"}

    if lower_q in ["who are you", "how can you help me", "what can you do"]:
        return {"reply": "I am an AI assistant representing developer Arham Mahmood. I can help answer questions about his skills, work history, projects, certifications, and contact information."}

    if any(q in lower_q for q in ["who is arham", "who is arham mahmood", "tell me about arham"]):
        return {"reply": "Arham Mahmood is an AI Engineer and BS Artificial Intelligence student from Pakistan with expertise in Computer Vision, NLP, and Generative AI."}

    if any(k in lower_q for k in ["github", "linkedin", "contact", "email", "link", "reach out", "get hub", "linked in"]):
        return {
            "reply": "You can reach Arham Mahmood using the following details:\n"
                     "* **Email**: [mah.arhamper@gmail.com](mailto:mah.arhamper@gmail.com)\n"
                     "* **GitHub**: [github.com/ArhamMahmood](https://github.com/ArhamMahmood)\n"
                     "* **LinkedIn**: [linkedin.com/in/arham-mahmood](https://www.linkedin.com/in/arham-mahmood-175b832a1)"
        }

    # 3. Deterministic Pattern Blockers
    OFF_TOPIC_PATTERNS = [
        r'\b(system prompt|system message|instructions|formatting rules|initial prompt|prompt instructions|guidelines)\b',
        r'\b(write|generate|create|provide|show|convert|format|transform)\b.*\b(script|code|python|function|class|essay|json|yaml|xml|table|dictionary|dict|hashmap|key-value|kv|struct)\b',
        r'\b(dictionary|key-value|hashmap)\b',
        r'\b(pretend|roleplay|act as|speak as|first person|i am arham|my name is arham|hiring manager|pitching|recruiter perspective)\b',
        r'\b(terminal|shell|bash|cmd|linux)\b'
    ]

    for pattern in OFF_TOPIC_PATTERNS:
        if re.search(pattern, lower_q):
            return {"reply": FALLBACK_RESPONSE}

    try:
        # 4. Intent Classification
        router_prompt = f"""Analyze the user query and classify it into target domains:
- experience (work history, jobs, internships)
- education (university, degrees, coursework, schools)
- projects (software builds, FYP, apps)
- skills (programming languages, frameworks, tools)
- certifications (certificates, courses, training)

Query: "{user_question}"
Output ONLY category word(s) as a comma-separated list. Output "general" if none fit."""

        intent_response = ollama.chat(
            model="qwen2.5:0.5b",
            messages=[{"role": "user", "content": router_prompt}],
            options={"temperature": 0.0}
        )
        raw_intent = intent_response["message"]["content"].strip().lower()

        valid_categories = {"experience", "education", "projects", "skills", "certifications"}
        detected_categories = [
            cat.strip() for cat in re.split(r'[,\s]+', raw_intent)
            if cat.strip() in valid_categories
        ]

        # 5. Local Embedding Generation
        query_response = ollama.embeddings(
            model="nomic-embed-text",
            prompt=user_question
        )
        query_vector = query_response["embedding"]

        # 6. Pinecone Vector Search
        search_kwargs = {
            "vector": query_vector,
            "top_k": 4 if len(detected_categories) <= 1 else 6,
            "include_metadata": True
        }

        if len(detected_categories) == 1:
            search_kwargs["filter"] = {"category": detected_categories[0]}
        elif len(detected_categories) > 1:
            search_kwargs["filter"] = {"category": {"$in": detected_categories}}

        search_results = index.query(**search_kwargs)

        # Fallback Query if category filter had low hits
        if not search_results.matches or search_results.matches[0].score < 0.38:
            if "filter" in search_kwargs:
                del search_kwargs["filter"]
                search_results = index.query(**search_kwargs)

        # Raised Threshold to 0.38 to reject fuzzy context matches
        if not search_results.matches or search_results.matches[0].score < 0.38:
            return {"reply": FALLBACK_RESPONSE}

        # 7. Extract Context
        context = ""
        for match in search_results.matches:
            if match.metadata and "text" in match.metadata:
                context += match.metadata["text"] + "\n---\n"

        # 8. HARD GROUNDING CHECK (Prevents CGPA & Missing Field Hallucinations)
        # If the user asks for GPA/CGPA but the term doesn't exist in retrieved context, fail immediately.
        if re.search(r'\b(cgpa|gpa|grade|marks|percentage|salary|phone|number)\b', lower_q):
            if not re.search(r'\b(cgpa|gpa|grade|marks|percentage|salary|phone)\b', context.lower()):
                return {"reply": FALLBACK_RESPONSE}

        # 9. Strict System Instructions
        system_instructions = f"""You are an AI assistant representing developer Arham Mahmood.

Retrieved Context:
{context}

CRITICAL CONSTRAINTS:
1. Refer to Arham Mahmood ONLY in third person ("Arham Mahmood is...", "His skills include...").
2. Answer using bullet points starting with '*'.
3. State ONLY facts explicitly written in the Retrieved Context. Do NOT guess, infer, or hallucinate missing details (such as CGPA, grades, or personal contact numbers unless stated in context).
4. If the retrieved context does not contain the answer, reply EXACTLY: "{FALLBACK_RESPONSE}"
"""

        response = ollama.chat(
            model="qwen2.5:1.5b",
            messages=[
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": user_question}
            ],
            options={
                "temperature": 0.0,    # 0.0 eliminates creative guessing
                "num_predict": 200
            }
        )
        
        reply_content = response["message"]["content"].strip()

        # 10. Post-Generation Output Sanity Checks
        if "```" in reply_content or re.search(r'\b(I am|my name|I have|my experience)\b', reply_content):
            return {"reply": FALLBACK_RESPONSE}

        # Enforce bullet formatting strictly on all non-empty lines
        lines = [line.strip() for line in reply_content.split('\n') if line.strip()]
        formatted_lines = []
        for line in lines:
            if not line.startswith('*') and not line.startswith('-'):
                formatted_lines.append(f"* {line}")
            else:
                formatted_lines.append(f"* {line.lstrip('*- ').strip()}")

        return {"reply": "\n".join(formatted_lines)}

    except Exception as e:
        print(f"RAG Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))