from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timedelta
import os, json, random

DB=os.getenv('DATABASE_URL','sqlite:///./study_buddy.db')
engine=create_engine(DB, connect_args={'check_same_thread':False} if DB.startswith('sqlite') else {})
Session=sessionmaker(bind=engine); Base=declarative_base()
class User(Base):
 __tablename__='users'
 id=Column(Integer,primary_key=True); name=Column(String); email=Column(String,unique=True); password=Column(String); college=Column(String,default=''); course=Column(String,default=''); year=Column(Integer,default=2); avatar=Column(String,default='📚'); subjects=Column(Text,default='[]'); topics=Column(Text,default='[]'); goals=Column(Text,default='[]'); styles=Column(Text,default='[]'); levels=Column(Text,default='{}'); availability=Column(Text,default='[]'); duration=Column(Integer,default=90); group_size=Column(Integer,default=4)
class Connection(Base):
 __tablename__='connections'
 id=Column(Integer,primary_key=True); sender_id=Column(Integer); recipient_id=Column(Integer); status=Column(String,default='pending'); created_at=Column(DateTime,default=datetime.utcnow)
class Group(Base):
 __tablename__='groups'
 id=Column(Integer,primary_key=True); name=Column(String); description=Column(Text); subject=Column(String); goal=Column(String); max_members=Column(Integer); privacy=Column(String); owner_id=Column(Integer); members=Column(Text,default='[]')
class Task(Base):
 __tablename__='tasks'
 id=Column(Integer,primary_key=True); group_id=Column(Integer); title=Column(String); priority=Column(String,default='Medium'); status=Column(String,default='To Do'); deadline=Column(String,default='')
class StudySession(Base):
 __tablename__='sessions'
 id=Column(Integer,primary_key=True); group_id=Column(Integer); title=Column(String); topic=Column(String); starts_at=Column(String); link=Column(String,default='')
class Notification(Base):
 __tablename__='notifications'
 id=Column(Integer,primary_key=True); user_id=Column(Integer); type=Column(String); content=Column(String); read=Column(Integer,default=0); created_at=Column(DateTime,default=datetime.utcnow)
Base.metadata.create_all(engine)
app=FastAPI(title='Study Buddy Finder API'); app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:3000'],allow_methods=['*'],allow_headers=['*'])
def arr(x): return json.loads(x or '[]')
def profile(u):
 return {'id':u.id,'name':u.name,'email':u.email,'college':u.college,'course':u.course,'year':u.year,'avatar':u.avatar,'subjects':arr(u.subjects),'topics':arr(u.topics),'goals':arr(u.goals),'styles':arr(u.styles),'levels':json.loads(u.levels or '{}'),'availability':arr(u.availability),'duration':u.duration,'groupSize':u.group_size}
def score(a,b):
 def overlap(x,y): return 100*len(set(x)&set(y))/max(1,len(set(x)|set(y)))
 av=overlap(a['availability'],b['availability']); parts={'Subjects':overlap(a['subjects'],b['subjects']),'Topics':overlap(a['topics'],b['topics']),'Goals':overlap(a['goals'],b['goals']),'Availability':av,'Study style':overlap(a['styles'],b['styles']),'Skill level':70 if set(a['subjects'])&set(b['subjects']) else 40}
 weights=[.25,.15,.20,.20,.10,.10]; total=round(sum(v*w for v,w in zip(parts.values(),weights)))
 return total, {k:round(v) for k,v in parts.items()}
class Auth(BaseModel): name:str=''; email:str; password:str
class ProfileIn(BaseModel): name:str; college:str=''; course:str=''; year:int=2; avatar:str='📚'; subjects:list[str]=[]; topics:list[str]=[]; goals:list[str]=[]; styles:list[str]=[]; levels:dict={}; availability:list[str]=[]; duration:int=90; groupSize:int=4
class GroupIn(BaseModel): name:str; description:str=''; subject:str; goal:str; max_members:int=6; privacy:str='Public'; owner_id:int
class TaskIn(BaseModel): group_id:int; title:str; priority:str='Medium'; deadline:str=''
class SessionIn(BaseModel): group_id:int; title:str; topic:str; starts_at:str; link:str=''
@app.get('/health')
def health(): return {'ok':True}
@app.post('/auth/register')
def register(x:Auth):
 s=Session()
 if s.query(User).filter_by(email=x.email).first(): raise HTTPException(400,'Email already registered')
 u=User(name=x.name or x.email.split('@')[0],email=x.email,password=x.password); s.add(u);s.commit(); return profile(u)
