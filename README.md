# Companyeval

A local scorecard for seed investing. New deals default to an AI-assisted assessment. Manual entry is still there when you want to score a company yourself.

The AI path reads four sources: the pitch deck, the company website, founder bios, and first-call notes. It fills the same scorecard and writes a one-page partner assessment. The assessment page downloads that memo as a PDF. Every claim in that assessment has to quote the source it came from. A sentence is dropped when its excerpt is not actually in that source. The page includes the strongest argument against investing, cited the same way. Composite, screen label, flags, and benchmark positions are calculated from the extracted facts and your weights.

In manual mode you enter the facts and rate each factor from 1 to 5. The deck is stored for reference.

## Setup

Run these steps from the project root in PowerShell.

1. Install Python 3.10 or newer. Django 5.0.4 needs that version. The commands below use the Windows `py -3` launcher.

2. Create a virtual environment and activate it. `.venv` is gitignored.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Install dependencies.

```powershell
py -3 -m pip install -r requirements.txt
```

4. Optional: add an OpenAI key so AI generation can run. Create a `.env` file in the project root. The app loads that file on startup, and `.env` is gitignored.

```text
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.6-terra
```

`OPENAI_MODEL` is optional. The default model is `gpt-5.6-terra`. Scoring, flags, and benchmarks work without a key. The generate page says how to set one.

5. Create the local SQLite database (`db.sqlite3`).

```powershell
py -3 manage.py migrate
```

6. Create your account. There is no public signup.

```powershell
py -3 manage.py createsuperuser
```

7. Start the server, then open http://127.0.0.1:8000/ and sign in.

```powershell
py -3 manage.py runserver
```

Later runs only need the virtual environment activated, then `py -3 manage.py runserver`.

## How a deal is scored

Five categories, with these default weights:

| Category | Weight |
| --- | --- |
| Team | 30% |
| Market | 25% |
| Product | 20% |
| Traction | 15% |
| Deal terms | 10% |

Change the weights in Settings. They must sum to 100, and saving them recalculates every deal.

Rate each factor from 1 to 5:

- **1** is well below a typical seed company in that sector
- **3** meets that bar
- **5** is exceptional

A finished category contributes `(average / 5) × its weight`. Until all 14 factors are scored, unscored factors count as zero and the composite is marked partial. The screen label appears only when the scorecard is complete:

- 75–100 Strong pursue
- 60–74 Worth a deeper look
- 45–59 Mixed
- below 45 Lean pass

The structured facts (team, market, product, traction, terms) do not set the score. They drive risk flags and the benchmark comparison. The 1–5 ratings are your judgment.

## Benchmarks

Each sector ships with a TAM floor, a pre-money or cap band, a round-size band, and an ARR band. These numbers are working defaults for a first screen, not a live market feed. Edit them on the Benchmarks page so they match the bar you actually use.

## Tests

```bash
py -3 manage.py test evaluations
```

## Key Decisions
* Create a set of well defined criteria to run the evaluations against.
* The agent then fills out the form and generate the evaluation based on the entered data.


### Next
I'd focus on:
* the output of the web scrapper


## How I used AI
* I used AI To research and define the variables worth considering on an investment analysis at a seed stage
* For creating the working prototype.
* to write automated tests
* To debug issues