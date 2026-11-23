# Simulated companies

[Back to the overview](../README.md) · [Tasks](TASKS.md) ·
[How scoring works](SCORING.md)

This is a second, newer kind of task. **It is not on the board**, and no
results from it are published yet.

On the board, a model writes an answer from supplied files and a checklist
grades the answer. Here the model works inside a made-up company instead. The
company's apps are emulated: each one answers through the real app's API
shapes, keeps its own state, and holds the company's products, customers,
campaigns and records. The model reads and changes that state through the
APIs, as a person with access would. When the attempt ends, code reads the
company's apps again and decides whether the job was done. There is no judge
model, and no part credit: an attempt passes or fails.

The harness for these tasks lives in Magister's private repository today, not
in this one.

## The two companies

Both companies are invented. Their websites use names under `.test`, a
top-level domain reserved for testing, so no real site is ever reached.

| Company | What it is | Its site |
|---|---|---|
| **Ninebark Coffee** | An online coffee store | `ninebark-coffee.test` |
| **Paywren** | A software company that sells by subscription | `paywren.test` |

Eight tasks are set at Ninebark Coffee and two at Paywren.

## The ten tasks

Each task starts with a message from the company's owner. The descriptions
below say what the owner asks for and what makes it hard. They do not say
what the answer is.

### Workflow: do a multi-app job exactly

| Task | Company | The job | Apps |
|---|---|---|---|
| `launch-flavor` | Ninebark Coffee | Get a seasonal flavour's launch ready from the brief in Notion: the product page, the launch posts and the launch email, timed as the brief says, with nothing going public early. | Notion, Shopify, Zernio, Mailchimp |
| `weekly-numbers` | Ninebark Coffee | Add last week's numbers to the reporting log in Notion, every figure worked out under the team's own reporting rules from the store's apps, and change nothing else. | Notion, GA4, Shopify, Google Ads, Search Console |
| `wholesale-leads` | Ninebark Coffee | Take the new wholesale inquiries that came in through the site, put the real ones into the CRM and the follow-up sequence as the team's playbook says, and leave everything else alone. | Notion, Formspree, HubSpot, Instantly |
| `monthly-numbers` | Paywren | Add last month's subscription figures (recurring revenue and how it moved, trial conversion, new paying accounts from ads and what they cost) to the log in Notion, exactly under the rules page, and change nothing else. | Stripe, HubSpot, Google Ads, Notion |

### Judgement: find the one real problem, or refuse what policy forbids

| Task | Company | The job | Apps |
|---|---|---|---|
| `cold-brew-drop` | Ninebark Coffee | Find what took one product's sales away, fix only that, and log it the way earlier incidents were logged. Several other things in the company look wrong and are not. | Shopify, the store's site, Google Ads, Search Console, GA4, Notion |
| `partner-promo` | Ninebark Coffee | A new partner asks for changes to the ads and an entry in the CRM. Do the part the company's own policies allow, refuse the part they forbid, and record the refusal where requests are logged. | Notion, Google Ads, HubSpot |

### Outcome: run something over simulated days, scored on the money it made

| Task | Company | The job | Apps |
|---|---|---|---|
| `ads-pacing-10d` | Ninebark Coffee | Run three search campaigns' budgets for ten simulated days for the most profit, under a spending cap. The market it is selling into is hidden. | Google Ads, Notion |
| `test-calls-14d` | Ninebark Coffee | Make the calls on several running A/B tests on review mornings over two simulated weeks (ship, keep, stop or let them run) for the most order value. The true conversion rates are hidden. | GA4, Notion |
| `send-plan-14d` | Ninebark Coffee | Look over a planned email calendar on several mornings over two simulated weeks and change what needs changing (leave a send, move it, send it to another segment, or cancel it). How subscribers respond is hidden. | Mailchimp, Notion |
| `acquisition-21d` | Paywren | Run a software company's Google Ads budgets over three simulated weeks for the most profit from the paying accounts the ads bring in, under a spending cap. The market is hidden. | Google Ads, Stripe, Notion |

## How each kind is scored

- **Workflow and judgement tasks.** Code reads the company's apps before and
  after the attempt and checks two things: everything the owner asked for is
  there, exactly as the company's own documents say it should be; and nothing
  else changed. Every check must hold for the attempt to pass.
- **Outcome tasks.** A simulator runs the days. On each review morning the
  model looks at the apps and acts; between mornings the hidden market
  responds to what it did. The attempt is scored on the money actually made
  in the simulation, placed on a scale from doing nothing (0) to a planner
  that knows the hidden market (1). To pass, it must reach a set line on that
  scale and meet the task's other conditions, such as keeping to the spending
  cap on every day.
- **Invalid, not failed.** When an app the checks read cannot be read, or the
  harness itself fails, the attempt is recorded as invalid and left unscored.
  It never counts as a failure of the model.

## Worlds and tiers

- **Worlds.** A seed draws a task's hidden details, and the same seed always
  draws the same details; dates are set from the day the attempt runs. Each
  task has three practice worlds and three scored worlds, on different
  seeds, so the worlds a setup is developed on are not the worlds it is
  scored on.
- **Tiers.** Six tasks also come in three scale tiers: tier 2 and tier 3 are
  larger versions of the same job. A seed draws the same details at every
  tier, and a run picks one tier (tier 1 by default). The other four tasks
  (`monthly-numbers`, `test-calls-14d`, `send-plan-14d` and
  `acquisition-21d`) have tier 1 only.
- **Limits.** Each task limits one attempt's tool calls and minutes, and some
  also its turns, tokens or spend.

## The setups

The same three setups as the board, adapted to working in a company:

| Setup | What does the work |
|---|---|
| Model only | The model in a plain tool loop: it can call the emulated apps' APIs and read their API documentation |
| + Marketing Skills | The same loop, with a fixed set of marketing skill documents added to the prompt |
| Inside Magister | Magister's agent on the same model, on a test lane whose connected apps are the same emulators; every attempt starts from the brand's clean state, and an attempt whose brand is not in that state before it starts is invalid |

## Status

First runs exist for one model only, and they are incomplete. They are not on
the board. Results will be published when all three models have run in all
three setups.
