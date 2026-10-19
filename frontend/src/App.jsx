import { useEffect, useRef, useState } from "react";
import { BrowserRouter, Link, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { API_BASE_URL, useAuth } from "./auth.jsx";

const ASK_URL = `${API_BASE_URL}/ask`;
const EXAMPLE_QUESTIONS = [
  "What tests are needed for helmets?",
  "How do I apply for BIS certification for packaged drinking water?",
  "What is the sample size for electric kettle testing?",
  "What labelling is required on drinking water bottles?",
];
const FEATURES = [
  { icon: "01", title: "Find the right standard", text: "Get pointed to the BIS standard and product manual relevant to your product." },
  { icon: "02", title: "ClauseTrace verified answers", text: "See the source clause and a supporting quote with every verified point." },
  { icon: "03", title: "Certification guidance", text: "Understand the product manual steps and documents involved in certification." },
  { icon: "04", title: "Lab and test guidance", text: "Find sampling, testing and equipment requirements in the manuals." },
  { icon: "05", title: "Multilingual support", text: "Ask questions and read guidance in more languages.", comingSoon: true },
  { icon: "06", title: "Voice support", text: "Speak your question and listen to the guidance.", comingSoon: true },
];
const USER_TYPES = { msme: "MSME", manufacturer: "Manufacturer", consumer: "Consumer", student: "Student" };

function Brand({ light = false }) {
  return <span className={`brand ${light ? "brand-light" : ""}`}><span className="brand-dot" />BIS Nirdesh</span>;
}

function LandingPage() {
  const { user, logout } = useAuth();
  return (
    <div className="landing-page">
      <nav className="landing-nav">
        <Link className="brand-link" to="/"><Brand /></Link>
        <div className="nav-links"><a href="#features">Features</a><a href="#how-it-works">How it works</a></div>
        <div className="nav-actions">
          {user ? <><span className="nav-user-name">{user.name}</span><button className="button button-quiet" onClick={logout}>Logout</button></> : <><Link className="button button-quiet" to="/login">Login</Link><Link className="button button-quiet" to="/register">Register</Link></>}
          <Link className="button button-primary nav-start" to="/chat">Start chatting <span aria-hidden="true">&gt;</span></Link>
        </div>
      </nav>
      <main>
        <section className="hero-section">
          <div className="hero-copy">
            <span className="eyebrow"><span className="eyebrow-dot" />BIS standards, made clearer</span>
            <h1>Understand BIS standards and certification <span>in minutes</span></h1>
            <p>Find answers in BIS product manuals, with the source clause and quote beside every verified point.</p>
            <div className="hero-actions"><Link className="button button-primary button-large" to="/chat">Start chatting <span aria-hidden="true">&gt;</span></Link><a className="button button-outline button-large" href="#how-it-works">See how it works</a></div>
            <div className="hero-proof"><span className="proof-check">OK</span>Answers grounded in the BIS documents you provide</div>
          </div>
          <div className="hero-visual" aria-hidden="true">
            <div className="visual-orbit orbit-one" /><div className="visual-orbit orbit-two" />
            <div className="document-card">
              <div className="document-top"><span className="document-stamp">BIS</span><span className="document-dots">...</span></div>
              <div className="document-line short" /><div className="document-line" /><div className="document-line medium" />
              <div className="document-highlight"><span>Clause 5.2</span><div className="document-line" /><div className="document-line medium" /></div>
              <div className="document-line short" /><div className="document-line medium" />
              <div className="verified-float"><span>OK</span><div><strong>Source verified</strong><small>ClauseTrace evidence</small></div></div>
            </div>
            <div className="visual-caption"><span className="caption-mark">S</span><span><strong>Clear answers</strong><small>Backed by exact clauses</small></span></div>
          </div>
        </section>
        <section className="section-block features-section" id="features">
          <div className="section-intro"><span className="eyebrow">A better way to navigate standards</span><h2>Everything you need to move forward</h2><p>From finding a requirement to understanding the next certification step.</p></div>
          <div className="feature-grid">{FEATURES.map((feature) => <article className="feature-card" key={feature.title}><div className="feature-card-top"><span className="feature-icon">{feature.icon}</span>{feature.comingSoon && <span className="coming-soon">Coming soon</span>}</div><h3>{feature.title}</h3><p>{feature.text}</p></article>)}</div>
        </section>
        <section className="how-section" id="how-it-works">
          <div className="how-heading"><span className="eyebrow">How it works</span><h2>From question to a cited answer</h2><p>A simple process that keeps the source close to the guidance.</p></div>
          <div className="steps-grid"><article className="step-card"><span className="step-number">01</span><h3>Ask your question</h3><p>Describe the product, requirement or certification step you need help with.</p></article><article className="step-card"><span className="step-number">02</span><h3>We search the BIS documents</h3><p>Relevant product manuals are searched for supporting clauses and details.</p></article><article className="step-card"><span className="step-number">03</span><h3>Get a verified answer with the exact clause</h3><p>Review the answer beside its source, page and supporting quote.</p></article></div>
          <Link className="button button-primary how-cta" to="/chat">Ask your first question <span aria-hidden="true">&gt;</span></Link>
        </section>
      </main>
      <footer className="landing-footer"><Link className="brand-link" to="/"><Brand /></Link><p>This tool gives guidance based on BIS product manuals. It is not an official certification decision.</p><span>BIS Nirdesh</span></footer>
    </div>
  );
}

function EvidencePanel({ response }) {
  const points = response.points || [];
  return <details className="evidence-details"><summary><span>Evidence (ClauseTrace)</span><span className="evidence-count">{points.length} {points.length === 1 ? "point" : "points"}</span></summary><div className="evidence-list">{points.length ? points.map((point, index) => <article className="evidence-point" key={`${point.source}-${index}`}><div className="evidence-point-head"><p>{point.statement}</p><span className={`verification-badge ${point.verified ? "is-verified" : "is-unverified"}`}>{point.verified ? "Verified" : "Not verified"}</span></div><div className="evidence-meta"><strong>{point.is_number}</strong><span>Page {point.page}</span>{point.clause_ref && <span>{point.clause_ref}</span>}</div>{point.title && <p className="evidence-title">{point.title}</p>}{point.quote && <blockquote>{point.quote}</blockquote>}</article>) : <p className="no-points">No supporting statements were returned.</p>}</div></details>;
}

function AssistantMessage({ message }) {
  if (message.error) return <article className="assistant-message error-message"><div className="assistant-avatar">B</div><div className="assistant-card"><p>{message.error}</p></div></article>;
  const response = message.response;
  return <article className="assistant-message"><div className="assistant-avatar">B</div><div className={`assistant-card ${response.evidence_found ? "" : "assistant-no-evidence"}`}><div className="assistant-card-top"><span className="assistant-label">BIS Nirdesh</span>{response.evidence_found && <span className="verification-summary">Verified: {response.verification_summary}</span>}</div>{!response.evidence_found && <div className="no-evidence-banner">No verified evidence found</div>}<p className="assistant-answer">{response.answer}</p><EvidencePanel response={response} /></div></article>;
}

function ChatPage() {
  const { token, user } = useAuth();
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [language, setLanguage] = useState("English");
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const feedRef = useRef(null);
  const messageRefs = useRef({});
  const waitingRef = useRef(false);

  useEffect(() => { if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight; }, [messages, loading]);

  async function sendQuestion(value = draft) {
    const question = value.trim();
    if (!question || waitingRef.current) return;
    waitingRef.current = true;
    setDraft("");
    setLoading(true);
    setSidebarOpen(false);
    const userId = `message-${Date.now()}`;
    setMessages((current) => [...current, { id: userId, role: "user", content: question }]);
    try {
      const result = await fetch(ASK_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ question, language }),
      });
      const data = await result.json();
      if (!result.ok) throw new Error(data.detail || data.error || "Request failed");
      setMessages((current) => [...current, { id: `answer-${Date.now()}`, role: "assistant", response: data }]);
    } catch {
      setMessages((current) => [...current, { id: `error-${Date.now()}`, role: "assistant", error: "We couldn't connect to BIS Nirdesh. Please check that the backend is running and try again." }]);
    } finally {
      waitingRef.current = false;
      setLoading(false);
    }
  }

  function handleSubmit(event) { event.preventDefault(); sendQuestion(); }
  function handleInputKeyDown(event) { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); sendQuestion(); } }
  function startNewChat() { if (waitingRef.current) return; setMessages([]); setDraft(""); setSidebarOpen(false); }
  function scrollToMessage(id) { messageRefs.current[id]?.scrollIntoView({ behavior: "smooth", block: "center" }); setSidebarOpen(false); }
  const pastQuestions = messages.filter((message) => message.role === "user");

  return <div className="chat-app">
    {sidebarOpen && <button className="sidebar-scrim" aria-label="Close menu" onClick={() => setSidebarOpen(false)} />}
    <aside className={`chat-sidebar ${sidebarOpen ? "sidebar-open" : ""}`}>
      <Link className="sidebar-brand" to="/"><Brand light /></Link>
      <button className="new-chat-button" onClick={startNewChat}><span>+</span>New chat</button>
      <div className="history-label">THIS SESSION</div>
      <nav className="question-history" aria-label="This session's past questions">{pastQuestions.map((message) => <button key={message.id} title={message.content} onClick={() => scrollToMessage(message.id)}><span>&gt;</span>{message.content}</button>)}{!pastQuestions.length && <p className="history-empty">Your questions will appear here.</p>}</nav>
      <div className="sidebar-bottom"><label htmlFor="chat-language">Answer language</label><select id="chat-language" value={language} onChange={(event) => setLanguage(event.target.value)}><option>English</option><option>Hindi</option><option>Tamil</option></select><p>Answers grounded in BIS product manuals</p>{user && <div className="sidebar-user"><span className="sidebar-user-mark">{user.name.slice(0, 1).toUpperCase()}</span><span><strong>{user.name}</strong><small>{USER_TYPES[user.user_type] || user.user_type}</small></span></div>}</div>
    </aside>
    <section className="chat-main">
      <header className="chat-topbar"><button className="menu-button" aria-label="Open menu" onClick={() => setSidebarOpen(true)}><span /><span /><span /></button><div><strong>BIS Nirdesh</strong><span>Standards assistant</span></div><Link className="chat-home-link" to="/">Home</Link></header>
      <div className={`chat-feed ${messages.length ? "has-messages" : "empty-feed"}`} ref={feedRef}>
        {!messages.length ? <div className="welcome-content"><div className="welcome-mark"><span className="brand-dot" /></div><p className="eyebrow">Your BIS standards assistant</p><h1>What can I help you understand?</h1><p className="welcome-subtitle">Ask about a standard, product requirement or certification step. Every answer is checked against the available documents.</p><div className="welcome-examples">{EXAMPLE_QUESTIONS.map((example, index) => <button key={example} onClick={() => sendQuestion(example)}><span>0{index + 1}</span>{example}<b>&gt;</b></button>)}</div></div> : <div className="message-list">{messages.map((message) => message.role === "user" ? <article className="user-message" id={message.id} key={message.id} ref={(node) => { messageRefs.current[message.id] = node; }}><div className="user-bubble">{message.content}</div></article> : <AssistantMessage message={message} key={message.id} />)}{loading && <div className="assistant-message typing-message"><div className="assistant-avatar">B</div><div className="typing-card"><span /><span /><span /><em>Searching BIS documents...</em></div></div>}</div>}
      </div>
      <div className="chat-composer-area"><form className="chat-composer" onSubmit={handleSubmit}><label className="visually-hidden" htmlFor="chat-question">Ask a question</label><textarea id="chat-question" rows="1" value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={handleInputKeyDown} placeholder="Ask about BIS standards or certification..." /><button type="submit" disabled={!draft.trim() || loading} aria-label="Send question">Send</button></form><p className="composer-note">Enter to send - Shift + Enter for a new line</p></div>
    </section>
  </div>;
}

