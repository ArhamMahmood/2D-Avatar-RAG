import os
from dotenv import load_dotenv
import ollama
from pinecone import Pinecone
from google import genai
from google.genai import types

load_dotenv()

# Initialize Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("avatar-brain")

# Initialize Gemini Client (automatically loads GEMINI_API_KEY from .env)
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def ask_avatar(user_question):
    user_question = user_question.strip()
    lower_q = user_question.lower()

    # 1. Fast Python-level conversational interceptor
    if lower_q in ["bye", "goodbye", "see ya", "cya"]:
        answer = "Goodbye! Feel free to reach out anytime if you have more questions about Arham Mahmood's resume."
        print(f"\nAssistant says: {answer}")
        return answer

    if lower_q in ["thank you", "thanks", "okay thank you", "thank you!"]:
        answer = "You're welcome! Let me know if you need any other details regarding Arham Mahmood's experience."
        print(f"\nAssistant says: {answer}")
        return answer

    if lower_q in ["hi", "hello", "hey", "who are you", "who are you?"]:
        answer = "Hello! I am an AI assistant from Sham Marianas. How can I help you today with questions about developer Arham Mahmood's resume?"
        print(f"\nAssistant says: {answer}")
        return answer

    FALLBACK_RESPONSE = "Sorry! At this moment I can only help you with information related to my developer Arham Mahmood's resume."

    print(f"\nUser asked: {user_question}")
    print("Searching vector memory and generating response with Gemini...")

    # 2. Embed user question locally (matching Pinecone vector space)
    query_response = ollama.embeddings(
        model="nomic-embed-text",
        prompt=user_question
    )
    query_vector = query_response["embedding"]

    # 3. Search Pinecone vector database
    search_results = index.query(
        vector=query_vector,
        top_k=3,
        include_metadata=True
    )

    # 4. Vector Score Thresholding
    if not search_results.matches or search_results.matches[0].score < 0.55:
        print(f"\nAssistant says: {FALLBACK_RESPONSE}")
        return FALLBACK_RESPONSE

    # 5. Extract context text safely
    context = ""
    for match in search_results.matches:
        if match.metadata and "text" in match.metadata:
            context += match.metadata["text"] + "\n---\n"

    # 6. Formulate system prompt instruction
    system_instruction = f"""You are an AI assistant from Sham Marianas representing developer Arham Mahmood.

Retrieved Context:
{context}

STRICT OUTPUT RULES:
1. Speak in plain conversational sentences only. Never use markdown headings (###), bullet points, or lists.
2. Always refer to Arham Mahmood in the third person ("Arham Mahmood is...", "His skills are..."). Never pretend to be Arham.
3. Answer strictly using the context above in 2 to 3 sentences maximum.
4. If the retrieved context does not directly answer the user's question, reply EXACTLY with:
"{FALLBACK_RESPONSE}"
"""

    # 7. Generate response via Google Gemini API
    try:
        response = gemini_client.models.generate_content(
            model="gemini-3.6-flash",
            contents=user_question,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3
            )
        )
        reply = response.text.strip()
    except Exception as e:
        print(f"Gemini API Error: {e}")
        reply = FALLBACK_RESPONSE

    print(f"\nAssistant says: {reply}")
    return reply

if __name__ == "__main__":
    # Quick terminal tests
    ask_avatar("who are you?")
    ask_avatar("What is Arham's experience in Computer Vision?")
    ask_avatar("Can I rent a cloud server here?")