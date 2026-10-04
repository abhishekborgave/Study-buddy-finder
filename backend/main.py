from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime, text, inspect
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool
from datetime import datetime, timedelta
from pathlib import Path
import os, json, random, hashlib, secrets

DB=os.getenv('DATABASE_URL',f"sqlite:///{Path(__file__).with_name('study_buddy.db').as_posix()}")
# SQLite is used for the local demo. NullPool avoids keeping connections open
# across the short-lived FastAPI request threads.
engine=create_engine(DB, connect_args={'check_same_thread':False} if DB.startswith('sqlite') else {}, poolclass=NullPool if DB.startswith('sqlite') else None)
Session=sessionmaker(bind=engine); Base=declarative_base()
class User(Base):
 __tablename__='users'
 id=Column(Integer,primary_key=True); name=Column(String); email=Column(String,unique=True); password=Column(String); college=Column(String,default=''); course=Column(String,default=''); year=Column(Integer,default=2); age=Column(Integer,nullable=True); location=Column(String,default=''); discord_handle=Column(String,default=''); avatar=Column(String,default='📚'); photo=Column(Text,default=''); subjects=Column(Text,default='[]'); topics=Column(Text,default='[]'); goals=Column(Text,default='[]'); styles=Column(Text,default='[]'); levels=Column(Text,default='{}'); availability=Column(Text,default='[]'); duration=Column(Integer,default=90); group_size=Column(Integer,default=4)
class Connection(Base):
 __tablename__='connections'
 id=Column(Integer,primary_key=True); sender_id=Column(Integer); recipient_id=Column(Integer); status=Column(String,default='pending'); created_at=Column(DateTime,default=datetime.utcnow)
class Group(Base):
 __tablename__='groups'
 id=Column(Integer,primary_key=True); name=Column(String); description=Column(Text); subject=Column(String); goal=Column(String); max_members=Column(Integer); privacy=Column(String); owner_id=Column(Integer); members=Column(Text,default='[]')
class Task(Base):
 __tablename__='tasks'
 id=Column(Integer,primary_key=True); group_id=Column(Integer); title=Column(String); subject=Column(String,default='General'); priority=Column(String,default='Medium'); status=Column(String,default='To Do'); deadline=Column(String,default='')
class StudySession(Base):
 __tablename__='sessions'
 id=Column(Integer,primary_key=True); group_id=Column(Integer); title=Column(String); subject=Column(String,default='General'); topic=Column(String); starts_at=Column(String); ends_at=Column(String,default=''); mode=Column(String,default='Online'); location=Column(String,default=''); platform=Column(String,default=''); link=Column(String,default=''); attendees=Column(Text,default='[]')
class Notification(Base):
 __tablename__='notifications'
 id=Column(Integer,primary_key=True); user_id=Column(Integer); type=Column(String); content=Column(String); read=Column(Integer,default=0); created_at=Column(DateTime,default=datetime.utcnow)
Base.metadata.create_all(engine)
if DB.startswith('sqlite'):
 with engine.begin() as conn:
  existing={c['name'] for c in inspect(conn).get_columns('users')}
  for name, definition in [('age','INTEGER'),('location',"VARCHAR DEFAULT ''"),('photo',"TEXT DEFAULT ''"),('discord_handle',"VARCHAR DEFAULT ''")]:
   if name not in existing: conn.execute(text(f'ALTER TABLE users ADD COLUMN {name} {definition}'))
  task_columns={c['name'] for c in inspect(conn).get_columns('tasks')}
  if 'subject' not in task_columns: conn.execute(text("ALTER TABLE tasks ADD COLUMN subject VARCHAR DEFAULT 'General'"))
  session_columns={c['name'] for c in inspect(conn).get_columns('sessions')}
  for name, definition in [('subject',"VARCHAR DEFAULT 'General'"),('ends_at',"VARCHAR DEFAULT ''"),('mode',"VARCHAR DEFAULT 'Online'"),('location',"VARCHAR DEFAULT ''"),('platform',"VARCHAR DEFAULT ''"),('attendees',"TEXT DEFAULT '[]'")]:
   if name not in session_columns: conn.execute(text(f'ALTER TABLE sessions ADD COLUMN {name} {definition}'))
