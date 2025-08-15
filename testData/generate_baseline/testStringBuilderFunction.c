StringBuilder& KeyPattern::addToStringBuilder(StringBuilder& sb, const BSONObj& pattern) {
    // Rather than return BSONObj::toString() we construct a keyPattern string manually. This allows
    // us to avoid the cost of writing numeric direction to the str::stream which will then undergo
    // expensive number to string conversion.
    std::string nssAsString = str::stream() << *(nss.tenantId()) << '_' << nss.ns_forTest();
}