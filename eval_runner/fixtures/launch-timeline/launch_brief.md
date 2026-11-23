# Orlo Fold launch: plan and scheduling rules

From Mara Quill, Head of Marketing. Orlo sells reusable food containers online and through
retailers, and the Orlo Fold collapsible lunch box launches this spring. `launch_plan.csv` lists
every task of the launch and `team_calendar.md` says who works when. The work starts on Monday
2027-03-01, and I have told retail partners the launch is on **2027-05-26**. I need to know
whether that holds.

## The plan file

- `duration` and `duration_unit`: how long the task takes. A task measured in working days counts
  only its owner's working days; one measured in calendar days counts every day.
- `depends_on`: the tasks that must be finished before it can start, separated by spaces. A task
  depends only on tasks with lower IDs. An entry
  such as `T22+3` adds a lead time in calendar days: the task cannot start before the third
  calendar day after T22's finish date (if T22 finishes on a Monday, on the Thursday at the
  earliest). A plain entry such as `T22` means the day after its finish date at the earliest.
- `owner`: the one person or supplier who does it.
- `optional`: `yes` for a task we could cut.
- `not_before`: the earliest date the task can start, set from outside. Blank means none.
- `deliverable`: what the task produces. It does not change the schedule.

## Scheduling rules

1. A task starts at the start of one of its owner's working days and runs on its owner's working
   days only, for its duration: a task of 3 working days that starts on a Monday, for someone who
   works Monday to Friday, finishes at the end of Wednesday. Its finish date is the last day it
   runs. Time off, holidays and days an owner does not work pause a task; they do not count.
2. A task can start on its owner's first working day that every entry in `depends_on` allows.
3. Every owner, person or supplier, does one task at a time and takes their tasks in task ID
   order: a task cannot start before the day after the same owner's previous task (the one with
   the closest lower ID) has finished, even if it could otherwise start sooner. Nobody starts a
   later task early.
4. A task with a `not_before` date cannot start before that date.
5. No task starts before 2027-03-01. Every task starts on the earliest day rules 1 to 5 allow.
6. The launch date is the day T96 runs.

## Definitions

- A task's **slack** is the number of its owner's working days (calendar days for a supplier) its
  finish could move later without moving the launch date, if every task that waits for it
  (because it depends on it, or because its owner takes it next) moved later as needed and nothing
  else changed.
- The **critical path** is the tasks whose slack is 0, in the order they run.

## Cutting tasks

Only optional tasks can be cut. A cut task is removed from the plan: a task that depended on it
depends instead on the tasks the cut task depended on, and its owner's next task follows the
owner's task before it. Everything else, including every duration, owner, lead time and
`not_before` date, stays as it is.

If the launch misses 2027-05-26, I need the smallest set of optional tasks to cut that
brings it to 2027-05-26 or earlier: the fewest tasks; if two sets of that size both do it,
the one with the earlier launch date; if they are still tied, the one whose task IDs come first.

For the review I also want every task's slack.
