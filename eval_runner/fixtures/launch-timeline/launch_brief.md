# Orlo Fold launch: plan, calendar and scheduling rules

From Mara Quill, Head of Marketing. Orlo sells reusable food containers online, and the Orlo Fold
collapsible lunch box launches this spring. `launch_plan.csv` lists every task of the launch. The
work starts on Monday 2027-03-01, and I have told retail partners the launch is on
**2027-04-13**. I need to know whether that holds.

## The plan file

- `duration_days`: working days the task takes.
- `depends_on`: the tasks that must be finished before it can start (space-separated).
- `owner`: the one person, or the printer, who does it.
- `optional`: `yes` for a task we could cut.
- `not_before`: the earliest date the task can start, set from outside (a booked studio, a press
  embargo). Blank means none.

## Owners

- Ana: brand lead
- Ben: copywriter
- Cleo: designer
- Dev: web developer
- Esme: PR and partnerships
- Finn: paid media
- Gia: lifecycle and support
- Printer: the outside packaging printer

## Calendar

Working days are Monday to Friday, except these company holidays:

- 2027-03-12 (company offsite)
- 2027-03-26 (Good Friday)
- 2027-03-29 (Easter Monday)

## Scheduling rules

1. A task starts at the start of a working day and runs for its duration in working days: a
   3-day task that starts on a Monday finishes at the end of Wednesday. Its finish date is its
   last working day.
2. A task can start on the first working day after every task it depends on has finished.
3. An owner does one task at a time and takes their tasks in task ID order: a task cannot start
   until the same owner's previous task (the one with the closest lower ID) has finished, even if
   it could otherwise start sooner. Nobody starts a later task early.
4. A task with a `not_before` date cannot start before that date, or before the first working
   day after it when the date is not a working day.
5. No task starts before 2027-03-01. Every task starts on the earliest working day that
   rules 2 to 5 allow.
6. The launch date is the day T24 runs.

## Definitions

- A task's **slack** is the number of working days its finish could move later without moving
  the launch date, if every task that waits for it (because it depends on it, or because its
  owner takes it next) moved later as needed and nothing else changed.
- The **critical path** is the tasks whose slack is 0, in the order they run.

## Cutting tasks

Only optional tasks can be cut. A cut task is removed from the plan: a task that depended on it
depends instead on the tasks the cut task depended on, and its owner's next task follows the
owner's task before it. Everything else, including every duration, owner and `not_before` date,
stays as it is.

If the launch misses 2027-04-13, I need the smallest set of optional tasks to cut that
brings it to 2027-04-13 or earlier: the fewest tasks; if two sets of that size both do it,
the one with the earlier launch date; if they are still tied, the one whose task IDs come first.

For the review I also want the slack of T06, T11, T16.
