import os,sqlite3,secrets,requests
from flask import Flask,request,jsonify,send_from_directory,session,Response
from werkzeug.security import generate_password_hash,check_password_hash
from dotenv import load_dotenv
load_dotenv()
BASE=os.path.dirname(os.path.abspath(__file__)); DB=os.path.join(BASE,"chatai.db")
app=Flask(__name__,static_folder="frontend",static_url_path="/")
app.secret_key=os.getenv("SECRET_KEY") or secrets.token_hex(32)
def db():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def init():
 c=db();c.executescript("""CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,email TEXT UNIQUE,password TEXT);
CREATE TABLE IF NOT EXISTS chats(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,title TEXT,updated_at DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT,chat_id INTEGER,role TEXT,content TEXT,created_at DATETIME DEFAULT CURRENT_TIMESTAMP);""");c.commit();c.close()
def uid(): return session.get("uid")
@app.get("/")
def home(): return send_from_directory("frontend","index.html")
@app.post("/api/signup")
def signup():
 d=request.json or {};n=d.get("name","").strip();e=d.get("email","").strip().lower();p=d.get("password","")
 if not n or not e or len(p)<6:return jsonify(error="Enter name, email and a 6+ character password"),400
 c=db()
 try:
  x=c.execute("INSERT INTO users(name,email,password) VALUES(?,?,?)",(n,e,generate_password_hash(p)));c.commit();session["uid"]=x.lastrowid;session["name"]=n
  return jsonify(user={"name":n,"email":e})
 except sqlite3.IntegrityError:return jsonify(error="Email already registered"),409
 finally:c.close()
@app.post("/api/login")
def login():
 d=request.json or {};e=d.get("email","").strip().lower();p=d.get("password","");c=db();u=c.execute("SELECT * FROM users WHERE email=?",(e,)).fetchone();c.close()
 if not u or not check_password_hash(u["password"],p):return jsonify(error="Invalid email or password"),401
 session["uid"]=u["id"];session["name"]=u["name"];return jsonify(user={"name":u["name"],"email":u["email"]})
@app.post("/api/logout")
def logout():session.clear();return jsonify(ok=True)
@app.get("/api/me")
def me():return jsonify(user={"name":session["name"]} if uid() else None)
@app.get("/api/chats")
def chats():
 if not uid():return jsonify(error="Login required"),401
 c=db();r=c.execute("SELECT id,title FROM chats WHERE user_id=? ORDER BY updated_at DESC",(uid(),)).fetchall();c.close();return jsonify([dict(x) for x in r])
@app.post("/api/chats")
def newchat():
 if not uid():return jsonify(error="Login required"),401
 t=(request.json or {}).get("title","New chat")[:80];c=db();x=c.execute("INSERT INTO chats(user_id,title) VALUES(?,?)",(uid(),t));c.commit();i=x.lastrowid;c.close();return jsonify(id=i,title=t)
@app.get("/api/chats/<int:i>")
def getchat(i):
 if not uid():return jsonify(error="Login required"),401
 c=db();ch=c.execute("SELECT * FROM chats WHERE id=? AND user_id=?",(i,uid())).fetchone()
 if not ch:c.close();return jsonify(error="Not found"),404
 m=c.execute("SELECT role,content FROM messages WHERE chat_id=? ORDER BY id",(i,)).fetchall();c.close();return jsonify(messages=[dict(x) for x in m])
def demo(q):
 ql=q.lower()
 if "dbms" in ql or "database" in ql:return """### DBMS in simple words
A **DBMS** stores, organizes and retrieves data.
```text
Students
Courses
Marks
Attendance
```
Examples: MySQL, PostgreSQL, Oracle and SQLite."""
 if "python" in ql:return """### Python example
```python
name = input("Enter your name: ")
print(f"Hello, {name}!")
```
This takes input and prints a greeting."""
 if "hello" in ql or "hi" in ql:return "Hey! 👋 I'm **ChatAI**. Ask me about coding, DBMS, projects, exams or anything you want to learn."
 return f"""I received:
> {q}

**ChatAI is working in DEMO mode.** No API key is required for this version. Connect an AI model later through the server `.env` settings for real model-generated answers."""
def system_messages(messages):
    return [{"role":"system","content":"You are ChatAI, the AI assistant inside the ChatAI application. Your name is ChatAI. Never claim that you are Claude, ChatGPT, Gemini, or another AI. If asked who you are, say you are ChatAI. Be helpful, friendly, accurate and concise."}]+messages

def real(messages, stream=False):
    url=os.getenv("AI_API_URL") or "http://localhost:11434/api/chat"
    model=os.getenv("AI_MODEL") or "qwen2.5:0.5b"
    payload={"model":model,"messages":system_messages(messages),"stream":stream}
    headers={"Content-Type":"application/json"}
    key=os.getenv("AI_API_KEY")
    if key: headers["Authorization"]="Bearer "+key
    r=requests.post(url,headers=headers,json=payload,stream=stream,timeout=120)
    r.raise_for_status()
    if not stream: return r.json()["message"]["content"]
    return r

