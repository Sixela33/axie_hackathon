from fastapi import FastAPI, Depends
from database import engine, SessionLocal
import models
from sqlalchemy.orm import Session
from data_types import User

app = FastAPI()

models.Base.metadata.create_all(bind=engine)

def get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

@app.get('/')
async def root(db: Session = Depends(get_db)):
    return db.query(models.User).all()

@app.post('/')
async def create_user(user: User, db: Session = Depends(get_db)):
    user_model = models.User()
    user_model.username = user.username

    db.add(user_model)
    db.commit()

    return user