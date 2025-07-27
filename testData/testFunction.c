/*
 * Pre-checks the $changeStream pipeline stages to ensure that only supported stages are added to
 * the $changestream pipeline, also ensures that $changeStream is the first stage in the pipeline.
 * This function is called before the pipeline is mutated. It also checks if the feature is enabled.
 */
static void
PreCheckChangeStreamPipelineStages(const bson_value_t *pipelineValue,
								   const AggregationPipelineBuildContext *context)
{
	bson_iter_t pipelineIterator;
	BsonValueInitIterator(pipelineValue, &pipelineIterator);
	int stageNum = 0;
	while (bson_iter_next(&pipelineIterator))
	{
		bson_iter_t documentIterator;

		/* Any errors here will be handled in MutateQueryWithPipeline*/
		if (!BSON_ITER_HOLDS_DOCUMENT(&pipelineIterator) ||
			!bson_iter_recurse(&pipelineIterator, &documentIterator))
		{
			continue;
		}

		/* Any errors here will be handled in MutateQueryWithPipeline*/
		pgbsonelement stageElement;
		if (!TryGetSinglePgbsonElementFromBsonIterator(&documentIterator, &stageElement))
		{
			continue;
		}

		const char *stageName = stageElement.path;

		/* The first change should be $changeStream. */
		if (stageNum == 0 && strcmp(stageName, "$changeStream") == 0)
		{
			continue;
		}
		/* Check the next stages to be one of the allowed stages. */
		else if (!StringArrayContains(CompatibleChangeStreamPipelineStages,
									  COMPATIBLE_CHANGE_STREAM_STAGES_COUNT,
									  stageName))
		{
			ereport(ERROR, (errcode(ERRCODE_DOCUMENTDB_ILLEGALOPERATION),
							errmsg(
								"Stage %s is not permitted in a $changeStream pipeline",
								stageName)));
		}
		stageNum++;
	}
}