app=FastAPI(title='Study Buddy Finder API'); app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:3000'],allow_methods=['*'],allow_headers=['*'])
def arr(x): return json.loads(x or '[]')
def profile(u):
 return {'id':u.id,'name':u.name,'email':u.email,'college':u.college,'course':u.course,'year':u.year,'age':u.age,'location':u.location,'discordHandle':u.discord_handle,'avatar':u.avatar,'photo':u.photo,'subjects':arr(u.subjects),'topics':arr(u.topics),'goals':arr(u.goals),'styles':arr(u.styles),'levels':json.loads(u.levels or '{}'),'availability':arr(u.availability),'duration':u.duration,'groupSize':u.group_size}
def score(a,b):
 def overlap(x,y): return 100*len(set(x)&set(y))/max(1,len(set(x)|set(y)))
 av=overlap(a['availability'],b['availability']); parts={'Subjects':overlap(a['subjects'],b['subjects']),'Topics':overlap(a['topics'],b['topics']),'Goals':overlap(a['goals'],b['goals']),'Availability':av,'Study style':overlap(a['styles'],b['styles']),'Skill level':70 if set(a['subjects'])&set(b['subjects']) else 40}
 weights=[.25,.15,.20,.20,.10,.10]; total=round(sum(v*w for v,w in zip(parts.values(),weights)))
 return total, {k:round(v) for k,v in parts.items()}
class Auth(BaseModel): name:str=''; email:str; password:str
class ProfileIn(BaseModel):
 name:str; college:str=''; course:str=''; year:int=2; age:int|None=None; location:str=''; discordHandle:str=''; avatar:str='📚'; photo:str=''; subjects:list[str]=[]; topics:list[str]=[]; goals:list[str]=[]; styles:list[str]=[]; levels:dict={}; availability:list[str]=[]; duration:int=90; groupSize:int=4
 @field_validator('age')
 @classmethod
 def valid_age(cls,v):
  if v is not None and not 13 <= v <= 100: raise ValueError('Age must be between 13 and 100')
  return v
 @field_validator('photo')
 @classmethod
 def valid_photo(cls,v):
  if len(v)>1_400_000: raise ValueError('Profile image is too large (maximum 1 MB)')
  if v and not (v.startswith('data:image/jpeg;base64,') or v.startswith('data:image/png;base64,') or v.startswith('data:image/webp;base64,')): raise ValueError('Only JPEG, PNG, and WebP images are accepted')
  return v
class GroupIn(BaseModel): name:str; description:str=''; subject:str; goal:str; max_members:int=6; privacy:str='Public'; owner_id:int
class TaskIn(BaseModel): group_id:int; title:str; subject:str='General'; priority:str='Medium'; deadline:str=''
class TaskUpdate(BaseModel): title:str|None=None; subject:str|None=None; priority:str|None=None; deadline:str|None=None; status:str|None=None
class SessionIn(BaseModel): group_id:int; title:str; subject:str='General'; topic:str; starts_at:str; ends_at:str=''; mode:str='Online'; location:str=''; platform:str=''; link:str=''
class SessionUpdate(BaseModel): title:str|None=None; subject:str|None=None; topic:str|None=None; starts_at:str|None=None; ends_at:str|None=None; mode:str|None=None; location:str|None=None; platform:str|None=None; link:str|None=None
@app.get('/health')
def health(): return {'ok':True}
def hash_password(password:str):
 salt=secrets.token_bytes(16); return 'scrypt$'+salt.hex()+'$'+hashlib.scrypt(password.encode(),salt=salt,n=2**14,r=8,p=1).hex()
def password_matches(password:str,stored:str):
 if not stored.startswith('scrypt$'): return secrets.compare_digest(password,stored)
 _,salt,digest=stored.split('$'); return secrets.compare_digest(hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=2**14,r=8,p=1).hex(),digest)
@app.post('/auth/register')
def register(x:Auth):
 s=Session()
 if s.query(User).filter_by(email=x.email).first(): raise HTTPException(400,'Email already registered')
 u=User(name=x.name or x.email.split('@')[0],email=x.email,password=hash_password(x.password)); s.add(u);s.commit(); return profile(u)
@app.post('/auth/login')
def login(x:Auth):
 s=Session();u=s.query(User).filter_by(email=x.email).first()
 if not u or not password_matches(x.password,u.password): raise HTTPException(401,'Invalid email or password')
 if not u.password.startswith('scrypt$'): u.password=hash_password(x.password);s.commit()
 return profile(u)
@app.put('/users/{uid}')
def update(uid:int,x:ProfileIn):
 s=Session();u=s.get(User,uid)
 if not u: raise HTTPException(404,'User not found')
 for k,v in x.model_dump().items(): setattr(u,{'groupSize':'group_size','discordHandle':'discord_handle'}.get(k,k),json.dumps(v) if isinstance(v,(list,dict)) else v)
 s.commit();return profile(u)
