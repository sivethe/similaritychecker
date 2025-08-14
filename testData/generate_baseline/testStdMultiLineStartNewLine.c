Status validateIdIndexSpec(const BSONObj& indexSpec) {
    bool isClusteredIndexSpec = indexSpec.hasField(IndexDescriptor::kClusteredFieldName);

    if (!isClusteredIndexSpec) {
        // Field names for a 'clustered' index spec have already been validated through
        // allowedClusteredIndexFieldNames.

        for (auto&& indexSpecElem : indexSpec) {
            auto indexSpecElemFieldName = indexSpecElem.fieldNameStringData();
            if (!allowedIdIndexFieldNames.count(indexSpecElemFieldName)) {
                return {ErrorCodes::InvalidIndexSpecificationOption,
                        str::stream()
                            << "The field '" << indexSpecElemFieldName
                            << "' is not valid for an _id index specification. Specification: "
                            << indexSpec};
            }
        }
    }

    auto keyPatternElem = indexSpec[IndexDescriptor::kKeyPatternFieldName];
    // validateIndexSpec() should have already verified that 'keyPatternElem' is an object.
    invariant(keyPatternElem.type() == BSONType::object);
    if (SimpleBSONObjComparator::kInstance.evaluate(keyPatternElem.Obj() != BSON("_id" << 1))) {
        return {ErrorCodes::BadValue,
                str::stream() << "The field '" << IndexDescriptor::kKeyPatternFieldName
                              << "' for an _id index must be {_id: 1}, but got "
                              << keyPatternElem.Obj()};
    }

    if (!indexSpec[IndexDescriptor::kHiddenFieldName].eoo()) {
        return Status(ErrorCodes::BadValue, "can't hide _id index");
    }

    return Status::OK();
}