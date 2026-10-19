# BIS Nirdesh
An AI assistant that helps people find and understand Indian (BIS) standards.

## Tech
- Backend: Python with FastAPI
- Database: PostgreSQL with pgvector
- AI: Google Gemini

## Rules
- Answers must come only from the BIS documents we give it.
- Every answer must show its source: IS number, clause number, and version.
- If no evidence is found, say so. Never guess.
- Keep the API key in a .env file, never in the code.
- Do one small task at a time, and tell me how to run and test it.