function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  async function submit(event) {
    event.preventDefault(); setError(""); setSubmitting(true);
    try { await login(email, password); navigate("/chat"); }
    catch (requestError) { setError(requestError.message); }
    finally { setSubmitting(false); }
  }
  return <main className="auth-page"><Link className="brand-link" to="/"><Brand /></Link><section className="auth-card"><div className="login-mark"><span className="brand-dot" /></div><p className="eyebrow">Welcome back</p><h1>Log in to BIS Nirdesh</h1><p className="auth-intro">Sign in to personalize your standards guidance.</p><form className="auth-form" onSubmit={submit}><label>Email address<input type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></label><label>Password<input type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} /></label>{error && <p className="auth-error" role="alert">{error}</p>}<button className="button button-primary auth-submit" disabled={submitting}>{submitting ? "Logging in..." : "Login"}</button></form><p className="auth-switch">New to BIS Nirdesh? <Link to="/register">Create an account</Link></p><Link className="guest-link" to="/chat">Continue as guest</Link></section></main>;
}

function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [details, setDetails] = useState({ name: "", email: "", password: "", user_type: "msme" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  function update(field, value) { setDetails((current) => ({ ...current, [field]: value })); }
  async function submit(event) {
    event.preventDefault(); setError(""); setSubmitting(true);
    try { await register(details); navigate("/chat"); }
    catch (requestError) { setError(requestError.message); }
    finally { setSubmitting(false); }
  }
  return <main className="auth-page"><Link className="brand-link" to="/"><Brand /></Link><section className="auth-card register-card"><div className="login-mark"><span className="brand-dot" /></div><p className="eyebrow">Get started</p><h1>Create your account</h1><p className="auth-intro">Tell us a little about yourself to tailor your guidance.</p><form className="auth-form" onSubmit={submit}><label>Name<input type="text" autoComplete="name" required maxLength="120" value={details.name} onChange={(event) => update("name", event.target.value)} /></label><label>Email address<input type="email" autoComplete="email" required value={details.email} onChange={(event) => update("email", event.target.value)} /></label><label>Password<input type="password" autoComplete="new-password" minLength="6" required value={details.password} onChange={(event) => update("password", event.target.value)} /><small>At least 6 characters</small></label><label>I am a<select value={details.user_type} onChange={(event) => update("user_type", event.target.value)}><option value="msme">MSME</option><option value="manufacturer">Manufacturer</option><option value="consumer">Consumer</option><option value="student">Student</option></select></label>{error && <p className="auth-error" role="alert">{error}</p>}<button className="button button-primary auth-submit" disabled={submitting}>{submitting ? "Creating account..." : "Register"}</button></form><p className="auth-switch">Already registered? <Link to="/login">Login</Link></p></section></main>;
}

function App() {
  return <BrowserRouter><Routes><Route path="/" element={<LandingPage />} /><Route path="/chat" element={<ChatPage />} /><Route path="/login" element={<LoginPage />} /><Route path="/register" element={<RegisterPage />} /><Route path="*" element={<Navigate to="/" replace />} /></Routes></BrowserRouter>;
}

export default App;
