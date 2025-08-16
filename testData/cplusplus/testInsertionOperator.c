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

// Simple out parameters
std::cout << "Testing std::cout =>Expected A1 instead of ";
std::cout << "Testing std::cout =>Expected A2 instead of " << documentType;
std::cout << "Testing std::cout =>Expected A3 instead of " << documentType << std::endl;
std::cerr << "Testing std::cerr =>Expected B1 instead of ";
std::cerr << "Testing std::cerr =>Expected B2 instead of " << documentType;
std::cerr << "Testing std::cerr =>Expected B3 instead of " << documentType << std::endl;

// Test adjacent string literals
std::cout << "Testing adjacent-string-literals =>Expected C1 instead of " << documentType
          << ". Please specify C2"
          << " or any other variable in the C* family"
          << " for this scenario to work." << std::endl;