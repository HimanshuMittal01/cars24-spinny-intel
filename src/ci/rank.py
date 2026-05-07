from ci.schemas import NormalizedListing, RankRow, ScoreRecord


def rank_listings(
    pairs: list[tuple[NormalizedListing, ScoreRecord]],
) -> list[RankRow]:
    rows: list[RankRow] = []
    for n, s in pairs:
        ratio = n.price / s.score_common if s.score_common > 0 else float("inf")
        rows.append(RankRow(
            listing_id=n.listing_id,
            platform=n.platform,
            price=n.price,
            rule_score=s.score_common,
            ratio=round(ratio, 2),
            disclosure_count=s.disclosure_count,
            imputed_dims=list(s.imputed_dims),
        ))
    rows.sort(key=lambda r: r.ratio)
    return rows
