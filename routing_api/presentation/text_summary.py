"""
Arabic / English text summary builders for enriched journeys.
"""

from routing_api.network.gtfs_lookups import GTFSLookups


def build_text_summaries(journey: dict, lookups: GTFSLookups) -> None:
    """
    Build ``text_summary`` (Arabic) and ``text_summary_en`` in-place on
    a journey dict.
    """
    arabic_stop = lambda sid: lookups.stop_to_name_ar.get(sid, lookups.stop_to_name.get(sid, ""))
    english_stop = lambda sid: lookups.stop_to_name.get(sid, "")
    arabic_route = lambda rid: lookups.route_to_short_name_ar.get(
        rid, lookups.route_to_short_name.get(rid, ""))
    english_route = lambda rid: lookups.route_to_short_name.get(rid, "")
    arabic_headsign = lambda tid: lookups.trip_to_headsign_ar.get(
        tid, lookups.trip_to_headsign.get(tid, ""))
    english_headsign = lambda tid: lookups.trip_to_headsign.get(tid, "")

    parts_ar, parts_en = [], []
    for i, leg in enumerate(journey["legs"]):
        if leg["type"] == "walk":
            if i == 0:
                nxt = next((l for l in journey["legs"][i + 1:] if l["type"] == "trip"), None)
                sid = nxt["from"]["stop_id"] if nxt else None
                parts_ar.append(f"امشي لغايه {arabic_stop(sid) if sid else ''}")
                parts_en.append(f"Walk to {english_stop(sid) or 'the stop'}")
            else:
                parts_ar.append("وتمشي لغايه وجهتك")
                parts_en.append("then walk to your destination")

        elif leg["type"] == "trip":
            tids = leg.get("trip_ids", [leg["trip_id"]])
            to_ar = arabic_stop(leg["to"]["stop_id"])
            to_en = english_stop(leg["to"]["stop_id"]) or "your stop"
            rnames_ar = list(dict.fromkeys(
                arabic_route(lookups.trip_to_route.get(t))
                for t in tids if arabic_route(lookups.trip_to_route.get(t))
            ))
            rnames_en = list(dict.fromkeys(
                english_route(lookups.trip_to_route.get(t))
                for t in tids if english_route(lookups.trip_to_route.get(t))
            ))
            hsigns_ar = list(dict.fromkeys(
                arabic_headsign(t) for t in tids if arabic_headsign(t)
            ))
            hsigns_en = list(dict.fromkeys(
                english_headsign(t) for t in tids if english_headsign(t)
            ))

            if len(rnames_ar) > 1:
                parts_ar.append(f"وتركب ({' أو '.join(rnames_ar)}) لغايه {to_ar}")
            elif len(hsigns_ar) > 1:
                parts_ar.append(
                    f"وتركب {rnames_ar[0] if rnames_ar else ''} "
                    f"({' أو '.join(hsigns_ar)}) لغايه {to_ar}"
                )
            elif rnames_ar:
                parts_ar.append(
                    f"وتركب {rnames_ar[0]} {hsigns_ar[0] if hsigns_ar else ''} لغايه {to_ar}"
                )
            else:
                parts_ar.append(f"وتركب لغايه {to_ar}")

            if len(rnames_en) > 1:
                parts_en.append(f"then take ({' or '.join(rnames_en)}) to {to_en}")
            elif len(hsigns_en) > 1:
                parts_en.append(
                    f"then take {rnames_en[0] if rnames_en else 'transit'} "
                    f"({' or '.join(hsigns_en)}) to {to_en}"
                )
            elif rnames_en:
                parts_en.append(
                    f"then take {rnames_en[0]} {hsigns_en[0] if hsigns_en else ''}".strip()
                    + f" to {to_en}"
                )
            else:
                parts_en.append(f"then take transit to {to_en}")

        elif leg["type"] == "transfer":
            sid = leg.get("end_stop_id", "")
            if arabic_stop(sid):
                parts_ar.append(f"وبعدين تمشي لغايه {arabic_stop(sid)}")
            if english_stop(sid):
                parts_en.append(f"then walk to {english_stop(sid)}")

    journey["text_summary"] = " ".join(p for p in parts_ar if p.strip())
    journey["text_summary_en"] = " ".join(p for p in parts_en if p.strip())
