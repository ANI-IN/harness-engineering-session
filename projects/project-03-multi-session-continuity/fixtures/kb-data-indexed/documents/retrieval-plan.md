# Retrieval plan

Retrieval works on lines, not on whole files. Every non-empty line of every
document is a candidate, and a candidate is judged only by the words it
shares with the question.

## Scoring

Questions and candidates are tokenized the same way: lowercase alphanumeric
runs, keeping tokens of four characters or more. A candidate's score is the
number of distinct question tokens it contains. Repeating a word buys
nothing; overlap is counted once per token.

## Ranking

The ranking keeps the two best scoring lines and returns them as citations.
Ties break first by document identifier, then by line number, so equal
scores always resolve the same way on every machine.

## Grounding

A generated answer must quote its best citation directly. When no candidate
scores at all, the tool says so instead of inventing prose. That refusal is
the whole point of grounding.
