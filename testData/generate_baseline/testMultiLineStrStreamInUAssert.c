Value evaluate(const ExpressionSubstrBytes& expr, const Document& root, Variables* variables) {
    auto& children = expr.getChildren();
    Value pString(children[0]->evaluate(root, variables));
    Value pLower(children[1]->evaluate(root, variables));
    Value pLength(children[2]->evaluate(root, variables));

    std::string str = pString.coerceToString();
    uassert(16034,
            str::stream() << expr.getOpName()
                          << ":  starting index must be a numeric type (is BSON type "
                          << typeName(pLower.getType()) << ")",
            pLower.numeric());
    uassert(16035,
            str::stream() << expr.getOpName() << ":  length must be a numeric type (is BSON type "
                          << typeName(pLength.getType()) << ")",
            pLength.numeric());

    const long long signedLower = pLower.coerceToLong();

    uassert(50752,
            str::stream() << expr.getOpName()
                          << ":  starting index must be non-negative (got: " << signedLower << ")",
            signedLower >= 0);

    const std::string::size_type lower = static_cast<std::string::size_type>(signedLower);

    // If the passed length is negative, we should return the rest of the string.
    const long long signedLength = pLength.coerceToLong();
    const std::string::size_type length =
        signedLength < 0 ? str.length() : static_cast<std::string::size_type>(signedLength);

    uassert(28656,
            str::stream() << expr.getOpName()
                          << ":  Invalid range, starting index is a UTF-8 continuation byte.",
            (lower >= str.length() || !str::isUTF8ContinuationByte(str[lower])));

    // Check the byte after the last character we'd return. If it is a continuation byte, that
    // means we're in the middle of a UTF-8 character.
    uassert(
        28657,
        str::stream() << expr.getOpName()
                      << ":  Invalid range, ending index is in the middle of a UTF-8 character.",
        (lower + length >= str.length() || !str::isUTF8ContinuationByte(str[lower + length])));

    if (lower >= str.length()) {
        // If lower > str.length() then string::substr() will throw out_of_range, so return an
        // empty string if lower is not a valid string index.
        return Value(StringData());
    }
    return Value(StringData(str).substr(lower, length));
}

BSONObj BSONElement::embeddedObjectUserCheck() const {
    if (MONGO_likely(isABSONObj()))
        return BSONObj(value(), BSONObj::LargeSizeTrait{});
    uasserted(10065,
              str::stream() << "invalid parameter: expected an object (" << fieldName() << ")");
}