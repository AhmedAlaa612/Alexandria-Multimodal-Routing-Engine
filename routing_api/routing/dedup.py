"""
Pre-rank corridor deduplication.
"""


def deduplicate_routing_results(routing_results):
    """
    Keep the best-cost result per corridor signature (stop sequence + agency
    sequence + transfer count).  Merges alternative trip_ids for
    same-corridor variants.
    """
    if not routing_results:
        return []

    def corridor_sig(cost_details):
        stops, agencies, transfers = [], [], 0
        for d in cost_details:
            if d["type"] == "trip":
                if not stops:
                    stops.append(d["from_stop_id"])
                stops.append(d["to_stop_id"])
                agencies.append(d.get("agency_id"))
            elif d["type"] == "transfer":
                transfers += 1
                end_sid = d.get("pathway", {}).get("end_stop_id")
                if end_sid is not None:
                    stops.append(end_sid)
        return (tuple(stops), tuple(agencies), transfers)

    def composite_cost(c):
        return (c[0], c[2] / 60.0, c[1], c[3])

    grouped = {}
    for result in routing_results:
        _, c, details = result
        sig = corridor_sig(details)
        cc = composite_cost(c)
        if sig not in grouped:
            grouped[sig] = {"best_cost": cc, "best_result": result, "members": [result]}
        else:
            grouped[sig]["members"].append(result)
            if cc < grouped[sig]["best_cost"]:
                grouped[sig]["best_cost"] = cc
                grouped[sig]["best_result"] = result

    deduped = []
    for group in grouped.values():
        best_path, best_c, best_details = group["best_result"]

        # Collect alternative trip_ids per leg position
        alts = {}
        for _, _, member_details in group["members"]:
            leg_i = 0
            for d in member_details:
                if d["type"] != "trip":
                    continue
                key = (leg_i, d.get("from_stop_id"), d.get("to_stop_id"), d.get("agency_id"))
                alts.setdefault(key, [])
                tid = d.get("trip_id")
                if tid and tid not in alts[key]:
                    alts[key].append(tid)
                leg_i += 1

        merged, leg_i = [], 0
        for d in best_details:
            nd = d.copy()
            if nd["type"] == "trip":
                key = (leg_i, nd.get("from_stop_id"), nd.get("to_stop_id"), nd.get("agency_id"))
                rep_tid = nd.get("trip_id")
                alt_ids = [rep_tid] + [t for t in alts.get(key, []) if t != rep_tid]
                nd["trip_ids"] = list(dict.fromkeys(alt_ids))
                leg_i += 1
            merged.append(nd)

        deduped.append((best_path, best_c, merged))
    return deduped
