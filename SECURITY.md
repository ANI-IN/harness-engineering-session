# Security policy

## Report a problem privately

If you find a security problem in this repository, such as a way for a run to leak an API key,
escape the sandbox, or reach the network, report it privately:

1. Open the repository's **Security** tab on GitHub:
   https://github.com/ANI-IN/harness-engineering-session/security
2. Choose **Report a vulnerability** and fill in the form. This opens a private security advisory
   that only the maintainers can see.

Please do not open a public issue or post about it in a course channel until it is fixed.

## Never post a key

Never paste an API key, your `.env` file, or a screenshot that shows either into an advisory, an
issue, a pull request, a support ticket, or a chat. Describe the problem and the steps to repeat it
instead. If a key was exposed anywhere, delete it on the provider's page (OpenAI or LangSmith) and
create a new one.

## What is in scope

- The `shipharness` command-line tool, the sandbox images, and the referee in `platform/`.
- The starter kit and skills in `use-in-your-repo/`.
- The course scripts and the CI workflow.

TeamTrack (`platform/teamtrack/`) is a teaching app with planted bugs and legacy code on purpose,
such as a list handler without a tenant filter. Those are part of the lessons, not security reports.

For course questions that are not about security, use the program's support channels, listed under
"Getting help" in the [README](README.md#getting-help).
