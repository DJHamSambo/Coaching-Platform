# Requirements Agent

## Purpose

`/tmp/workspace/DJHamSambo/Coaching-Platform/agents/requirements_agent.py` distils raw source material into a concise, implementation-ready set of requirements for development agents.

## Supported inputs

- Inline text passed with `--text`
- Local files passed with `--file`
- Website links passed with `--url`

## Output

The agent produces markdown with these sections:

- Summary
- Functional requirements
- Non-functional requirements
- Constraints and assumptions
- Open questions
- Sources

## Usage

```bash
python /tmp/workspace/DJHamSambo/Coaching-Platform/agents/requirements_agent.py \
  --text "Build a coaching platform with session booking and reminders." \
  --file /absolute/path/to/notes.txt \
  --url https://example.com/specification \
  --title "Coaching Platform Requirements" \
  --output /absolute/path/to/requirements.md
```

## Notes

- The agent uses Python standard library only.
- Website content is fetched with `urllib` and converted to plain text with a small HTML parser.
- URL fetching is restricted to public `http` and `https` websites so local or private addresses are not processed.
- When no explicit functional requirements are detected, the summary is used as a fallback requirement set so the output stays useful.
