from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
import asyncpg
from datetime import datetime
import os
from dotenv import load_dotenv
import uuid

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

app = FastAPI()
security = HTTPBasic()

async def get_db():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        await conn.close()

class FAQ(BaseModel):
    question: str
    answer: str

class Business(BaseModel):
    bot_token: str
    owner_chat_id: str
    bot_name: str
    logo_url: str | None
    response_template: str

async def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    async with asyncpg.connect(DATABASE_URL) as conn:
        user = await conn.fetchrow(
            'SELECT business_id FROM Businesses WHERE username = $1 AND password = $2',
            credentials.username, credentials.password
        )
        if not user:
            raise HTTPException(status_code=401, detail='Invalid credentials')
        return user['business_id']

@app.post('/businesses')
async def create_business(business: Business):
    async with asyncpg.connect(DATABASE_URL) as conn:
        business_id = str(uuid.uuid4())
        await conn.execute(
            'INSERT INTO Businesses (business_id, bot_token, owner_chat_id, bot_name, logo_url, response_template, username, password) '
            'VALUES ($1, $2, $3, $4, $5, $6, $7, $8)',
            business_id, business.bot_token, business.owner_chat_id, business.bot_name,
            business.logo_url, business.response_template, business_id, str(uuid.uuid4())
        )
        return {'business_id': business_id, 'username': business_id, 'password': str(uuid.uuid4())}

@app.get('/faqs')
async def get_faqs(business_id: str = Depends(authenticate)):
    async with asyncpg.connect(DATABASE_URL) as conn:
        faqs = await conn.fetch('SELECT question, answer FROM FAQs WHERE business_id = $1', business_id)
        return [{'question': faq['question'], 'answer': faq['answer']} for faq in faqs]

@app.post('/faqs')
async def add_faq(faq: FAQ, business_id: str = Depends(authenticate)):
    async with asyncpg.connect(DATABASE_URL) as conn:
        await conn.execute(
            'INSERT INTO FAQs (business_id, question, answer) VALUES ($1, $2, $3)',
            business_id, faq.question, faq.answer
        )
        return {'message': 'FAQ added'}

@app.delete('/faqs/{question}')
async def delete_faq(question: str, business_id: str = Depends(authenticate)):
    async with asyncpg.connect(DATABASE_URL) as conn:
        await conn.execute('DELETE FROM FAQs WHERE business_id = $1 AND question = $2', business_id, question)
        return {'message': 'FAQ deleted'}

@app.get('/analytics')
async def get_analytics(business_id: str = Depends(authenticate)):
    async with asyncpg.connect(DATABASE_URL) as conn:
        top_questions = await conn.fetch(
            'SELECT message_text, COUNT(*) as count FROM Messages WHERE business_id = $1 AND is_answered = TRUE '
            'GROUP BY message_text ORDER BY count DESC LIMIT 5',
            business_id
        )
        total_messages = await conn.fetchval(
            'SELECT COUNT(*) FROM Messages WHERE business_id = $1', business_id
        )
        unanswered = await conn.fetchval(
            'SELECT COUNT(*) FROM Messages WHERE business_id = $1 AND is_answered = FALSE', business_id
        )
        return {
            'top_questions': [{'question': q['message_text'], 'count': q['count']} for q in top_questions],
            'total_messages': total_messages,
            'unanswered_queries': unanswered
        }