@app.get('/matches/{uid}')
def matches(uid:int):
 s=Session(); me=s.get(User,uid)
 if not me: raise HTTPException(404,'User not found')
 a=profile(me); out=[]; unavailable={uid}
 for c in s.query(Connection).filter((Connection.sender_id==uid)|(Connection.recipient_id==uid)).all():
  unavailable.add(c.recipient_id if c.sender_id==uid else c.sender_id)
 for g in s.query(Group).all():
  m_list=[int(m) for m in arr(g.members) if str(m).isdigit()]
  if uid in m_list:
   for m in m_list: unavailable.add(m)
 for u in s.query(User).filter(User.id!=uid):
  if u.id in unavailable: continue
  b=profile(u); total,breakdown=score(a,b)
  out.append({**b,'compatibility':total,'breakdown':breakdown,'commonSubjects':list(set(a['subjects'])&set(b['subjects'])),'commonTopics':list(set(a['topics'])&set(b['topics'])),'reasons':[f"{len(set(a['subjects'])&set(b['subjects']))} shared subjects",f"{len(set(a['goals'])&set(b['goals']))} shared goals",f"{len(set(a['availability'])&set(b['availability']))} overlapping study slots"]})
 return sorted(out,key=lambda x:x['compatibility'],reverse=True)
@app.post('/connections')
def connect(sender_id:int,recipient_id:int):
 s=Session()
 existing=s.query(Connection).filter(((Connection.sender_id==sender_id)&(Connection.recipient_id==recipient_id))|((Connection.sender_id==recipient_id)&(Connection.recipient_id==sender_id))).first()
 if existing: return {'id':existing.id,'status':existing.status}
 c=Connection(sender_id=sender_id,recipient_id=recipient_id);s.add(c); sender=s.get(User,sender_id);s.add(Notification(user_id=recipient_id,type='connection',content=f'{sender.name} sent you a connection request.'));s.commit();return {'id':c.id,'status':'pending'}
@app.get('/connections/{uid}')
def connections(uid:int):
 s=Session(); cs=s.query(Connection).filter((Connection.sender_id==uid)|(Connection.recipient_id==uid)).all(); return [{'id':c.id,'status':c.status,'direction':'incoming' if c.recipient_id==uid else 'sent','person':profile(s.get(User,c.sender_id if c.recipient_id==uid else c.recipient_id))} for c in cs]
@app.post('/connections/{cid}/{action}')
def connection_action(cid:int,action:str):
 s=Session();c=s.get(Connection,cid)
 if not c: raise HTTPException(404,'Connection not found')
 c.status='accepted' if action=='accept' else 'declined'
 if action=='accept':
  sender=s.get(User,c.sender_id); recipient=s.get(User,c.recipient_id);s.add(Notification(user_id=c.sender_id,type='connection',content=f'{recipient.name} accepted your connection request.'))
  existing=[g for g in s.query(Group).all() if set(arr(g.members))=={c.sender_id,c.recipient_id}]
  if not existing:
   shared=list(set(arr(sender.subjects))&set(arr(recipient.subjects))); group=Group(name=f'{sender.name.split()[0]} & {recipient.name.split()[0]} Study Duo',description='Automatically created after your connection was accepted.',subject=shared[0] if shared else 'General Study',goal='General Learning',max_members=2,privacy='Invite Only',owner_id=c.sender_id,members=json.dumps([c.sender_id,c.recipient_id]));s.add(group)
 s.commit();return {'status':c.status}
@app.delete('/connections/{cid}')
def unfriend(cid:int,user_id:int):
 s=Session(); c=s.get(Connection,cid)
 if not c or user_id not in (c.sender_id,c.recipient_id): raise HTTPException(404,'Connection not found')
 s.delete(c);s.commit();return {'ok':True}
@app.get('/groups/{uid}')
def groups(uid:int): return [dict(id=g.id,name=g.name,description=g.description,subject=g.subject,goal=g.goal,maxMembers=g.max_members,privacy=g.privacy,members=arr(g.members)) for g in Session().query(Group).all() if uid in [int(m) for m in arr(g.members) if str(m).isdigit()]]
@app.post('/groups')
def create_group(x:GroupIn):
 s=Session();g=Group(name=x.name,description=x.description,subject=x.subject,goal=x.goal,max_members=x.max_members,privacy=x.privacy,owner_id=x.owner_id,members=json.dumps([x.owner_id]));s.add(g);s.commit();return {'id':g.id}
