verify(Err100,
       str::stream() << "Function " << this->funcName() << " takes [" << ExpectedArguments
                     << "] arguments. However, function was called with " << this->arguments.size() << " arguments.",
       this->arguments.size() == ExpectedArguments);

// Verify StringBuilder usage
auto message = StringBuilder();
message << "Format: python3 SomeSamplePythonFile.py ";
message << args.toString();
for (; i != args.keys->rend(); ++i) {
    message << " => " << args.Values[*i].toString();
}

// Verify multi-line InsertionOperator with function at end
return {Err100,
        str::stream() << "Invalid use of Function1 [" << this->funcName() << "]. "
                      << "Function was called with arguments: " 
                      << this->arguments.size()};

