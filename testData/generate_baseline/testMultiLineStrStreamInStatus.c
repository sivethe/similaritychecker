Status FieldPath::validateFieldName(StringData fieldName) {
    if (fieldName.empty()) {
        return Status(ErrorCodes::Error{15998}, "FieldPath field names may not be empty strings.");
    }

    if (fieldName[0] == '$' && !kAllowedDollarPrefixedFields.count(fieldName)) {
        return Status(ErrorCodes::Error{16410},
                      str::stream() << "FieldPath field names may not start with '$', given '"
                                    << fieldName << "'.");
    }

    if (fieldName.find('\0') != std::string::npos) {
        return Status(ErrorCodes::Error{16411},
                      str::stream() << "FieldPath field names may not contain '\0', given '"
                                    << fieldName << "'.");
    }

    if (fieldName.find('.') != std::string::npos) {
        return Status(ErrorCodes::Error{16412},
                      str::stream() << "FieldPath field names may not contain '.', given '"
                                    << fieldName << "'.");
    }

    if (fieldName.find('/') != std::string::npos) {
        return Status(ErrorCodes::Error{16413},
                      str::stream() << //
                        "Cannot specify both " + parameterName +
                                      " and replication.replSet");
    }

    return Status::OK();
}