@app.post('/groups/{gid}/members')
def add_group_member(gid:int,user_id:int):
 s=Session();g=s.get(Group,gid); user=s.get(User,user_id)
 if not g or not user: raise HTTPException(404,'Group or user not found')
 members=arr(g.members)
 if user_id in members or str(user_id) in [str(m) for m in members]: return {'members':members}
 if len(members)>=g.max_members: raise HTTPException(400,'This group is full')
 members.append(user_id);g.members=json.dumps(members);s.add(Notification(user_id=user_id,type='group',content=f'You were added to {g.name}.'));s.commit();return {'members':members}
@app.get('/groups/{gid}/workspace')
def workspace(gid:int):
 s=Session(); return {'tasks':[{'id':t.id,'title':t.title,'subject':t.subject,'priority':t.priority,'status':t.status,'deadline':t.deadline} for t in s.query(Task).filter_by(group_id=gid)],'sessions':[{'id':x.id,'title':x.title,'subject':x.subject,'topic':x.topic,'startsAt':x.starts_at,'endsAt':x.ends_at,'mode':x.mode,'location':x.location,'platform':x.platform,'link':x.link,'attendees':arr(x.attendees)} for x in s.query(StudySession).filter_by(group_id=gid)]}
@app.post('/tasks')
def create_task(x:TaskIn): s=Session();t=Task(**x.model_dump());s.add(t);s.commit();return {'id':t.id}
@app.patch('/tasks/{tid}')
def update_task(tid:int,x:TaskUpdate|None=None,status:str|None=None):
 s=Session(); t=s.get(Task,tid)
 if not t: raise HTTPException(404,'Task not found')
 changes=x.model_dump(exclude_none=True) if x else {}
 if status: changes['status']=status
 for key,value in changes.items(): setattr(t,key,value)
 s.commit();return {'id':t.id,'status':t.status}
@app.delete('/tasks/{tid}')
def delete_task(tid:int):
 s=Session(); t=s.get(Task,tid)
 if not t: raise HTTPException(404,'Task not found')
 s.delete(t);s.commit();return {'ok':True}
@app.post('/sessions')
def create_session(x:SessionIn):
 try: start=datetime.fromisoformat(x.starts_at); end=datetime.fromisoformat(x.ends_at)
 except ValueError: raise HTTPException(422,'Use valid start and end times')
 if start < datetime.now() - timedelta(minutes=2): raise HTTPException(422,'Session start time cannot be in the past')
 if end <= start: raise HTTPException(422,'Session end time must be after start time')
 s=Session();z=StudySession(**x.model_dump());s.add(z);s.commit();return {'id':z.id}
@app.patch('/sessions/{sid}')
def update_session(sid:int,x:SessionUpdate):
 s=Session(); z=s.get(StudySession,sid)
 if not z: raise HTTPException(404,'Session not found')
 values=x.model_dump(exclude_none=True); start=values.get('starts_at',z.starts_at); end=values.get('ends_at',z.ends_at)
 try: start_dt=datetime.fromisoformat(start); end_dt=datetime.fromisoformat(end)
 except ValueError: raise HTTPException(422,'Use valid start and end times')
 if end_dt <= start_dt: raise HTTPException(422,'Session end time must be after start time')
 for key,value in values.items(): setattr(z,key,value)
 s.commit();return {'id':z.id}
@app.delete('/sessions/{sid}')
def delete_session(sid:int):
 s=Session(); z=s.get(StudySession,sid)
 if not z: raise HTTPException(404,'Session not found')
 s.delete(z);s.commit();return {'ok':True}
@app.post('/sessions/{sid}/attendance')
def attendance(sid:int,user_id:int):
 s=Session(); session=s.get(StudySession,sid)
 if not session: raise HTTPException(404,'Session not found')
 attendees=arr(session.attendees)
 if str(user_id) not in [str(a) for a in attendees] and user_id not in attendees:
  attendees.append(user_id);session.attendees=json.dumps(attendees);s.commit()
 return {'attendees':attendees}
@app.get('/notifications/{uid}')
def notifications(uid:int):
 s=Session(); return [{'id':n.id,'type':n.type,'content':n.content,'read':bool(n.read),'createdAt':n.created_at.isoformat()} for n in s.query(Notification).filter_by(user_id=uid).order_by(Notification.created_at.desc())]
@app.post('/notifications/{nid}/read')
def read_notification(nid:int):
 s=Session(); n=s.get(Notification,nid)
 if not n: raise HTTPException(404,'Notification not found')
 n.read=1;s.commit();return {'ok':True}
