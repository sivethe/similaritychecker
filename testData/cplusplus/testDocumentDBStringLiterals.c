
// Verify multi-line errmsg
errmsg("PlanExecutor error during aggregation :: caused by :: "
       "Invalid range: Expected the sortBy field to be a Date, "
       "but it was %s", BsonTypeName(element->bsonValue.value_type))

// Verify multi-line errdetail_log
errdetail_log("PlanExecutor error during aggregation :: caused by :: "
              "Invalid range: Expected the sortBy field to be a Date, "
              "but it was %s", BsonTypeName(element->bsonValue.value_type))