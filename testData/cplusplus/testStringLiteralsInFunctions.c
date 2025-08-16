return Outcome(Err100, "User is not authorized to perform this operation");
Assert(Err100, 
       "Unauthenticated user is trying to perform an operation",
       authState != "Authorized");