@app.post("/api/chat")
def chat():
    if not uid(): return jsonify(error="Login required"),401
    d=request.json or {};q=(d.get("message") or "").strip();i=d.get("chat_id")
    if not q: return jsonify(error="Message required"),400
    c=db()
    if not i:
        x=c.execute("INSERT INTO chats(user_id,title) VALUES(?,?)",(uid(),q[:50]));i=x.lastrowid
    elif not c.execute("SELECT id FROM chats WHERE id=? AND user_id=?",(i,uid())).fetchone():
        c.close();return jsonify(error="Chat not found"),404
    c.execute("INSERT INTO messages(chat_id,role,content) VALUES(?,?,?)",(i,"user",q))
    h=c.execute("SELECT role,content FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT 20",(i,)).fetchall()
    msgs=[{"role":x["role"],"content":x["content"]} for x in reversed(h)]
    c.commit();c.close()
    def generate():
        answer="";mode="real"
        try:
            r=real(msgs,stream=True)
            for line in r.iter_lines():
                if not line: continue
                data=__import__("json").loads(line.decode("utf-8"))
                piece=data.get("message",{}).get("content","")
                if piece:
                    answer+=piece;yield piece
        except Exception as e:
            print("AI Error:",e);mode="demo";answer=demo(q)
            for pos in range(0,len(answer),8): yield answer[pos:pos+8]
        finally:
            save=db();save.execute("INSERT INTO messages(chat_id,role,content) VALUES(?,?,?)",(i,"assistant",answer));save.execute("UPDATE chats SET updated_at=CURRENT_TIMESTAMP WHERE id=?",(i,));save.commit();save.close()
    return Response(generate(),mimetype="text/plain",headers={"X-Chat-Id":str(i),"X-AI-Mode":"stream"})

@app.post("/api/regenerate")
def regenerate():
    if not uid(): return jsonify(error="Login required"),401
    i=(request.json or {}).get("chat_id");c=db()
    ch=c.execute("SELECT id FROM chats WHERE id=? AND user_id=?",(i,uid())).fetchone()
    if not ch: c.close();return jsonify(error="Chat not found"),404
    last=c.execute("SELECT * FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT 1",(i,)).fetchone()
    if not last or last["role"]!="assistant": c.close();return jsonify(error="Nothing to regenerate"),400
    c.execute("DELETE FROM messages WHERE id=?",(last["id"],))
    h=c.execute("SELECT role,content FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT 20",(i,)).fetchall();msgs=[{"role":x["role"],"content":x["content"]} for x in reversed(h)];c.commit();c.close()
    q=msgs[-1]["content"] if msgs else ""
    def generate():
        answer=""
        try:
            r=real(msgs,stream=True)
            for line in r.iter_lines():
                if not line: continue
                data=__import__("json").loads(line.decode());piece=data.get("message",{}).get("content","")
                if piece: answer+=piece;yield piece
        except Exception:
            answer=demo(q)
            for pos in range(0,len(answer),8): yield answer[pos:pos+8]
        finally:
            save=db();save.execute("INSERT INTO messages(chat_id,role,content) VALUES(?,?,?)",(i,"assistant",answer));save.execute("UPDATE chats SET updated_at=CURRENT_TIMESTAMP WHERE id=?",(i,));save.commit();save.close()
    return Response(generate(),mimetype="text/plain")

@app.delete("/api/chats/<int:i>")
def delete_chat(i):
    if not uid(): return jsonify(error="Login required"),401
    c=db();c.execute("DELETE FROM messages WHERE chat_id=?",(i,));c.execute("DELETE FROM chats WHERE id=? AND user_id=?",(i,uid()));c.commit();c.close();return jsonify(ok=True)

@app.patch("/api/chats/<int:i>")
def rename_chat(i):
    if not uid(): return jsonify(error="Login required"),401
    title=(request.json or {}).get("title","").strip()[:80]
    if not title:return jsonify(error="Title required"),400
    c=db();c.execute("UPDATE chats SET title=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",(title,i,uid()));c.commit();c.close();return jsonify(ok=True,title=title)

@app.post("/api/upload")
def upload():
    if not uid(): return jsonify(error="Login required"),401
    f=request.files.get("file")
    if not f:return jsonify(error="No file selected"),400
    name=f.filename or "file";ext=os.path.splitext(name)[1].lower()
    try:
        if ext==".pdf":
            from pypdf import PdfReader
            text="\n".join((p.extract_text() or "") for p in PdfReader(f).pages)
        else:
            text=f.read().decode("utf-8",errors="ignore")
        return jsonify(name=name,text=text[:50000])
    except Exception as e:return jsonify(error="Could not read this file: "+str(e)),400

if __name__=="__main__":init();app.run(port=5000,debug=True)
