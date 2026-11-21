# Wrenfold Home: product description style sheet

Every product in product_specs.csv gets one description, written from its
own row, the certificate register (certificates.csv) and the warranty policy
(warranty_policy.md), and nothing else. The catalog is published on
Mar 2, 2027.

## Shape

1. 35 to 75 words, the spec line included. A word is anything between two
   spaces.
2. Begin with the product's name, exactly as the `name` column writes it.
3. End with the spec line, and put nothing after it. The spec line is:

   `Material: <material>. Dimensions: W <width_cm> x D <depth_cm> x H <height_cm> cm. Weight: <weight_kg> kg.`

   The material is written exactly as the `material` column writes it, the
   dimensions are the row's own numbers, and the `x` is a lower-case letter x.
   When `weight_kg` is blank, the spec line stops after `cm.`, with no weight
   part. For a made-up row, with and without a weight:

   `Material: solid cherry. Dimensions: W 50 x D 50 x H 50 cm. Weight: 7 kg.`

   `Material: solid cherry. Dimensions: W 50 x D 50 x H 50 cm.`

## Facts

4. Use only the product's own facts: its name, category, material, colour,
   features, certifications, warranty and where it is made. Saying what a
   listed feature plainly is or does is fine. Add no other use, feature,
   finish, care advice or comparison, and never name another product or
   another product's material.
5. Warranty: the product's warranty is its row's `warranty_years` when that
   has a number, and otherwise its category's in warranty_policy.md. State it
   once as `<n>-year warranty`, in digits with a hyphen (`2-year warranty`).
   When the product has none, say nothing about a warranty or a guarantee.
6. Where it is made: when `made_in` has a country, say `Made in <country>`.
   When it is blank, name no country and do not say where it is made.
7. Certifications: `certificate_ids` lists the product's certificates. A
   certificate counts only when certificates.csv gives it the status `valid`
   and a `valid_until` on or after the publish date. Name the `standard` of
   every certificate that counts, exactly as certificates.csv writes it, and
   no other standard. When none counts, do not use the words certified or
   certification at all.
8. Weight: only in the spec line, and only when `weight_kg` has a number.
   When it is blank, say nothing about weight anywhere.
9. A size given outside the spec line is one of the row's own dimensions, in
   cm.
10. No price: no amount of money, and none of the words price, priced,
    pricing, cost, sale or discount.
11. Last season's descriptions (previous_descriptions.md) may be reused only
    where they still agree with the row, the register and the policy.

## Words

12. Never use these words, in any case, whole or as part of a hyphenated
    word: `luxurious`, `luxury`, `timeless`, `stunning`, `perfect`, `perfectly`, `elevate`, `elevates`, `must-have`, `premium`, `eco-friendly`, `sustainable`, `non-toxic`, `handcrafted`, `handmade`, `best`.
