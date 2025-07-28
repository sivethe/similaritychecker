#include <iostream>
#include <string>

// Sample function demonstrating multi-line error message handling
void validateDBRefField(const std::string& fieldName, const std::string& fieldType, const std::string& fullPath, bool hasNextField, const std::string& nextFieldName) {
    if (fieldName == "$ref") {
        if (fieldType != "String") {
            std::cout << "The DBRef $ref field must be a String, not a " << fieldType << std::endl;
            return;
        }

        if (!hasNextField || nextFieldName != "$id") {
            std::cerr << "The DBRef $ref field must be followed by a $id field" << std::endl;
            return;
        }
    } else {
        // Not an okay, $ prefixed field name.
        if (!fieldName.empty() && fieldName[0] == '$') {
            std::stream() << "The dollar ($) prefixed field '" << fieldName
                      << "' in '" << fullPath
                      << "' is not allowed in the context of an update's replacement"
                      << " document. Consider using an aggregation pipeline with"
                      << " $replaceWith." << std::endl;
            return;
        }
        
        // Test adjacent string literals (C++ auto-concatenation)
        if (fieldName == "$invalid") {
            std::cerr << "Invalid field detected: " << fieldName
                      << " - this field type is not supported"
                         " in the current schema version"
                         " and should be removed." << std::endl;
            return;
        }
    }
}
