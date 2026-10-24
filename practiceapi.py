from fastapi import FastAPI,Path
from typing import Optional
from pydantic import BaseModel
app=FastAPI() #instanc of fastapi class

#create and endpoint ,an endpoint is the door of communication where the req shld land at from the request made in frontend

#amoazon.com/delete-user #here delete user is the endpoint after the req lands at the endpoint it does some specific work
#core ones are 
#GET -GET AN INFO 
# POST -CREATE SMTG NEW (POST INFO TO ENDPOINT)
# PUT-UPDATE DATA
# DELETE -DELETE SMTG
students={
  1:{
    "name":"john",
    "age":12
  }
}
#creating an api
@app.get("/")  #homepage so ntg after slash
def index():
  return {"name" :"First Data"}

@app.get("/get-student/{student_id}") #Path parameter way
def get_student(student_id:int =Path(...,description="The id of the student you want to view",gt=0)):
  return students[student_id]

@app.get("/get-by-name") #query parameter way
def get_student(name:Optional[str]=None):
  for student_id in students:
    if students[student_id]["name"]==name:
      return students[student_id]
  return {"Data :Not Found"}  
 #now combining both query and pth parameters

class Student(BaseModel):
  name :str
  age :int
@app.post("/create-student/{student_id}")
def create_student(student_id :int,student :Student):
  if student_id in students:
    return{"Error":"Student exists"}
  students[student_id]=student
  return students[student_id]

class UpdateStudent(BaseModel):
  name:Optional[str]=None
  age:Optional[int]=None
@app.put("/update-student/{student_id}")
def update_student(student_id:int,student:UpdateStudent):
  if student_id not in students:
    return{"Error":"Student doesnt exist"}
  if student.name!=None:
    students[student_id].name=student.name
  if student.age!=None:
    students[student_id].age=student.age 
  return students[student_id]

@app.delete("/delete-student/{student_id}")
def delete_student(student_id: int):
    if student_id not in students:
        return {"Error": "Student does not exist"}

    del students[student_id]
    return {"Message": "Student deleted successfully"}