@app.get('/dashboard/{uid}')
def dashboard(uid:int):
 s=Session(); gs=[g for g in s.query(Group).all() if uid in [int(m) for m in arr(g.members) if str(m).isdigit()]]; tasks=[]; sessions=[]
 for g in gs:
  tasks += s.query(Task).filter_by(group_id=g.id).all(); sessions += s.query(StudySession).filter_by(group_id=g.id).all()
 match_count=len(matches(uid)); completed=len([t for t in tasks if t.status=='Completed'])
 study_minutes=0
 for session in sessions:
  is_attendee = any(str(a) == str(uid) for a in arr(session.attendees))
  if is_attendee and session.ends_at and session.starts_at:
   try:
    s_dt = datetime.fromisoformat(session.starts_at)
    e_dt = datetime.fromisoformat(session.ends_at)
    if e_dt > s_dt:
     study_minutes += (e_dt - s_dt).total_seconds() / 60
   except ValueError: pass
 upcoming=sorted([x for x in sessions if x.starts_at >= datetime.now().isoformat()],key=lambda x:x.starts_at)
 return {'compatibleBuddies':match_count,'activeGroups':len(gs),'completedTasks':completed,'studyHours':round(study_minutes/60,1),'attendedSessions':len([x for x in sessions if any(str(a) == str(uid) for a in arr(x.attendees))]),'tasks':[{'id':t.id,'title':t.title,'subject':t.subject,'priority':t.priority,'status':t.status,'deadline':t.deadline} for t in tasks],'sessions':[{'id':x.id,'title':x.title,'subject':x.subject,'topic':x.topic,'startsAt':x.starts_at,'endsAt':x.ends_at,'mode':x.mode,'location':x.location,'platform':x.platform,'link':x.link,'attendees':arr(x.attendees)} for x in sessions],'upcomingSessions':[{'id':x.id,'title':x.title,'subject':x.subject,'topic':x.topic,'startsAt':x.starts_at,'endsAt':x.ends_at,'mode':x.mode,'location':x.location,'platform':x.platform,'link':x.link,'attendees':arr(x.attendees)} for x in upcoming]}
def seed():
 s=Session()
 if s.query(User).count(): return
 data=[('Maya Patel',['Python','AI/ML','Mathematics'],['Machine Learning','Pandas','Calculus'],['Exam Preparation','Project Work'],['Discussion','Problem Solving'],['Mon 18','Wed 18','Sat 10']),('Arjun Mehta',['Python','Data Structures','C++'],['Algorithms','Arrays','Pandas'],['Coding Practice','Interview Preparation'],['Problem Solving','Teaching Others'],['Mon 18','Thu 19','Sat 10']),('Riya Sharma',['DBMS','OS','Computer Networks'],['SQL','Normalization','Process Scheduling'],['Exam Preparation','Assignment Help'],['Reading/Notes','Silent Study'],['Tue 17','Wed 18','Sun 11']),('Kabir Singh',['Web Development','JavaScript','Python'],['React','APIs','Pandas'],['Project Work','General Learning'],['Discussion','Videos'],['Mon 18','Fri 17','Sat 10']),('Ananya Rao',['Java','DBMS','Data Structures'],['OOP','SQL','Trees'],['Competitive Programming','Exam Preparation'],['Problem Solving','Silent Study'],['Wed 18','Thu 19','Sun 11'])]
 for i,(n,sub,top,go,sty,av) in enumerate(data): s.add(User(name=n,email=n.lower().replace(' ','')+'@demo.edu',password='demo123',college='National Institute of Technology',course='B.Tech CSE',year=(i%3)+2,avatar=['🌻','🧠','✨','🚀','🌿'][i],subjects=json.dumps(sub),topics=json.dumps(top),goals=json.dumps(go),styles=json.dumps(sty),availability=json.dumps(av),levels=json.dumps({x:'Intermediate' for x in sub})))
 s.commit(); g=Group(name='Python Project Lab',description='Build, learn, and review together.',subject='Python',goal='Project Work',max_members=6,privacy='Public',owner_id=1,members=json.dumps([1,2]));s.add(g);s.commit();s.add_all([Task(group_id=g.id,title='Finish model evaluation',priority='High',status='In Progress',deadline='2026-10-06'),Task(group_id=g.id,title='Review API routes',priority='Medium',status='To Do',deadline='2026-10-08'),StudySession(group_id=g.id,title='ML revision sprint',topic='Model evaluation',starts_at='2026-10-05T18:00',link='')]);s.commit()
seed()
