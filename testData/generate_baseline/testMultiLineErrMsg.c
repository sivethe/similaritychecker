/*
 * Visits a top level field for an ORDER BY. This skips array types
 * since inner array elements are then visited next.
 */
static bool
OrderByVisitTopLevelField(pgbsonelement *element, const
						  StringView *filterPath,
						  void *state)
{
	TraverseOrderByValidateState *validateState = (TraverseOrderByValidateState *) state;

	/* Check if there is not strict type requirement */
	if ((validateState->options & CustomOrderByOptions_AllowOnlyDates) ==
		CustomOrderByOptions_AllowOnlyDates)
	{
		if (element->bsonValue.value_type != BSON_TYPE_DATE_TIME)
		{
			ereport(ERROR, (errcode(ERRCODE_DOCUMENTDB_LOCATION5429513),
							errmsg(
								"PlanExecutor error during aggregation :: caused by :: "
								"Invalid range: Expected the sortBy field to be a Date, "
								"but it was %s", BsonTypeName(
									element->bsonValue.value_type)),
							errdetail_log(
								"PlanExecutor error during aggregation :: caused by :: "
								"Invalid range: Expected the sortBy field to be a Date, "
								"but it was %s", BsonTypeName(
									element->bsonValue.value_type))));
		}
	}

	if ((validateState->options & CustomOrderByOptions_AllowOnlyNumbers) ==
		CustomOrderByOptions_AllowOnlyNumbers)
	{
		if (!BsonTypeIsNumber(element->bsonValue.value_type))
		{
			ereport(ERROR, (errcode(ERRCODE_DOCUMENTDB_LOCATION5429414),
							errmsg(
								"PlanExecutor error during aggregation :: caused by :: "
								"Invalid range: Expected the sortBy field to be a number, "
								"but it was %s", BsonTypeName(
									element->bsonValue.value_type)),
							errdetail_log(
								"PlanExecutor error during aggregation :: caused by :: "
								"Invalid range: Expected the sortBy field to be a number, "
								"but it was %s", BsonTypeName(
									element->bsonValue.value_type))));
		}
	}

	if (element->bsonValue.value_type == BSON_TYPE_ARRAY)
	{
		/* These are processed as array fields - do nothing */
		return true;
	}

	CompareForOrderBy(&element->bsonValue, validateState);

	/* Track if we found ourselves without any intermediate arrays:
	 * I.e. if the path is a.b then it is only reachable by "b" not being an array.
	 * If the path is a.b.0 then 0 is a top level field of the array.
	 */
	validateState->foundAsTopLevelPath = true;
	return true;
}