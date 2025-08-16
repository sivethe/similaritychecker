
// Verify multi-line errmsg
errmsg("PlanExecutor error during aggregation :: caused by :: "
       "Invalid range: Expected the sortBy field to be a Date, "
       "but it was %s", BsonTypeName(element->bsonValue.value_type))

errmsg("The limit field in delete objects must be 0 "
       "or 1. Got " INT64_FORMAT, limit)

// Verify that concatenated_string pattern with less than 3 words (default min-words) is ignored without error
errmsg("This"
       "is")

// Verify multi-line errdetail_log
errdetail_log("PlanExecutor error during aggregation :: caused by :: "
              "Invalid range: Expected the sortBy field to be a Date, "
              "but it was %s", BsonTypeName(element->bsonValue.value_type))

// Verify string-concatenation both in single and multi line
appendStringInfo(&selectQuery,
                "SELECT shard_key_value FROM %s.documents_" UINT64_FORMAT
                " WHERE object_id = $1::%s",
                ApiDataSchemaName, collection->collectionId,
                FullBsonTypeName);

// Verify that comments are ignored inside concatenated_string parsing
appendStringInfo(createTableStringInfo,
                "CREATE TABLE %s ("

                /* derived shard key field generated from the real shard key */
                "shard_key_value bigint not null,"

                /* unique ID of the object */
                "object_id %s.bson not null,"

                /*
                * the document
                *
                * NB: Ensure to match DOCUMENT_DATA_TABLE_DOCUMENT_VAR_ contants
                *     defined in collection.h if you decide changing definiton
                *     or position of document column.
                */
                "document %s.bson not null",
                dataTableNameInfo->data,
                CoreSchemaName, CoreSchemaName);