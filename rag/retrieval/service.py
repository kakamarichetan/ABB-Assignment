from pathlib import Path
import re,joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
class RAGService:
 def __init__(self,index_path,documents_path): self.index_path=Path(index_path); self.documents_path=Path(documents_path)
 def ingest(self):
  docs=[]
  for p in sorted(self.documents_path.glob("*.md")):
   for i,s in enumerate(re.split(r"(?m)^## ",p.read_text(encoding="utf8"))):
    if not s.strip(): continue
    lines=s.splitlines(); title=lines[0].strip() if lines else p.stem; body="\n".join(lines[1:]).strip()
    docs.append({"document":p.name,"section":title,"text":body,"asset_ids":re.findall(r"[A-Z]+-\d+",s)})
  self.index_path.parent.mkdir(parents=True,exist_ok=True)
  v=TfidfVectorizer(ngram_range=(1,2),stop_words="english"); m=v.fit_transform([x["text"] for x in docs])
  joblib.dump({"docs":docs,"vectorizer":v,"matrix":m},self.index_path)
 def search(self,q,asset_ids=None,k=5):
  if not self.index_path.exists(): self.ingest()
  d=joblib.load(self.index_path); scores=cosine_similarity(d["vectorizer"].transform([q]),d["matrix"])[0]; hits=[]
  for i,s in enumerate(scores):
   x=d["docs"][i]
   if asset_ids and x["asset_ids"] and not set(asset_ids)&set(x["asset_ids"]): continue
   if s>0:hits.append((float(s),x))
  return [{"score":round(s,4),**x,"citation":f"{x['document']} — {x['section']}"} for s,x in sorted(hits,reverse=True,key=lambda z:z[0])[:k]]
