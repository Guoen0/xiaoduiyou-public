# Dietary recommendation safety gate

Use this when caregivers ask what a child has eaten, what is new, or what food to try next.

## Required reads

1. Read relevant food records from Growth Diary.
2. In the same workflow call `xiaoduiyou_child_get`; food history alone is insufficient because the live child profile owns allergies and avoidance rules.
3. Build two sets before recommending:
   - `recorded_eaten`: explicit ingredients from diary records.
   - `excluded`: live profile allergies/avoidances plus caregiver corrections from the current turn.

## Filtering rules

- Say `not explicitly recorded in the diary`; never claim the child definitely never ate an item.
- Composite foods with unspecified ingredients do not prove exposure to all possible ingredients.
- Category-level avoidance is recursive. Expand the stated category into its common members and derivatives, then scan protein powders, sauces, oils when requested, and processed-food ingredients instead of checking only the headline ingredient.
- Prior diary exposure without a documented reaction does not override a current caregiver restriction.
- Scan candidates, sample meals, condiments, sauces, oils, and packaged-food suggestions. A safe headline list with an unsafe example is still a failed recommendation.

## Correction recovery

If a caregiver says a recommendation is unsafe or provides a missing allergy:

1. Acknowledge the miss directly.
2. Use the child-profile workflow to read, merge, patch, and verify the allergy field without dropping existing entries.
3. Preserve certainty: keep `confirmed allergy` distinct from `temporarily avoid / treat as allergic`.
4. Discard the old recommendation list and regenerate from scratch under the updated exclusions.

If a caregiver says a proposed “new” food was actually eaten before formal diary tracking:

1. Treat the correction as authoritative and exclude the food from future novelty recommendations.
2. When asked to backfill it, create a clearly labeled historical food record so future food-history queries find it.
3. If the real eating date/time is unknown and the caregiver authorizes a pre-history placeholder date, state in the record that the timestamp is bookkeeping only and does not represent the actual meal.
4. Verify the backfill by querying each corrected ingredient separately; a multi-word query may not match combined ingredient text.

## Recommendation style

- Prefer simple, low-ingredient foods.
- Introduce one new ingredient at a time against known-safe foods.
- With multiple or broad exclusions, do not casually propose additional common allergens for home trials when history is unclear or potentially severe; suggest clinician guidance.