@app.post('/auth/login')
def login(x:Auth):
 u=Session().query(User).filter_by(email=x.email,password=x.password).first()
 if not u: raise HTTPException(401,'Invalid email or password')
 return profile(u)
@app.put('/users/{uid}')
def update(uid:int,x:ProfileIn):
 s=Session();u=s.get(User,uid)
 if not u: raise HTTPException(404,'User not found')
 for k,v in x.model_dump().items(): setattr(u,{'groupSize':'group_size'}.get(k,k),json.dumps(v) if isinstance(v,(list,dict)) else v)
 s.commit();return profile(u)
@app.get('/matches/{uid}')
def matches(uid:int):
 s=Session(); me=s.get(User,uid)
 if not me: raise HTTPException(404,'User not found')
 a=profile(me); out=[]
 for u in s.query(User).filter(User.id!=uid):
  b=profile(u); total,breakdown=score(a,b)
  out.append({**b,'compatibility':total,'breakdown':breakdown,'commonSubjects':list(set(a['subjects'])&set(b['subjects'])),'commonTopics':list(set(a['topics'])&set(b['topics'])),'reasons':[f"{len(set(a['subjects'])&set(b['subjects']))} shared subjects",f"{len(set(a['goals'])&set(b['goals']))} shared goals",f"{len(set(a['availability'])&set(b['availability']))} overlapping study slots"]})
 return sorted(out,key=lambda x:x['compatibility'],reverse=True)
@app.post('/connections')
def connect(sender_id:int,recipient_id:int):
 s=Session();c=Connection(sender_id=sender_id,recipient_id=recipient_id);s.add(c); sender=s.get(User,sender_id);s.add(Notification(user_id=recipient_id,type='connection',content=f'{sender.name} sent you a connection request.'));s.commit();return {'id':c.id,'status':'pending'}
@app.get('/connections/{uid}')
def connections(uid:int):
 s=Session(); cs=s.query(Connection).filter((Connection.sender_id==uid)|(Connection.recipient_id==uid)).all(); return [{'id':c.id,'status':c.status,'direction':'incoming' if c.recipient_id==uid else 'sent','person':profile(s.get(User,c.sender_id if c.recipient_id==uid else c.recipient_id))} for c in cs]
@app.post('/connections/{cid}/{action}')
def connection_action(cid:int,action:str):
 s=Session();c=s.get(Connection,cid); c.status='accepted' if action=='accept' else 'declined'
 if action=='accept': s.add(Notification(user_id=c.sender_id,type='connection',content=f'{s.get(User,c.recipient_id).name} accepted your connection request.'))
 s.commit();return {'status':c.status}
@app.get('/groups/{uid}')
def groups(uid:int): return [dict(id=g.id,name=g.name,description=g.description,subject=g.subject,goal=g.goal,maxMembers=g.max_members,privacy=g.privacy,members=arr(g.members)) for g in Session().query(Group).all() if uid in arr(g.members)]
@app.post('/groups')
def create_group(x:GroupIn):
 s=Session();g=Group(name=x.name,description=x.description,subject=x.subject,goal=x.goal,max_members=x.max_members,privacy=x.privacy,owner_id=x.owner_id,members=json.dumps([x.owner_id]));s.add(g);s.commit();return {'id':g.id}
@app.get('/groups/{gid}/workspace')
def workspace(gid:int):
 s=Session(); return {'tasks':[{'id':t.id,'title':t.title,'priority':t.priority,'status':t.status,'deadline':t.deadline} for t in s.query(Task).filter_by(group_id=gid)],'sessions':[{'id':x.id,'title':x.title,'topic':x.topic,'startsAt':x.starts_at,'link':x.link} for x in s.query(StudySession).filter_by(group_id=gid)]}
