# Architecture

Three layers: cli (argument parsing), core (postings and balances), store (JSON files under data/).

Hard rule: core never touches the filesystem; only store does.
