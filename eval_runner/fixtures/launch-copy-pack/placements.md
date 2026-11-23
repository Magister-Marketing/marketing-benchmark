# Placements: Halo launch

Every product (`MINI`, `ONE`, `MAX`, `PET`) gets the assets below: 18 per product, 72 in all.
An asset's id is the product code, the placement code and its number in two
digits, joined by hyphens: `MINI-SH-01` to `MINI-SH-05`, `ONE-SD-01`, and so on.

The limit is the most characters an asset may hold, every space and
punctuation mark included. "Must include" and "must not include" mean the
exact characters shown, in any case. A product's full name and its name:
MINI: `Larkspur Halo Mini`, `Halo Mini`; ONE: `Larkspur Halo One`, `Halo One`; MAX: `Larkspur Halo Max`, `Halo Max`; PET: `Larkspur Halo Pet`, `Halo Pet`.

| code | placement | channel | assets per product | limit | price allowed | must include | must not include |
|---|---|---|---:|---:|---|---|---|
| `SH` | Search ad headline | search | 5 | 30 | no | asset 01 only: the product's full name | - |
| `SD` | Search ad description | search | 2 | 90 | yes | `Larkspur` | - |
| `FP` | Social ad primary text | social | 2 | 125 | yes | the product's full name | - |
| `FH` | Social ad headline | social | 2 | 40 | no | the product's name | - |
| `ES` | Email subject line | email | 2 | 45 | no | - | the word `free` |
| `EP` | Email preheader | email | 2 | 85 | yes | the date its launch offer ends (voice rule 6) | - |
| `SM` | SMS | sms | 1 | 160 | yes | see SMS below | - |
| `PT` | Push notification title | push | 1 | 40 | no | - | `Larkspur` |
| `PB` | Push notification body | push | 1 | 100 | yes | - | - |

## Search ad headlines

No two of a product's 5 headlines open with the same two words. Two
headlines open the same way when their first two words are the same,
compared in lower case. Apostrophes are dropped, a number with its decimal
point and its % sign is one word (`99.5%`), `&` is a word, and any other
punctuation is read as a space (`2-Year` is two words).

## SMS

Every SMS opens with `Larkspur:`, carries its product's SMS link (see the
brief), and ends with exactly `Reply STOP to opt out.` All three count toward the limit.

An SMS stays within 160 characters only when every character in it is a
letter A to Z or a to z, a digit, a space, or one of these: `!"#$%&'()*+,-./:;=?@`. Any
other character (a curly apostrophe or quote, an em or en dash, an emoji, an
accented letter) sends the whole message as Unicode, and a Unicode SMS may
hold only 70 characters.
