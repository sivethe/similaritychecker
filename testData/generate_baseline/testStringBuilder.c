Status ViewGraph::_validateChildren(uint64_t startingId,
                                    uint64_t currentId,
                                    int currentDepth,
                                    StatsMap* statsMap,
                                    std::vector<uint64_t>* traversalIds) {
    const Node& currentNode = _graph[currentId];
    traversalIds->push_back(currentId);

    // If we've encountered the id of the starting node, we've found a cycle in the graph.
    if (currentDepth > 0 && currentId == startingId) {
        auto iterator = traversalIds->rbegin();
        auto errmsg = StringBuilder();

        errmsg << "View cycle detected: ";
        errmsg << _graph[*iterator].nss.toStringForErrorMsg();
        for (; iterator != traversalIds->rend(); ++iterator) {
            errmsg << " => " << _graph[*iterator].nss.toStringForErrorMsg();
        }
        return {ErrorCodes::GraphContainsCycle, errmsg.str()};
    }

    // Return early if we've already exceeded the maximum depth. This will also be triggered if
    // we're traversing a cycle introduced through unvalidated inserts.
    if (currentDepth > kMaxViewDepth) {
        return {ErrorCodes::ViewDepthLimitExceeded,
                str::stream() << "View depth limit exceeded; maximum depth is "
                              << ViewGraph::kMaxViewDepth};
    }

    int maxHeightOfChildren = 0;
    int maxSizeOfChildren = 0;
    for (uint64_t childId : currentNode.children) {
        if ((*statsMap)[childId].checked) {
            continue;
        }

        const auto& childNode = _graph[childId];
        if (childNode.isView() &&
            !CollatorInterface::collatorsMatch(currentNode.collator.get(),
                                               childNode.collator.get())) {
            return {ErrorCodes::OptionNotSupportedOnView,
                    str::stream() << "View " << currentNode.nss.toStringForErrorMsg()
                                  << " has a collation that does not match the collation of view "
                                  << childNode.nss.toStringForErrorMsg()};
        }

        auto res = _validateChildren(startingId, childId, currentDepth + 1, statsMap, traversalIds);
        if (!res.isOK()) {
            return res;
        }

        maxHeightOfChildren = std::max(maxHeightOfChildren, (*statsMap)[childId].height);
        maxSizeOfChildren = std::max(maxSizeOfChildren, (*statsMap)[childId].cumulativeSize);
    }

    traversalIds->pop_back();
    (*statsMap)[currentId].checked = true;
    (*statsMap)[currentId].height = maxHeightOfChildren + 1;
    (*statsMap)[currentId].cumulativeSize += maxSizeOfChildren + currentNode.size;
    return Status::OK();
}