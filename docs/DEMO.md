# Demo script (about 5 minutes)

Before starting: Ollama running; API running (uvicorn app.main:app --reload);
dashboard running (streamlit run dashboard\Home.py) at http://localhost:8501.

1. Home (30 s)
   "An AI writes database commands from plain-English questions. They can be wrong, reach
   private data, or be so heavy they slow the database. This is a security guard that checks
   every command before it runs." Point at the four-step cards and the three possible answers.

2. Ask in plain English (45 s) - Try it, first tab
   Click "Orders per status", then "Check and run".
   Show the green "Safe to run" card, the 4-step strip, the SQL the model wrote and the result.

3. A heavy query (60 s) - Try it, "Paste SQL" tab
   Click "Heavy query", then "Check and run".
   Show the red "Blocked" card and the plain-English reasons. Point out: a LIMIT hides the cost
   at the top of the plan, so the guardrail looks at every step.

4. Attacks (60 s) - same tab, one at a time
   "Sneaky second command", "Private table", "Private columns via *".
   For each, read the reason in plain English.

5. A harmless query that must not be blocked (30 s)
   Click "Uses CASE". Point out: false blocks matter as much as missed attacks.

6. The repair loop (45 s) - page "Question tests", section "Repair-loop stress test"
   "When the AI invents a column, the database rejects it, the reason goes back to the AI,
   and the fixed query is checked again before it runs. In a stress test where the first
   attempt had less information, correctness rose from 65% to 85%. Security problems are
   never sent back for repair."
   Optional live version: python -m evaluation.repair_demo (the last example is constructed; say so).

7. Results (60 s) - page "Results"
   Choose "Final test". Read the green and blue sentences. Compare the five approaches.
   Be honest: one runaway query was missed, some harmless queries were wrongly blocked, and
   the fixes made afterwards are not counted in these numbers.

8. History (15 s) - page "History"
   Pick a request from the dropdown to show how every decision is recorded and explained.
