import React, { useState, useEffect } from 'react';
import { render } from 'react-dom';
import axios from 'axios';
import Quill from 'quill';
import 'quill/dist/quill.snow.css';
import './index.css';

const App = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [faqs, setFaqs] = useState([]);
  const [newQuestion, setNewQuestion] = useState('');
  const [newAnswer, setNewAnswer] = useState('');
  const [botName, setBotName] = useState('');
  const [logoUrl, setLogoUrl] = useState('');
  const [responseTemplate, setResponseTemplate] = useState('[Answer]');
  const [analytics, setAnalytics] = useState(null);
  const [quill, setQuill] = useState(null);

  useEffect(() => {
    const quillEditor = new Quill('#editor', {
      theme: 'snow',
      modules: { toolbar: [['bold', 'italic'], ['emoji'], [{ 'color': [] }]] }
    });
    setQuill(quillEditor);
    quillEditor.on('text-change', () => {
      setResponseTemplate(quillEditor.root.innerHTML);
    });
    return () => quillEditor.disable();
  }, []);

  const login = async () => {
    try {
      const response = await axios.get('/api/faqs', {
        auth: { username, password }
      });
      setFaqs(response.data);
      setIsAuthenticated(true);
    } catch (error) {
      alert('Неверные учетные данные');
    }
  };

  const addFAQ = async () => {
    await axios.post('/api/faqs', { question: newQuestion, answer: newAnswer }, {
      auth: { username, password }
    });
    setFaqs([...faqs, { question: newQuestion, answer: newAnswer }]);
    setNewQuestion('');
    setNewAnswer('');
  };

  const deleteFAQ = async (question) => {
    await axios.delete(`/api/faqs/${encodeURIComponent(question)}`, {
      auth: { username, password }
    });
    setFaqs(faqs.filter(faq => faq.question !== question));
  };

  const getAnalytics = async () => {
    const response = await axios.get('/api/analytics', {
      auth: { username, password }
    });
    setAnalytics(response.data);
  };

  const uploadLogo = async (event) => {
    const file = event.target.files[0];
    const formData = new FormData();
    formData.append('logo', file);
    const response = await axios.post('/api/upload_logo', formData, {
      auth: { username, password }
    });
    setLogoUrl(response.data.logo_url);
  };

  const saveBranding = async () => {
    await axios.post('/api/branding', {
      bot_name: botName,
      logo_url: logoUrl,
      response_template: responseTemplate
    }, {
      auth: { username, password }
    });
    alert('Брендинг сохранен');
  };

  if (!isAuthenticated) {
    return (
      <div className="container mx-auto p-4">
        <h1 className="text-2xl font-bold mb-4">Вход</h1>
        <input
          type="text"
          placeholder="Имя пользователя"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="border p-2 m-2"
        />
        <input
          type="password"
          placeholder="Пароль"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="border p-2 m-2"
        />
        <button onClick={login} className="bg-blue-500 text-white p-2 rounded">Войти</button>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">{botName} Настройки</h1>
      
      <div className="mb-4">
        <h2 className="text-xl">FAQ</h2>
        <input
          type="text"
          placeholder="Вопрос"
          value={newQuestion}
          onChange={(e) => setNewQuestion(e.target.value)}
          className="border p-2 m-2"
        />
        <input
          type="text"
          placeholder="Ответ"
          value={newAnswer}
          onChange={(e) => setNewAnswer(e.target.value)}
          className="border p-2 m-2"
        />
        <button onClick={addFAQ} className="bg-blue-500 text-white p-2 rounded">Добавить FAQ</button>
        <ul>
          {faqs.map(faq => (
            <li key={faq.question}>
              {faq.question}: {faq.answer}
              <button onClick={() => deleteFAQ(faq.question)} className="text-red-500 ml-2">Удалить</button>
            </li>
          ))}
        </ul>
      </div>
      
      <div className="mb-4">
        <h2 className="text-xl">Брендинг</h2>
        <input
          type="text"
          placeholder="Название бота"
          value={botName}
          onChange={(e) => setBotName(e.target.value)}
          className="border p-2 m-2"
        />
        <input
          type="file"
          onChange={uploadLogo}
          className="border p-2 m-2"
        />
        <div id="editor" className="border p-2 m-2" style={{ height: '200px' }}></div>
        <button onClick={saveBranding} className="bg-blue-500 text-white p-2 rounded">Сохранить</button>
      </div>
      
      <div className="mb-4">
        <h2 className="text-xl">Аналитика</h2>
        <button onClick={getAnalytics} className="bg-blue-500 text-white p-2 rounded">Получить аналитику</button>
        {analytics && (
          <div>
            <p>Всего сообщений: {analytics.total_messages}</p>
            <p>Неотвеченные вопросы: {analytics.unanswered_queries}</p>
            <h3>Топ-5 вопросов:</h3>
            <ul>
              {analytics.top_questions.map(q => (
                <li key={q.question}>{q.question}: {q.count}</li>
              ))}
            </ul>
            <a href="/api/analytics/csv" className="bg-blue-500 text-white p-2 rounded">Скачать CSV</a>
          </div>
        )}
      </div>
    </div>
  );
};

render(<App />, document.getElementById('root'));