@app.post('/tasks')
def create_task(x:TaskIn): s=Session();t=Task(**x.model_dump());s.add(t);s.commit();return {'id':t.id}
@app.patch('/tasks/{tid}')
def update_task(tid:int,status:str):
 s=Session(); t=s.get(Task,tid)
 if not t: raise HTTPException(404,'Task not found')
 t.status=status;s.commit();return {'id':t.id,'status':t.status}
@app.post('/sessions')
def create_session(x:SessionIn): s=Session();z=StudySession(**x.model_dump());s.add(z);s.commit();return {'id':z.id}
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
 s=Session(); gs=[g for g in s.query(Group).all() if uid in arr(g.members)]; tasks=[]; sessions=[]
 for g in gs:
  tasks += s.query(Task).filter_by(group_id=g.id).all(); sessions += s.query(StudySession).filter_by(group_id=g.id).all()
 match_count=len(matches(uid)); completed=len([t for t in tasks if t.status=='Completed'])
 upcoming=sorted([x for x in sessions if x.starts_at >= datetime.now().isoformat()],key=lambda x:x.starts_at)
 return {'compatibleBuddies':match_count,'activeGroups':len(gs),'completedTasks':completed,'studyHours':0,'tasks':[{'id':t.id,'title':t.title,'priority':t.priority,'status':t.status,'deadline':t.deadline} for t in tasks],'upcomingSessions':[{'id':x.id,'title':x.title,'topic':x.topic,'startsAt':x.starts_at,'link':x.link} for x in upcoming]}
def seed():
 s=Session()
 if s.query(User).count(): return
 data=[('Maya Patel',['Python','AI/ML','Mathematics'],['Machine Learning','Pandas','Calculus'],['Exam Preparation','Project Work'],['Discussion','Problem Solving'],['Mon 18','Wed 18','Sat 10']),('Arjun Mehta',['Python','Data Structures','C++'],['Algorithms','Arrays','Pandas'],['Coding Practice','Interview Preparation'],['Problem Solving','Teaching Others'],['Mon 18','Thu 19','Sat 10']),('Riya Sharma',['DBMS','OS','Computer Networks'],['SQL','Normalization','Process Scheduling'],['Exam Preparation','Assignment Help'],['Reading/Notes','Silent Study'],['Tue 17','Wed 18','Sun 11']),('Kabir Singh',['Web Development','JavaScript','Python'],['React','APIs','Pandas'],['Project Work','General Learning'],['Discussion','Videos'],['Mon 18','Fri 17','Sat 10']),('Ananya Rao',['Java','DBMS','Data Structures'],['OOP','SQL','Trees'],['Competitive Programming','Exam Preparation'],['Problem Solving','Silent Study'],['Wed 18','Thu 19','Sun 11'])]
 for i,(n,sub,top,go,sty,av) in enumerate(data): s.add(User(name=n,email=n.lower().replace(' ','')+'@demo.edu',password='demo123',college='National Institute of Technology',course='B.Tech CSE',year=(i%3)+2,avatar=['🌻','🧠','✨','🚀','🌿'][i],subjects=json.dumps(sub),topics=json.dumps(top),goals=json.dumps(go),styles=json.dumps(sty),availability=json.dumps(av),levels=json.dumps({x:'Intermediate' for x in sub})))
 s.commit(); g=Group(name='Python Project Lab',description='Build, learn, and review together.',subject='Python',goal='Project Work',max_members=6,privacy='Public',owner_id=1,members=json.dumps([1,2]));s.add(g);s.commit();s.add_all([Task(group_id=g.id,title='Finish model evaluation',priority='High',status='In Progress',deadline='2026-10-06'),Task(group_id=g.id,title='Review API routes',priority='Medium',status='To Do',deadline='2026-10-08'),StudySession(group_id=g.id,title='ML revision sprint',topic='Model evaluation',starts_at='2026-10-05T18:00',link='')]);s.commit()
seed()
